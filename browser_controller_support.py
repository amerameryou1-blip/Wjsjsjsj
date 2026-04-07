import os
import json
import html
import time
import base64
from urllib.parse import quote

DEFAULT_OWNER = 'amerameryou1-blip'
DEFAULT_REPO = 'Wjsjsjsj'
DEFAULT_BRANCH = 'main'
DEFAULT_PREFIX = ''
DEFAULT_MAIN_PATH = 'browser_controller_main.py'
DEFAULT_SUPPORT_PATH = 'browser_controller_support.py'
DEFAULT_FULL_PATH = 'browser_controller_full.py'
DEFAULT_LAUNCHER_PATH = 'kaggle_launcher.py'
DEFAULT_README_PATH = 'README.md'
BUNDLE_FILE_ORDER = [
    DEFAULT_README_PATH,
    DEFAULT_SUPPORT_PATH,
    DEFAULT_MAIN_PATH,
    DEFAULT_FULL_PATH,
    DEFAULT_LAUNCHER_PATH,
]
PRIMARY_EXECUTION_FILES = [
    DEFAULT_SUPPORT_PATH,
    DEFAULT_MAIN_PATH,
]
ANTIGRAVITY_DOWNLOAD_URL = 'https://antigravity.google/download/linux'
ANTIGRAVITY_HOME_URL = 'https://antigravity.google/download'
ANTIGRAVITY_DEB_COMMANDS = '\n'.join([
    'sudo mkdir -p /etc/apt/keyrings',
    'curl -fsSL https://us-central1-apt.pkg.dev/doc/repo-signing-key.gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/antigravity-repo-key.gpg',
    'echo "deb [signed-by=/etc/apt/keyrings/antigravity-repo-key.gpg] https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/ antigravity-debian main" | sudo tee /etc/apt/sources.list.d/antigravity.list > /dev/null',
    'sudo apt update',
    'sudo apt install -y antigravity',
    'antigravity',
])
ANTIGRAVITY_RPM_COMMANDS = '\n'.join([
    "sudo tee /etc/yum.repos.d/antigravity.repo <<'EOL'",
    '[antigravity-rpm]',
    'name=Antigravity RPM Repository',
    'baseurl=https://us-central1-yum.pkg.dev/projects/antigravity-auto-updater-dev/antigravity-rpm',
    'enabled=1',
    'gpgcheck=0',
    'EOL',
    'sudo dnf makecache',
    'sudo dnf install -y antigravity',
    'antigravity',
])


def now_text():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def detect_state_root():
    kaggle_root = '/kaggle/working'
    if os.path.isdir(kaggle_root):
        return os.path.join(kaggle_root, 'kaggle_bundle_state')
    return '/tmp/kaggle_bundle_state'


def ensure_state_dirs():
    root = detect_state_root()
    bundle_dir = os.path.join(root, 'bundle-cache')
    logs_dir = os.path.join(root, 'logs')
    temp_dir = os.path.join(root, 'temp')
    config_path = os.path.join(root, 'dashboard_config.json')
    for path_value in [root, bundle_dir, logs_dir, temp_dir]:
        os.makedirs(path_value, exist_ok=True)
    return {
        'root': root,
        'bundle_dir': bundle_dir,
        'logs_dir': logs_dir,
        'temp_dir': temp_dir,
        'config_path': config_path,
        'is_kaggle': os.path.isdir('/kaggle/working'),
    }


def file_read_text(path_value):
    with open(path_value, 'r', encoding='utf-8') as handle:
        return handle.read()


def file_write_text(path_value, text_value):
    parent = os.path.dirname(path_value)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path_value, 'w', encoding='utf-8') as handle:
        handle.write(text_value)


