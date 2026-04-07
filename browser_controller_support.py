import os
import json
import html
import time

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


def state_root():
    if os.path.isdir('/kaggle/working'):
        return os.path.join('/kaggle/working', 'simple_linux_controller')
    return '/tmp/simple_linux_controller'


def ensure_state_dirs():
    root = state_root()
    bundle_dir = os.path.join(root, 'bundle')
    os.makedirs(bundle_dir, exist_ok=True)
    return {
        'root': root,
        'bundle_dir': bundle_dir,
        'config_path': os.path.join(root, 'controller_config.json'),
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
    return 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + str(path_value).strip('/')


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


def html_card(title_text, lines, accent='#22d3ee'):
    rendered_lines = ''.join(
        '<div style="margin-top:8px;line-height:1.6;color:#cbd5e1;">' + html.escape(str(line)) + '</div>'
        for line in (lines or [])
    )
    return (
        '<div style="margin:10px 0;padding:18px 20px;border-radius:22px;border:1px solid rgba(255,255,255,0.12);'
        'background:#081225;color:#fff;box-shadow:0 10px 30px rgba(0,0,0,0.15);">'
        '<div style="font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:' + accent + ';font-weight:700;">Card</div>'
        '<div style="font-size:24px;font-weight:800;margin-top:8px;">' + html.escape(str(title_text)) + '</div>'
        + rendered_lines +
        '</div>'
    )


def html_code_block(text_value):
    return (
        '<pre style="overflow:auto;white-space:pre-wrap;word-break:break-word;background:#020617;color:#e2e8f0;'
        'padding:18px;border-radius:20px;border:1px solid rgba(255,255,255,0.08);line-height:1.7;">'
        + html.escape(str(text_value)) + '</pre>'
    )


def build_readme_text(owner_value, repo_value, branch_value, prefix_value):
    launcher_path = repo_path(prefix_value, DEFAULT_LAUNCHER_PATH)
    launcher_url = build_raw_url(owner_value, repo_value, branch_value, launcher_path)
    return '\n'.join([
        '# One-Tap Kaggle Controller Bundle',
        '',
        '## Fast flow',
        '',
        '1. Open the website.',
        '2. Paste your GitHub key.',
        '3. Tap **Do everything for me**.',
        '4. The site uploads the bundle and copies `kaggle_launcher.py`.',
        '5. Open Kaggle, paste the launcher into one cell, and run it.',
        '',
        'Repo: ' + owner_value + '/' + repo_value,
        'Branch: ' + branch_value,
        'Prefix: ' + (prefix_value or 'repo root'),
        '',
        'Launcher raw URL:',
        launcher_url,
        '',
        'Includes:',
        '- visible control screen',
        '- Google quick action',
        '- Linux helper',
        '- Kaggle-ready launcher',
    ])
