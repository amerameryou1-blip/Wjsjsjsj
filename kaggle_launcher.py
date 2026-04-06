import os
import sys
import subprocess


def pip_install(packages):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + packages, check=False)


pip_install(['requests'])

import requests

OWNER = 'amerameryou1-blip'
REPO = 'Wjsjsjsj'
BRANCH = 'main'
PREFIX = ''
BACKEND_FILE = 'kaggle_ngrok_backend.py'


def state_root():
    kaggle_root = '/kaggle/working'
    if os.path.isdir(kaggle_root):
        path_value = os.path.join(kaggle_root, 'browser_remote_state')
    else:
        path_value = '/tmp/browser_remote_state'
    os.makedirs(path_value, exist_ok=True)
    return path_value


def cache_path():
    return os.path.join(state_root(), BACKEND_FILE)


def build_raw_url(owner_value, repo_value, branch_value, path_value):
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + path_value


def fetch_backend_text():
    repo_path = (PREFIX.strip('/') + '/' + BACKEND_FILE).strip('/')
    url_value = build_raw_url(OWNER, REPO, BRANCH, repo_path)
    print('Fetching backend from:', url_value)
    response = requests.get(url_value, timeout=90)
    response.raise_for_status()
    code_text = response.text
    compile(code_text, BACKEND_FILE, 'exec')
    with open(cache_path(), 'w', encoding='utf-8') as handle:
        handle.write(code_text)
    return code_text


def load_cached_backend():
    cached_file = cache_path()
    if not os.path.exists(cached_file):
        return None
    with open(cached_file, 'r', encoding='utf-8') as handle:
        code_text = handle.read()
    compile(code_text, cached_file, 'exec')
    print('Using cached backend:', cached_file)
    return code_text


def load_backend_with_fallback():
    try:
        return fetch_backend_text()
    except Exception as exc:
        print('Remote fetch failed:', str(exc))
        cached = load_cached_backend()
        if cached:
            return cached
        raise


def main():
    code_text = load_backend_with_fallback()
    namespace = {'__name__': '__main__'}
    exec(compile(code_text, BACKEND_FILE, 'exec'), namespace)


if __name__ == '__main__':
    main()
