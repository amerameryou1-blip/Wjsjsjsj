import os
import sys
import json
import subprocess


def pip_install(packages):
    env = dict(os.environ)
    env.setdefault('PIP_ROOT_USER_ACTION', 'ignore')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + packages, check=False, env=env)


pip_install([
    'requests',
    'ipywidgets',
    'Pillow',
    'ipyevents',
])

import requests

OWNER = 'amerameryou1-blip'
REPO = 'Wjsjsjsj'
BRANCH = 'main'
PREFIX = ''
BUNDLE_FILES = [
    'browser_controller_support.py',
    'browser_controller_main.py',
]



def state_root():
    kaggle_root = '/kaggle/working'
    if os.path.isdir(kaggle_root):
        return os.path.join(kaggle_root, 'zorin_kaggle_desktop')
    return os.path.join('/tmp', 'zorin_kaggle_desktop')



def bundle_dir():
    path_value = os.path.join(state_root(), 'bundle-cache')
    os.makedirs(path_value, exist_ok=True)
    return path_value



def launcher_report_path():
    os.makedirs(state_root(), exist_ok=True)
    return os.path.join(state_root(), 'launcher-report.json')



def build_raw_url(owner_value, repo_value, branch_value, path_value):
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + path_value



def fetch_text(url_value):
    response = requests.get(url_value, timeout=90)
    response.raise_for_status()
    return response.text



def fetch_bundle():
    cached_paths = {}
    for file_name in BUNDLE_FILES:
        repo_path = (PREFIX.strip('/') + '/' + file_name).strip('/')
        local_path = os.path.join(bundle_dir(), file_name)
        url_value = build_raw_url(OWNER, REPO, BRANCH, repo_path)
        print('Fetching:', url_value)
        text_value = fetch_text(url_value)
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
        print('Bundle fetch failed:', str(exc))
        cached = load_cached_bundle()
        if cached:
            print('Using cached bundle from previous run.')
            return cached
        raise



def execute_support(paths_map):
    support_path = paths_map['browser_controller_support.py']
    support_ns = {'__name__': 'browser_controller_support'}
    support_code = open(support_path, 'r', encoding='utf-8').read()
    exec(compile(support_code, support_path, 'exec'), support_ns)
    return support_ns



def execute_main(paths_map, support_ns):
    main_path = paths_map['browser_controller_main.py']
    main_ns = {
        '__name__': '__main__',
        '__browser_support__': support_ns,
        '__browser_bundle_paths__': paths_map,
    }
    main_code = open(main_path, 'r', encoding='utf-8').read()
    exec(compile(main_code, main_path, 'exec'), main_ns)



def main():
    paths_map = load_bundle_with_fallback()
    support_ns = execute_support(paths_map)
    install_report = support_ns['install_or_repair_stack'](include_browser=True)
    report = {
        'timestamp': support_ns['now_text'](),
        'state_root': support_ns['detect_state_root']() if 'detect_state_root' in support_ns else state_root(),
        'bundle_paths': paths_map,
        'browser_found': install_report.get('browser_found', ''),
        'persistent': install_report.get('persistent', False),
    }
    with open(launcher_report_path(), 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(report, indent=2, ensure_ascii=False))
    execute_main(paths_map, support_ns)


if __name__ == '__main__':
    main()
