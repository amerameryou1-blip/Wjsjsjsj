from pathlib import Path
import base64

import requests

API_BASE = "https://api.github.com"
API_VERSION = "2022-11-28"


def build_headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
    }


def get_existing_sha(owner, repo, repo_path, token, branch="main"):
    url = f"{API_BASE}/repos/{owner}/{repo}/contents/{repo_path}"
    response = requests.get(
        url,
        headers=build_headers(token),
        params={"ref": branch},
        timeout=60,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json().get("sha")


def upsert_bytes(owner, repo, token, repo_path, blob_bytes, branch="main", commit_message=None):
    url = f"{API_BASE}/repos/{owner}/{repo}/contents/{repo_path}"
    payload = {
        "message": commit_message or f"Update {repo_path}",
        "content": base64.b64encode(blob_bytes).decode("utf-8"),
        "branch": branch,
    }

    existing_sha = get_existing_sha(owner, repo, repo_path, token, branch=branch)
    if existing_sha:
        payload["sha"] = existing_sha

    response = requests.put(url, headers=build_headers(token), json=payload, timeout=60)
    if response.status_code not in (200, 201):
        raise RuntimeError(f"GitHub push failed for {repo_path}: {response.status_code} {response.text}")

    data = response.json()
    html_url = data.get("content", {}).get("html_url", "")
    print(f"[pushed] {repo_path} -> {html_url}")
    return data


def push_path_map(owner, repo, token, path_map, branch="main", commit_message="Update Kaggle launcher system"):
    results = []
    for repo_path, local_path in path_map.items():
        local_path = Path(local_path)
        if not local_path.exists():
            print(f"[skip] missing {local_path}")
            continue
        results.append(
            upsert_bytes(
                owner=owner,
                repo=repo,
                token=token,
                repo_path=repo_path,
                blob_bytes=local_path.read_bytes(),
                branch=branch,
                commit_message=commit_message,
            )
        )
    print(f"Done. Pushed {len(results)} file(s) to {owner}/{repo}@{branch}.")
    return results
