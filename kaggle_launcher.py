import os
import sys
import json
import shutil
import subprocess


def pip_install(packages):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + packages, check=False)


pip_install(['requests', 'ipywidgets', 'Pillow', 'xvfbwrapper', 'ipyevents'])

import requests

OWNER = 'amerameryou1-blip'
REPO = 'Wjsjsjsj'
BRANCH = 'main'
PREFIX = ''
BUNDLE_FILES = [
    'browser_controller_main.py',
    'browser_controller_support.py',
]


def state_root():
    kaggle_root = '/kaggle/working'
    if os.path.isdir(kaggle_root):
        return os.path.join(kaggle_root, 'browser_controller_state')
    return '/tmp/browser_controller_state'


def bundle_dir():
    path_value = os.path.join(state_root(), 'bundle-cache')
    os.makedirs(path_value, exist_ok=True)
    return path_value


def build_raw_url(owner_value, repo_value, branch_value, path_value):
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + path_value


def fetch_text(url_value):
    response = requests.get(url_value, timeout=60)
    response.raise_for_status()
    return response.text


def ensure_system_tools():
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    os.environ['DISPLAY'] = ':99'
    os.environ['XDG_RUNTIME_DIR'] = os.path.join(state_root(), 'runtime')
    os.makedirs(os.environ['XDG_RUNTIME_DIR'], exist_ok=True)
    os.makedirs(os.path.join(state_root(), 'downloads'), exist_ok=True)
    os.makedirs(os.path.join(state_root(), 'chrome-profile'), exist_ok=True)

    packages = [
        'xvfb', 'xdotool', 'scrot', 'imagemagick', 'wget', 'curl', 'ca-certificates', 'fonts-liberation',
        'libatk1.0-0', 'libatk-bridge2.0-0', 'libatspi2.0-0', 'libvulkan1', 'libxcomposite1',
        'libxdamage1', 'libxrandr2', 'libgbm1', 'libasound2', 'libpangocairo-1.0-0',
        'libpango-1.0-0', 'libgtk-3-0', 'libnss3', 'libxshmfence1', 'xdg-utils'
    ]

    need_install = False
    for tool_name in ['Xvfb', 'xdotool', 'scrot']:
        if shutil.which(tool_name) is None:
            need_install = True
            break

    browser_found = False
    for browser_name in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium']:
        if shutil.which(browser_name) is not None:
            browser_found = True
            break

    if not browser_found:
        need_install = True

    if need_install:
        subprocess.run('apt-get update -y', shell=True, check=False)
        subprocess.run('apt-get install -y ' + ' '.join(packages), shell=True, check=False)
        browser_found = False
        for browser_name in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium']:
            if shutil.which(browser_name) is not None:
                browser_found = True
                break
        if not browser_found:
            subprocess.run('wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb', shell=True, check=False)
            subprocess.run('apt-get install -y /tmp/chrome.deb || true', shell=True, check=False)
            subprocess.run('apt-get -f install -y || true', shell=True, check=False)
            subprocess.run('apt-get install -y /tmp/chrome.deb || true', shell=True, check=False)
            if shutil.which('google-chrome') is None and shutil.which('google-chrome-stable') is None:
                subprocess.run('apt-get install -y chromium-browser || apt-get install -y chromium || true', shell=True, check=False)


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
    ensure_system_tools()
    paths_map = load_bundle_with_fallback()
    execute_bundle(paths_map)


if __name__ == '__main__':
    main()
