import importlib
import shutil
import subprocess
import sys

APT_PACKAGES = ["chromium-chromedriver"]
PIP_PACKAGES = [
    ("requests", "requests"),
    ("selenium", "selenium"),
]


def run_command(command):
    print("$", " ".join(command))
    subprocess.run(command, check=True)


def ensure_apt_packages(packages):
    if not shutil.which("apt-get"):
        print("apt-get not available on this runtime. Skipping apt packages.")
        return
    run_command(["apt-get", "update", "-y"])
    run_command(["apt-get", "install", "-y", *packages])


def ensure_pip_packages(packages):
    missing = []
    for package_name, module_name in packages:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if missing:
        run_command([sys.executable, "-m", "pip", "install", "-q", *missing])
    else:
        print("Required pip packages already installed.")


def ensure_runtime():
    ensure_apt_packages(APT_PACKAGES)
    ensure_pip_packages(PIP_PACKAGES)


if __name__ == "__main__":
    ensure_runtime()