def load_json(path_value, default_value):
    try:
        with open(path_value, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return default_value


def save_json(path_value, data_value):
    temp_path = path_value + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as handle:
        json.dump(data_value, handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, path_value)


def repo_path(prefix_value, file_name):
    prefix_clean = prefix_value.strip('/')
    if prefix_clean:
        return prefix_clean + '/' + file_name
    return file_name


def build_raw_url(owner_value, repo_value, branch_value, path_value):
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + path_value.strip('/')


def fetch_text(requests_module, url_value, timeout=60):
    response = requests_module.get(url_value, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_bundle_files(requests_module, owner_value, repo_value, branch_value, prefix_value, file_names, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    bundle_map = {}
    for file_name in file_names:
        remote_path = repo_path(prefix_value, file_name)
        url_value = build_raw_url(owner_value, repo_value, branch_value, remote_path)
        text_value = fetch_text(requests_module, url_value, timeout=60)
        if file_name.endswith('.py'):
            compile(text_value, file_name, 'exec')
        local_path = os.path.join(target_dir, file_name)
        file_write_text(local_path, text_value)
        bundle_map[file_name] = {
            'name': file_name,
            'repo_path': remote_path,
            'url': url_value,
            'local_path': local_path,
            'content': text_value,
        }
    return bundle_map


def load_bundle_from_directory(base_dir, file_names):
    if not os.path.isdir(base_dir):
        return {}
    bundle_map = {}
    for file_name in file_names:
        local_path = os.path.join(base_dir, file_name)
        if not os.path.exists(local_path):
            continue
        bundle_map[file_name] = {
            'name': file_name,
            'repo_path': file_name,
            'url': '',
            'local_path': local_path,
            'content': file_read_text(local_path),
        }
    return bundle_map


def merge_bundle_maps(*bundle_maps):
    merged = {}
    for bundle_map in bundle_maps:
        for key, value in bundle_map.items():
            merged[key] = value
    return merged


def bundle_summary_lines(bundle_map):
    lines = []
    for file_name in BUNDLE_FILE_ORDER:
        item = bundle_map.get(file_name)
        if not item:
            continue
        lines.append(file_name + ' → ' + item.get('local_path', ''))
    return lines


def github_headers(token_value):
    return {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token_value.strip(),
        'X-GitHub-Api-Version': '2022-11-28',
    }


def github_validate_token(requests_module, token_value):
    response = requests_module.get('https://api.github.com/user', headers=github_headers(token_value), timeout=60)
    if response.status_code != 200:
        raise RuntimeError('GitHub token invalid or missing repo access')
    data = response.json()
    return {
        'login': str(data.get('login') or ''),
        'name': str(data.get('name') or ''),
        'id': str(data.get('id') or ''),
    }


def github_check_repo_access(requests_module, token_value, owner_value, repo_value):
    url_value = 'https://api.github.com/repos/' + owner_value + '/' + repo_value
    response = requests_module.get(url_value, headers=github_headers(token_value), timeout=60)
    if response.status_code != 200:
        raise RuntimeError('Cannot access repository ' + owner_value + '/' + repo_value)
    data = response.json()
    permissions = data.get('permissions') or {}
    can_push = bool(permissions.get('push') or permissions.get('admin') or permissions.get('maintain'))
    return {
        'full_name': str(data.get('full_name') or (owner_value + '/' + repo_value)),
        'default_branch': str(data.get('default_branch') or ''),
        'private': bool(data.get('private')),
        'can_push': can_push,
    }


def github_existing_sha(requests_module, token_value, owner_value, repo_value, branch_value, path_value):
    encoded_path = quote(path_value.strip('/'), safe='/')
    url_value = 'https://api.github.com/repos/' + owner_value + '/' + repo_value + '/contents/' + encoded_path
    response = requests_module.get(
        url_value,
        headers=github_headers(token_value),
        params={'ref': branch_value},
        timeout=60,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data.get('sha')


def github_upsert_file(requests_module, token_value, owner_value, repo_value, branch_value, path_value, content_text, commit_message):
    encoded_path = quote(path_value.strip('/'), safe='/')
    url_value = 'https://api.github.com/repos/' + owner_value + '/' + repo_value + '/contents/' + encoded_path
    sha_value = github_existing_sha(requests_module, token_value, owner_value, repo_value, branch_value, path_value)
    payload = {
        'message': commit_message,
        'content': base64.b64encode(content_text.encode('utf-8')).decode('ascii'),
        'branch': branch_value,
    }
    if sha_value:
        payload['sha'] = sha_value
    response = requests_module.put(url_value, headers=github_headers(token_value), json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def github_upsert_many(requests_module, token_value, owner_value, repo_value, branch_value, files_map, commit_prefix):
    results = []
    for path_value, content_text in files_map.items():
        result = github_upsert_file(
            requests_module,
            token_value,
            owner_value,
            repo_value,
            branch_value,
            path_value,
            content_text,
            commit_prefix + ' · ' + path_value,
        )
        results.append(result)
    return results


def html_card(title_text, body_lines, accent='#7c3aed'):
    parts = []
    parts.append('<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;background:#0f172a;border:1px solid #1e293b;border-left:4px solid ' + accent + ';border-radius:14px;padding:16px 18px;margin:10px 0;">')
    parts.append('<div style="font-size:15px;font-weight:700;color:#f8fafc;margin-bottom:10px;">' + html.escape(title_text) + '</div>')
    for line in body_lines:
        parts.append('<div style="font-size:13px;line-height:1.6;color:#cbd5e1;margin:3px 0;">' + html.escape(line) + '</div>')
    parts.append('</div>')
    return ''.join(parts)


def html_code_block(title_text, code_text):
    return ''.join([
        '<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;background:#020617;border:1px solid #1e293b;border-radius:14px;padding:16px 18px;margin:10px 0;">',
        '<div style="font-size:14px;font-weight:700;color:#f8fafc;margin-bottom:10px;">' + html.escape(title_text) + '</div>',
        '<pre style="margin:0;white-space:pre-wrap;word-break:break-word;color:#93c5fd;font-size:12px;line-height:1.65;">' + html.escape(code_text) + '</pre>',
        '</div>',
    ])


def build_readme_text(owner_value, repo_value, branch_value, prefix_value):
    prefix_clean = prefix_value.strip('/')
    if prefix_clean:
        prefix_clean = prefix_clean + '/'
    raw_base = 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/'
    tree_url = 'https://github.com/' + owner_value + '/' + repo_value + '/tree/' + branch_value
    lines = [
        '# Kaggle Bundle Uploader',
        '',
        'This repository stores a Kaggle-ready bundle that can be uploaded from the website and launched from a Kaggle notebook.',
        '',
        '## Quick flow',
        '1. Open the website and paste a GitHub token with repo write access.',
        '2. Upload the bundle files to this repository.',
        '3. Copy `kaggle_launcher.py` into a Kaggle notebook cell and run it.',
        '',
        '## Repository target',
        '- Owner: ' + owner_value,
        '- Repo: ' + repo_value,
        '- Branch: ' + branch_value,
        '- Prefix: ' + (prefix_clean or '(repo root)'),
        '',
        '## Files',
        '- `' + prefix_clean + 'README.md`',
        '- `' + prefix_clean + 'browser_controller_support.py`',
        '- `' + prefix_clean + 'browser_controller_main.py`',
        '- `' + prefix_clean + 'browser_controller_full.py`',
        '- `' + prefix_clean + 'kaggle_launcher.py`',
        '',
        '## Raw URLs',
        '- README: ' + raw_base + prefix_clean + 'README.md',
        '- Support: ' + raw_base + prefix_clean + 'browser_controller_support.py',
        '- Main: ' + raw_base + prefix_clean + 'browser_controller_main.py',
        '- Full: ' + raw_base + prefix_clean + 'browser_controller_full.py',
        '- Launcher: ' + raw_base + prefix_clean + 'kaggle_launcher.py',
        '',
        '## GitHub tree',
        tree_url,
        '',
        '## Antigravity Linux install',
        'Debian/Ubuntu and RPM commands are included in the website and Kaggle dashboard.',
        '',
        'Generated on: ' + now_text(),
        '',
    ]
    return '\n'.join(lines)
