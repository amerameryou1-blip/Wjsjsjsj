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
DEFAULT_README_PATH = 'README.md'
DEFAULT_SUPPORT_PATH = 'browser_controller_support.py'
DEFAULT_MAIN_PATH = 'browser_controller_main.py'
DEFAULT_FULL_PATH = 'browser_controller_full.py'
DEFAULT_LAUNCHER_PATH = 'kaggle_launcher.py'
BUNDLE_FILE_ORDER = [
    DEFAULT_README_PATH,
    DEFAULT_SUPPORT_PATH,
    DEFAULT_MAIN_PATH,
    DEFAULT_FULL_PATH,
    DEFAULT_LAUNCHER_PATH,
]
GOOGLE_HOME_URL = 'https://www.google.com/'
ANTIGRAVITY_HOME_URL = 'https://antigravity.google/download'
ANTIGRAVITY_DOWNLOAD_URL = 'https://antigravity.google/download/linux'
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
    if os.path.isdir('/kaggle/working'):
        return os.path.join('/kaggle/working', 'simple_linux_controller')
    return '/tmp/simple_linux_controller'


def ensure_state_dirs():
    root = detect_state_root()
    bundle_dir = os.path.join(root, 'bundle')
    logs_dir = os.path.join(root, 'logs')
    os.makedirs(bundle_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    return {
        'root': root,
        'bundle_dir': bundle_dir,
        'logs_dir': logs_dir,
        'config_path': os.path.join(root, 'dashboard_config.json'),
        'log_path': os.path.join(logs_dir, 'dashboard.log'),
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
    file_write_text(path_value, json.dumps(data_value, indent=2, ensure_ascii=False))


def repo_path(prefix_value, file_name):
    clean_prefix = str(prefix_value or '').strip().strip('/')
    if clean_prefix:
        return clean_prefix + '/' + file_name
    return file_name


def build_raw_url(owner_value, repo_value, branch_value, path_value):
    clean_path = str(path_value or '').strip('/').strip()
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + clean_path


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
        for key, value in (bundle_map or {}).items():
            merged[key] = value
    return merged


def bundle_summary_lines(bundle_map):
    lines = []
    for file_name in BUNDLE_FILE_ORDER:
        item = (bundle_map or {}).get(file_name)
        if not item:
            continue
        lines.append(file_name + ' -> ' + str(item.get('local_path') or ''))
    if not lines:
        lines.append('No files loaded yet.')
    return lines


def github_headers(token_value):
    return {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + str(token_value).strip(),
        'X-GitHub-Api-Version': '2022-11-28',
    }


def github_validate_token(requests_module, token_value):
    response = requests_module.get('https://api.github.com/user', headers=github_headers(token_value), timeout=60)
    if response.status_code != 200:
        raise RuntimeError('GitHub token is invalid or missing permissions.')
    data = response.json()
    return {
        'login': str(data.get('login') or ''),
        'name': str(data.get('name') or ''),
        'id': str(data.get('id') or ''),
    }


def github_repo_info(requests_module, token_value, owner_value, repo_value):
    url_value = 'https://api.github.com/repos/' + owner_value + '/' + repo_value
    response = requests_module.get(url_value, headers=github_headers(token_value), timeout=60)
    if response.status_code != 200:
        raise RuntimeError('Cannot access repository ' + owner_value + '/' + repo_value)
    data = response.json()
    permissions = data.get('permissions') or {}
    return {
        'full_name': str(data.get('full_name') or owner_value + '/' + repo_value),
        'default_branch': str(data.get('default_branch') or ''),
        'can_push': bool(permissions.get('push') or permissions.get('admin') or permissions.get('maintain')),
    }


def github_existing_sha(requests_module, token_value, owner_value, repo_value, branch_value, path_value):
    encoded_path = quote(str(path_value).strip('/'), safe='/')
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
    return (response.json() or {}).get('sha')


def github_upload_file(requests_module, token_value, owner_value, repo_value, branch_value, path_value, content_text, commit_message):
    encoded_path = quote(str(path_value).strip('/'), safe='/')
    url_value = 'https://api.github.com/repos/' + owner_value + '/' + repo_value + '/contents/' + encoded_path
    sha_value = github_existing_sha(requests_module, token_value, owner_value, repo_value, branch_value, path_value)
    payload = {
        'message': commit_message,
        'content': base64.b64encode(str(content_text).encode('utf-8')).decode('ascii'),
        'branch': branch_value,
    }
    if sha_value:
        payload['sha'] = sha_value
    response = requests_module.put(url_value, headers=github_headers(token_value), json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def github_upload_bundle(requests_module, token_value, owner_value, repo_value, branch_value, prefix_value, bundle_map, commit_prefix):
    results = []
    for file_name in BUNDLE_FILE_ORDER:
        item = (bundle_map or {}).get(file_name)
        if not item:
            continue
        target_path = repo_path(prefix_value, file_name)
        result = github_upload_file(
            requests_module,
            token_value,
            owner_value,
            repo_value,
            branch_value,
            target_path,
            item.get('content') or '',
            (commit_prefix or 'Upload bundle') + ' · ' + target_path,
        )
        results.append({
            'file_name': file_name,
            'repo_path': target_path,
            'result': result,
        })
    return results


def html_card(title_text, lines, accent='#38bdf8'):
    safe_lines = ''.join('<li style="margin:6px 0;">' + html.escape(str(line)) + '</li>' for line in lines)
    return (
        '<div style="border:1px solid ' + accent + ';border-radius:16px;padding:16px;background:#0f172a;color:#e2e8f0;">'
        '<div style="font-size:18px;font-weight:700;margin-bottom:8px;">' + html.escape(str(title_text)) + '</div>'
        '<ul style="margin:0;padding-left:18px;">' + safe_lines + '</ul>'
        '</div>'
    )


def html_code_block(text_value):
    return (
        '<pre style="white-space:pre-wrap;background:#020617;color:#dbeafe;border:1px solid #334155;'
        'padding:16px;border-radius:14px;overflow:auto;">'
        + html.escape(str(text_value))
        + '</pre>'
    )


def build_readme_text(owner_value, repo_value, branch_value, prefix_value):
    prefix_label = prefix_value.strip('/') or 'repo root'
    lines = [
        '# Simple Linux Controller Bundle',
        '',
        'This repo stores a simple Kaggle-ready bundle and launcher.',
        '',
        '## Simple steps',
        '',
        '1. Open the website.',
        '2. Paste your GitHub token in the upload box.',
        '3. Click **Upload bundle to GitHub**.',
        '4. Copy `kaggle_launcher.py` from the website.',
        '5. Paste it into one Kaggle notebook cell.',
        '6. Run the cell.',
        '',
        '## Repo settings',
        '',
        '- Owner: `' + owner_value + '`',
        '- Repo: `' + repo_value + '`',
        '- Branch: `' + branch_value + '`',
        '- Prefix: `' + prefix_label + '`',
        '',
        '## Bundle files',
        '',
        '- README.md',
        '- browser_controller_support.py',
        '- browser_controller_main.py',
        '- browser_controller_full.py',
        '- kaggle_launcher.py',
        '',
        '## Linux install',
        '',
        'The dashboard includes Antigravity Linux commands for deb-based and rpm-based distributions.',
        '',
        '## Quick links',
        '',
        '- Google: ' + GOOGLE_HOME_URL,
        '- Antigravity: ' + ANTIGRAVITY_DOWNLOAD_URL,
    ]
    return '\n'.join(lines) + '\n'
