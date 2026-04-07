#!/usr/bin/env python3
"""Antigravity install-and-launch probe for Kaggle.

What it does:
1. Adds the documented Antigravity apt repository.
2. Installs Antigravity plus a lightweight X11 stack for notebook use.
3. Launches a virtual desktop on Xvfb with Openbox.
4. Starts Antigravity and captures a screenshot.
5. Saves all state, logs, and screenshots under /kaggle/working.

This script is intentionally self-contained and does not overwrite the existing
browser controller files in this repository.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

BASE_DIR = Path(os.environ.get("ANTIGRAVITY_PROBE_DIR", "/kaggle/working/antigravity_probe")).resolve()
HOME_DIR = BASE_DIR / "home"
CACHE_DIR = BASE_DIR / "cache"
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
SCREENSHOT_DIR = BASE_DIR / "screenshots"
SCREENSHOT_PATH = SCREENSHOT_DIR / "antigravity-launch.png"
REPORT_PATH = BASE_DIR / "report.json"
SESSION_PATH = BASE_DIR / "session.json"
DISPLAY_NAME = os.environ.get("ANTIGRAVITY_DISPLAY", ":99")
SCREEN_GEOMETRY = os.environ.get("ANTIGRAVITY_SCREEN", "1600x900x24")
REPO_LINE = (
    "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] "
    "https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ "
    "antigravity-debian main"
)
APP_PACKAGES = [
    "ca-certificates",
    "curl",
    "dbus-x11",
    "desktop-file-utils",
    "openbox",
    "procps",
    "python3",
    "scrot",
    "wmctrl",
    "x11-utils",
    "xauth",
    "xclip",
    "xdg-utils",
    "xdotool",
    "xvfb",
    "antigravity",
]


@dataclass
class ProbeReport:
    ok: bool
    install_ok: bool
    launch_ok: bool
    apt_candidate_seen: bool
    antigravity_command: list[str]
    screenshot_path: str
    screenshot_exists: bool
    session_path: str
    base_dir: str
    window_lines: list[str]
    process_lines: list[str]
    notes: list[str]
    last_error: str
    started_at: float
    finished_at: float


class ProbeError(RuntimeError):
    pass


class Runner:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_file = log_path.open("a", encoding="utf-8")

    def close(self) -> None:
        self.log_file.close()

    def write(self, message: str) -> None:
        print(message)
        self.log_file.write(message + "\n")
        self.log_file.flush()

    def run(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        check: bool = True,
        text_input: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.write(f"$ {' '.join(shlex.quote(part) for part in command)}")
        completed = subprocess.run(
            list(command),
            input=text_input,
            capture_output=True,
            text=True,
            env=dict(env) if env is not None else None,
            cwd=str(cwd) if cwd else None,
        )
        if completed.stdout.strip():
            self.write(completed.stdout.rstrip())
        if completed.stderr.strip():
            self.write(completed.stderr.rstrip())
        if check and completed.returncode != 0:
            raise ProbeError(
                f"Command failed with exit code {completed.returncode}: {' '.join(command)}"
            )
        return completed

    def popen(
        self,
        command: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.Popen[str]:
        self.write(f"[spawn] {' '.join(shlex.quote(part) for part in command)}")
        return subprocess.Popen(
            list(command),
            stdout=self.log_file,
            stderr=self.log_file,
            stdin=subprocess.DEVNULL,
            text=True,
            env=dict(env) if env is not None else None,
            cwd=str(cwd) if cwd else None,
            start_new_session=True,
        )


def ensure_directories() -> None:
    for path in [BASE_DIR, HOME_DIR, CACHE_DIR, CONFIG_DIR, DATA_DIR, LOG_DIR, SCREENSHOT_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def sudo_prefix() -> list[str]:
    return [] if os.geteuid() == 0 else ["sudo"]


def parse_dbus_exports(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^(DBUS_[A-Z_]+)=(.*?);", line.strip())
        if not match:
            continue
        key = match.group(1)
        raw_value = match.group(2).strip()
        if raw_value.startswith("'") and raw_value.endswith("'"):
            raw_value = raw_value[1:-1]
        values[key] = raw_value
    return values


def write_root_text(runner: Runner, target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.geteuid() == 0:
        target.write_text(content, encoding="utf-8")
        return
    runner.run(["sudo", "tee", str(target)], text_input=content)


def install_antigravity(runner: Runner) -> bool:
    runner.write("Preparing Antigravity apt repository...")
    runner.run(sudo_prefix() + ["mkdir", "-p", "/etc/apt/keyrings"])

    key_temp = BASE_DIR / "antigravity-repo-key.gpg"
    runner.run(
        [
            "bash",
            "-lc",
            (
                "curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg "
                f"| gpg --dearmor --yes -o {shlex.quote(str(key_temp))}"
            ),
        ]
    )
    runner.run(sudo_prefix() + ["cp", str(key_temp), "/etc/apt/keyrings/antigravity-repo-key.gpg"])
    write_root_text(runner, Path("/etc/apt/sources.list.d/antigravity.list"), REPO_LINE + "\n")

    runner.write("Refreshing apt metadata...")
    runner.run(sudo_prefix() + ["apt-get", "update"])

    policy = runner.run(["apt-cache", "policy", "antigravity"], check=False)
    candidate_seen = "Candidate:" in (policy.stdout or "") and "(none)" not in (policy.stdout or "")

    runner.write("Installing Antigravity and desktop helpers...")
    runner.run(
        sudo_prefix()
        + [
            "apt-get",
            "install",
            "-y",
            "--no-install-recommends",
            *APP_PACKAGES,
        ]
    )
    return candidate_seen


def build_session_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(HOME_DIR),
            "DISPLAY": DISPLAY_NAME,
            "XDG_CACHE_HOME": str(CACHE_DIR),
            "XDG_CONFIG_HOME": str(CONFIG_DIR),
            "XDG_DATA_HOME": str(DATA_DIR),
            "NO_AT_BRIDGE": "1",
        }
    )
    return env


def wait_for_display(runner: Runner, env: Mapping[str, str]) -> None:
    for _ in range(50):
        probe = runner.run(["xdpyinfo", "-display", DISPLAY_NAME], env=env, check=False)
        if probe.returncode == 0:
            return
        time.sleep(0.3)
    raise ProbeError(f"X display {DISPLAY_NAME} did not become ready")


def stop_previous_processes(runner: Runner) -> None:
    runner.run(["bash", "-lc", f"pkill -f 'Xvfb {DISPLAY_NAME}' || true"], check=False)
    runner.run(["bash", "-lc", "pkill -f '(^|/)openbox($| )' || true"], check=False)
    runner.run(["bash", "-lc", "pkill -f '(^|/)antigravity($| )' || true"], check=False)


def start_virtual_desktop(runner: Runner, env: dict[str, str]) -> tuple[subprocess.Popen[str], subprocess.Popen[str], dict[str, str]]:
    stop_previous_processes(runner)

    xvfb = runner.popen(
        [
            "Xvfb",
            DISPLAY_NAME,
            "-screen",
            "0",
            SCREEN_GEOMETRY,
            "-ac",
            "+extension",
            "RANDR",
            "-dpi",
            "96",
            "-nolisten",
            "tcp",
        ],
        env=env,
    )
    wait_for_display(runner, env)

    dbus_launch = runner.run(["dbus-launch", "--sh-syntax"], env=env)
    env.update(parse_dbus_exports(dbus_launch.stdout))

    openbox = runner.popen(["openbox"], env=env)
    time.sleep(2)
    return xvfb, openbox, env


def parse_exec_from_desktop_file(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("Exec="):
            continue
        exec_line = line.split("=", 1)[1].strip()
        cleaned = [part for part in shlex.split(exec_line) if not part.startswith("%")]
        return cleaned or None
    return None


def detect_antigravity_command() -> list[str]:
    direct = shutil.which("antigravity")
    if direct:
        return [direct]

    desktop_candidates = [
        Path("/usr/share/applications/antigravity.desktop"),
        Path("/usr/share/applications/google-antigravity.desktop"),
    ]
    for desktop_file in desktop_candidates:
        parsed = parse_exec_from_desktop_file(desktop_file)
        if parsed:
            return parsed

    for root, _, files in os.walk("/usr/share/applications"):
        for filename in files:
            if "antigravity" not in filename.lower() or not filename.endswith(".desktop"):
                continue
            parsed = parse_exec_from_desktop_file(Path(root) / filename)
            if parsed:
                return parsed

    raise ProbeError("Could not locate the Antigravity launcher after installation")


def launch_antigravity(runner: Runner, env: Mapping[str, str]) -> tuple[list[str], subprocess.Popen[str]]:
    command = detect_antigravity_command()
    command_to_run = list(command)

    if os.geteuid() == 0 and "--no-sandbox" not in command_to_run:
        command_to_run.append("--no-sandbox")

    process = runner.popen(command_to_run, env=env, cwd=HOME_DIR)
    time.sleep(16)
    return command_to_run, process


def capture_screenshot(runner: Runner, env: Mapping[str, str]) -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "scrot",
            "-o",
            "-D",
            DISPLAY_NAME,
            str(SCREENSHOT_PATH),
        ],
        env=env,
    )


def collect_window_lines(runner: Runner, env: Mapping[str, str]) -> list[str]:
    windows = runner.run(["wmctrl", "-lx"], env=env, check=False)
    return [line for line in (windows.stdout or "").splitlines() if line.strip()]


def collect_process_lines(runner: Runner) -> list[str]:
    processes = runner.run(["bash", "-lc", "ps -ef | grep -i antigravity | grep -v grep"], check=False)
    return [line for line in (processes.stdout or "").splitlines() if line.strip()]


def save_session(process: subprocess.Popen[str], xvfb: subprocess.Popen[str], openbox: subprocess.Popen[str]) -> None:
    SESSION_PATH.write_text(
        json.dumps(
            {
                "display": DISPLAY_NAME,
                "screen": SCREEN_GEOMETRY,
                "base_dir": str(BASE_DIR),
                "home": str(HOME_DIR),
                "screenshot": str(SCREENSHOT_PATH),
                "antigravity_pid": process.pid,
                "xvfb_pid": xvfb.pid,
                "openbox_pid": openbox.pid,
                "saved_at": time.time(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def show_notebook_artifacts() -> None:
    try:
        from IPython.display import Image, JSON, display  # type: ignore
    except Exception:
        return

    if SCREENSHOT_PATH.exists():
        display(Image(filename=str(SCREENSHOT_PATH)))
    if REPORT_PATH.exists():
        with REPORT_PATH.open("r", encoding="utf-8") as handle:
            display(JSON(json.load(handle)))


def terminate_if_dead(process: subprocess.Popen[str], notes: list[str]) -> None:
    return_code = process.poll()
    if return_code is not None:
        notes.append(f"Antigravity exited early with code {return_code}.")


def main() -> int:
    ensure_directories()
    log_path = LOG_DIR / "antigravity_probe.log"
    runner = Runner(log_path)
    started_at = time.time()
    notes: list[str] = []
    last_error = ""
    apt_candidate_seen = False
    install_ok = False
    launch_ok = False
    antigravity_command: list[str] = []
    window_lines: list[str] = []
    process_lines: list[str] = []

    try:
        runner.write("Starting Antigravity Kaggle probe...")
        runner.write(f"Saving state under: {BASE_DIR}")
        apt_candidate_seen = install_antigravity(runner)
        install_ok = True

        env = build_session_env()
        xvfb, openbox, session_env = start_virtual_desktop(runner, env)
        antigravity_command, process = launch_antigravity(runner, session_env)
        terminate_if_dead(process, notes)
        capture_screenshot(runner, session_env)
        window_lines = collect_window_lines(runner, session_env)
        process_lines = collect_process_lines(runner)
        save_session(process, xvfb, openbox)

        if any("antigravity" in line.lower() for line in window_lines) or process.poll() is None:
            launch_ok = True
        if SCREENSHOT_PATH.exists():
            notes.append(f"Screenshot saved to {SCREENSHOT_PATH}")
        else:
            notes.append("Screenshot file was not created.")
        if SESSION_PATH.exists():
            notes.append(f"Session info saved to {SESSION_PATH}")

    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
        notes.append(last_error)
        runner.write(f"ERROR: {last_error}")

    finished_at = time.time()
    report = ProbeReport(
        ok=install_ok and (launch_ok or SCREENSHOT_PATH.exists()),
        install_ok=install_ok,
        launch_ok=launch_ok,
        apt_candidate_seen=apt_candidate_seen,
        antigravity_command=antigravity_command,
        screenshot_path=str(SCREENSHOT_PATH),
        screenshot_exists=SCREENSHOT_PATH.exists(),
        session_path=str(SESSION_PATH),
        base_dir=str(BASE_DIR),
        window_lines=window_lines,
        process_lines=process_lines,
        notes=notes,
        last_error=last_error,
        started_at=started_at,
        finished_at=finished_at,
    )
    REPORT_PATH.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    runner.write(f"Report written to {REPORT_PATH}")
    runner.write(f"Screenshot path: {SCREENSHOT_PATH}")
    runner.write(f"Log path: {log_path}")
    show_notebook_artifacts()
    runner.close()
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
