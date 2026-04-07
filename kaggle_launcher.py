import os
import sys
import subprocess


# Paste this whole file into one Kaggle notebook cell and run it.
# Change these values only if your GitHub repository is different.
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


def pip_install(packages):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q'] + packages, check=False)


def state_root():
    if os.path.isdir('/kaggle/working'):
        return os.path.join('/kaggle/working', 'simple_linux_controller')
    return '/tmp/simple_linux_controller'


def bundle_dir():
    path_value = os.path.join(state_root(), 'bundle')
    os.makedirs(path_value, exist_ok=True)
    return path_value


def repo_path(prefix_value, file_name):
    clean_prefix = str(prefix_value or '').strip().strip('/')
    if clean_prefix:
        return clean_prefix + '/' + file_name
    return file_name


def raw_url(owner_value, repo_value, branch_value, path_value):
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + path_value.strip('/')


def fetch_bundle(requests_module):
    paths_map = {}
    for file_name in BUNDLE_FILES:
        repo_file_path = repo_path(PREFIX, file_name)
        url_value = raw_url(OWNER, REPO, BRANCH, repo_file_path)
        print('Fetching:', url_value)
        response = requests_module.get(url_value, timeout=60)
        response.raise_for_status()
        text_value = response.text
        if file_name.endswith('.py'):
            compile(text_value, file_name, 'exec')
        local_path = os.path.join(bundle_dir(), file_name)
        with open(local_path, 'w', encoding='utf-8') as handle:
            handle.write(text_value)
        paths_map[file_name] = local_path
    return paths_map


def run_bundle(paths_map):
    support_path = paths_map['browser_controller_support.py']
    main_path = paths_map['browser_controller_main.py']

    support_ns = {'__name__': 'browser_controller_support'}
    with open(support_path, 'r', encoding='utf-8') as handle:
        support_code = handle.read()
    exec(compile(support_code, support_path, 'exec'), support_ns)

    main_ns = {
        '__name__': '__main__',
        '__browser_support__': support_ns,
        '__browser_bundle_paths__': paths_map,
    }
    with open(main_path, 'r', encoding='utf-8') as handle:
        main_code = handle.read()
    exec(compile(main_code, main_path, 'exec'), main_ns)


def main():
    print('Simple Kaggle launcher')
    print('Owner:', OWNER)
    print('Repo:', REPO)
    print('Branch:', BRANCH)
    print('Prefix:', PREFIX or '(repo root)')
    print('Installing small Python packages...')
    pip_install(['requests', 'ipywidgets'])

    import requests

    print('Downloading bundle files from GitHub...')
    paths_map = fetch_bundle(requests)
    print('Starting dashboard...')
    run_bundle(paths_map)


if __name__ == '__main__':
    main()
