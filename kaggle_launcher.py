import os
import sys
import subprocess


def pip_install(packages):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + packages, check=False)


pip_install(['requests', 'ipywidgets'])

import requests

# Replace these values only if your GitHub repository is different.
OWNER = 'amerameryou1-blip'
REPO = 'Wjsjsjsj'
BRANCH = 'main'
PREFIX = ''
BUNDLE_FILES = [
    'README.md',
    'browser_controller_support.py',
    'browser_controller_main.py',
    'browser_controller_full.py',
    'kaggle_launcher.py',
]


def state_root():
    kaggle_root = '/kaggle/working'
    if os.path.isdir(kaggle_root):
        return os.path.join(kaggle_root, 'kaggle_bundle_state')
    return '/tmp/kaggle_bundle_state'


def bundle_dir():
    path_value = os.path.join(state_root(), 'bundle-cache')
    os.makedirs(path_value, exist_ok=True)
    return path_value


def build_raw_url(owner_value, repo_value, branch_value, path_value):
    clean_path = path_value.strip('/')
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + clean_path


def repo_path(prefix_value, file_name):
    prefix_clean = prefix_value.strip('/')
    if prefix_clean:
        return prefix_clean + '/' + file_name
    return file_name


def fetch_text(url_value):
    response = requests.get(url_value, timeout=60)
    response.raise_for_status()
    return response.text


def fetch_bundle():
    cached_paths = {}
    for file_name in BUNDLE_FILES:
        remote_path = repo_path(PREFIX, file_name)
        local_path = os.path.join(bundle_dir(), file_name)
        url_value = build_raw_url(OWNER, REPO, BRANCH, remote_path)
        print('Fetching:', url_value)
        text_value = fetch_text(url_value)
        if file_name.endswith('.py'):
            compile(text_value, file_name, 'exec')
        with open(local_path, 'w', encoding='utf-8') as handle:
            handle.write(text_value)
        cached_paths[file_name] = local_path
    return cached_paths


def load_cached_bundle():
    cached_paths = {}
    for file_name in BUNDLE_FILES:
        local_path = os.path.join(bundle_dir(), file_name)
        if not os.path.exists(local_path):
            return None
        cached_paths[file_name] = local_path
    return cached_paths


def load_bundle_with_fallback():
    try:
        return fetch_bundle()
    except Exception as exc:
        print('Fetch failed:', str(exc))
        cached = load_cached_bundle()
        if cached:
            print('Using cached bundle from previous run.')
            return cached
        raise


def execute_bundle(paths_map):
    support_path = paths_map['browser_controller_support.py']
    main_path = paths_map['browser_controller_main.py']

    support_ns = {'__name__': 'browser_controller_support'}
    support_code = open(support_path, 'r', encoding='utf-8').read()
    exec(compile(support_code, support_path, 'exec'), support_ns)

    main_ns = {
        '__name__': '__main__',
        '__browser_support__': support_ns,
        '__browser_bundle_paths__': paths_map,
    }
    main_code = open(main_path, 'r', encoding='utf-8').read()
    exec(compile(main_code, main_path, 'exec'), main_ns)


def main():
    print('Loading Kaggle bundle from GitHub...')
    print('Owner:', OWNER)
    print('Repo:', REPO)
    print('Branch:', BRANCH)
    print('Prefix:', PREFIX or '(repo root)')
    paths_map = load_bundle_with_fallback()
    execute_bundle(paths_map)


if __name__ == '__main__':
    main()
