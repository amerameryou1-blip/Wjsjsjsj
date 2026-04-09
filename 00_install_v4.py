#!/usr/bin/env python3
"""Install a Kaggle-friendly llama.cpp stack for local GGUF inference."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


WORKDIR = Path("/kaggle/working")
CACHE_DIR = WORKDIR / ".cache"
PIP_CACHE_DIR = CACHE_DIR / "pip"
BIN_DIR = WORKDIR / "bin"
LLAMA_CPP_DIR = WORKDIR / "llama.cpp"
LLAMA_CPP_BUILD_DIR = LLAMA_CPP_DIR / "build"
SERVER_HINT_FILE = WORKDIR / "llama-server-path.txt"
CUDA_NVCC = Path("/usr/local/cuda/bin/nvcc")


def run_command(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    """Run a subprocess with clear logging."""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    print(f"\n[RUN] {' '.join(command)}")
    subprocess.run(command, check=True, cwd=str(cwd) if cwd else None, env=merged_env)


def get_installed_version(package_name: str) -> str | None:
    """Return the installed version for a package, or None if missing."""
    try:
        metadata = importlib.import_module("importlib.metadata")
    except ImportError:
        metadata = importlib.import_module("importlib_metadata")

    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def ensure_python_package(
    spec: str,
    package_name: str,
    minimum_version: str | None = None,
    *,
    required: bool = True,
    extra_args: list[str] | None = None,
) -> None:
    """Install a package only if needed."""
    if minimum_version:
        from packaging.version import Version

        installed = get_installed_version(package_name)
        if installed is not None and Version(installed) >= Version(minimum_version):
            print(f"[OK] {package_name} {installed} already satisfies >= {minimum_version}")
            return
    else:
        installed = get_installed_version(package_name)
        if installed is not None:
            print(f"[OK] {package_name} {installed} is already installed")
            return

    command = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if extra_args:
        command.extend(extra_args)
    command.append(spec)

    try:
        run_command(command)
    except Exception:
        if required:
            raise
        print(f"[WARN] Optional package install failed and will be skipped: {spec}")


def bootstrap_python_stack() -> None:
    """Install build helpers without upgrading Kaggle's working cmake to 4.x."""
    ensure_python_package("packaging", "packaging")
    ensure_python_package("ninja", "ninja")
    ensure_python_package("scikit-build-core", "scikit-build-core")
    # Kaggle already ships a usable cmake; we pin below 4 because cmake 4.x has
    # caused configure/build regressions for llama.cpp in practice.
    ensure_python_package("cmake<4", "cmake", minimum_version="3.27.0")


def install_runtime_packages() -> None:
    """Install the requested runtime stack."""
    ensure_python_package(
        "transformers>=5.5.0",
        "transformers",
        minimum_version="5.5.0",
        extra_args=["--pre"],
    )
    ensure_python_package("torch", "torch")
    ensure_python_package("accelerate", "accelerate")
    ensure_python_package("bitsandbytes", "bitsandbytes", required=False)
    ensure_python_package("pillow", "Pillow")
    ensure_python_package("timm", "timm")
    ensure_python_package("hf_transfer", "hf_transfer")
    ensure_python_package("huggingface_hub", "huggingface-hub")
    ensure_python_package("requests", "requests")
    ensure_python_package("sentencepiece", "sentencepiece")


def ensure_llama_cpp_checkout() -> None:
    """Clone llama.cpp if needed."""
    if LLAMA_CPP_DIR.exists():
        print(f"[OK] Reusing llama.cpp checkout at {LLAMA_CPP_DIR}")
        return

    run_command(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/ggml-org/llama.cpp.git",
            str(LLAMA_CPP_DIR),
        ]
    )


def build_standalone_llama_server() -> Path:
    """Build the standalone CUDA llama-server binary."""
    if not CUDA_NVCC.exists():
        raise RuntimeError(
            "CUDA compiler not found at /usr/local/cuda/bin/nvcc. "
            "This Kaggle image cannot build CUDA llama.cpp from source."
        )

    existing_binary = BIN_DIR / "llama-server"
    if existing_binary.exists():
        SERVER_HINT_FILE.write_text(str(existing_binary), encoding="utf-8")
        print(f"[OK] Reusing existing llama-server at {existing_binary}")
        return existing_binary

    env = os.environ.copy()
    env["CUDACXX"] = str(CUDA_NVCC)

    configure_command = [
        "cmake",
        "-S",
        str(LLAMA_CPP_DIR),
        "-B",
        str(LLAMA_CPP_BUILD_DIR),
        "-DGGML_CUDA=ON",
        "-DGGML_NATIVE=OFF",
        "-DLLAMA_BUILD_SERVER=ON",
        "-DLLAMA_CURL=OFF",
        "-DCMAKE_CUDA_ARCHITECTURES=75",
        "-DCMAKE_BUILD_TYPE=Release",
    ]
    build_command = [
        "cmake",
        "--build",
        str(LLAMA_CPP_BUILD_DIR),
        "--target",
        "llama-server",
        "--config",
        "Release",
        "-j",
        "2",
    ]

    run_command(configure_command, env=env)
    run_command(build_command, env=env)

    candidates = [
        LLAMA_CPP_BUILD_DIR / "bin" / "llama-server",
        LLAMA_CPP_BUILD_DIR / "bin" / "Release" / "llama-server",
    ]
    for candidate in candidates:
        if candidate.exists():
            BIN_DIR.mkdir(parents=True, exist_ok=True)
            target = BIN_DIR / "llama-server"
            shutil.copy2(candidate, target)
            target.chmod(0o755)
            SERVER_HINT_FILE.write_text(str(target), encoding="utf-8")
            print(f"[OK] Built standalone llama-server at {target}")
            return target

    raise FileNotFoundError(
        "llama-server build finished without producing a binary. "
        f"Checked: {', '.join(str(path) for path in candidates)}"
    )


def main() -> None:
    try:
        print("[INFO] Starting Kaggle install step for local GGUF inference...")
        WORKDIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        PIP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
        os.environ["PIP_CACHE_DIR"] = str(PIP_CACHE_DIR)

        bootstrap_python_stack()
        install_runtime_packages()
        ensure_llama_cpp_checkout()
        build_standalone_llama_server()
        print("[SUCCESS] 00_install_v4.py completed.")
    except Exception as exc:
        print(f"[ERROR] 00_install_v4.py failed: {exc}")
        raise


if __name__ == "__main__":
    main()
