import base64
import importlib.util
import subprocess
import sys
from pathlib import Path

if importlib.util.find_spec("requests") is None:
    print("[SETUP] Installing requests...")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)

import requests

WORKDIR = Path("/kaggle/working")
WORKDIR.mkdir(parents=True, exist_ok=True)

REPO_OWNER = "amerameryou1-blip"
REPO_NAME = "Wjsjsjsj"
BRANCH = "main"
BASE_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}"
FILES = [
    "00_install.py",
    "01_auth.py",
    "02_download_model.py",
    "03_run_server.py",
    "04_inference_test.py",
    "05_github_uploader.py",
]

headers = {}
try:
    from kaggle_secrets import UserSecretsClient

    github_token = UserSecretsClient().get_secret("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
except Exception as secret_exc:
    print(f"[WARN] Could not load GITHUB_TOKEN for raw file fetches: {secret_exc}")

for filename in FILES:
    url = f"{BASE_URL}/{filename}"
    destination = WORKDIR / filename
    print(f"[FETCH-START] {filename} <- {url}")
    response = requests.get(url, headers=headers, timeout=120)
    if response.status_code == 200:
        destination.write_text(response.text, encoding="utf-8")
    else:
        print(
            f"[WARN] Raw fetch failed for {filename} with status {response.status_code}; "
            "trying GitHub Contents API fallback."
        )
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{filename}"
        api_headers = {"Accept": "application/vnd.github+json"}
        if "Authorization" in headers:
            api_headers["Authorization"] = headers["Authorization"]
        api_response = requests.get(api_url, headers=api_headers, params={"ref": BRANCH}, timeout=120)
        api_response.raise_for_status()
        payload = api_response.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        destination.write_text(content, encoding="utf-8")
    print(f"[FETCH-DONE] Saved {filename} to {destination}")

for filename in FILES:
    script_path = WORKDIR / filename
    print(f"[RUN-START] {filename}")
    subprocess.run([sys.executable, str(script_path)], check=True)
    print(f"[RUN-DONE] {filename}")

print("[SUCCESS] Kaggle Gemma 4 setup finished.")
