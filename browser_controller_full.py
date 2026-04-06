# Bundle reference
#
# This file is only a convenience copy for the website viewer.
# Preferred repo layout for the launcher:
# - browser_controller_main.py
# - browser_controller_support.py
#
# Copy the two files from the website sections if you want the cleanest repo layout.

# ===== browser_controller_support.py =====

import os
import re
import json
import html
import time
import base64
import shutil
import subprocess
from urllib.parse import quote_plus


DISPLAY_VALUE = ':99'
SCREEN_W = 1280
SCREEN_H = 800

URL_GOOGLE = 'https://www.google.com/'
URL_GOOGLE_LOGIN = 'https://accounts.google.com/'
URL_KAGGLE_CPU_SEARCH = 'https://www.google.com/search?q=' + quote_plus('Kaggle notebook CPU cores runtime')
URL_CODEX_WEB = 'https://chatgpt.com/codex'
URL_CODEX_APP = 'https://developers.openai.com/codex/app'
URL_CODEX_CLI_RELEASES = 'https://github.com/openai/codex/releases/latest'
URL_ANTIGRAVITY_APP = 'https://antigravity.google/download'

DEFAULT_OWNER = 'amerameryou1-blip'
DEFAULT_REPO = 'Wjsjsjsj'
DEFAULT_BRANCH = 'main'
DEFAULT_PREFIX = ''
DEFAULT_MAIN_PATH = 'browser_controller_main.py'
DEFAULT_SUPPORT_PATH = 'browser_controller_support.py'
DEFAULT_README_PATH = 'README.md'


def now_text():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def detect_state_root():
    kaggle_working = '/kaggle/working'
    if os.path.isdir(kaggle_working):
        return os.path.join(kaggle_working, 'browser_controller_state')
    return '/tmp/browser_controller_state'


def ensure_state_dirs():
    root = detect_state_root()
    runtime_dir = os.path.join(root, 'runtime')
    profile_dir = os.path.join(root, 'chrome-profile')
    downloads_dir = os.path.join(root, 'downloads')
    bundle_dir = os.path.join(root, 'bundle-cache')
    state_json = os.path.join(root, 'state.json')
    logs_dir = os.path.join(root, 'logs')

    for path in [root, runtime_dir, profile_dir, downloads_dir, bundle_dir, logs_dir]:
        os.makedirs(path, exist_ok=True)

    os.environ['DISPLAY'] = DISPLAY_VALUE
    os.environ['XDG_RUNTIME_DIR'] = runtime_dir
    return {
        'root': root,
        'runtime_dir': runtime_dir,
        'profile_dir': profile_dir,
        'downloads_dir': downloads_dir,
        'bundle_dir': bundle_dir,
        'state_json': state_json,
        'logs_dir': logs_dir,
        'persistent': root.startswith('/kaggle/working/'),
    }


def display_env(extra_env=None):
    env = dict(os.environ)
    env['DISPLAY'] = DISPLAY_VALUE
    env.setdefault('XDG_RUNTIME_DIR', '/tmp/browser-controller-runtime')
    os.makedirs(env['XDG_RUNTIME_DIR'], exist_ok=True)
    if extra_env:
        env.update(extra_env)
    return env


def run_list(args, env=None, capture_output=True, check=False):
    return subprocess.run(
        args,
        env=display_env(env),
        text=True,
        capture_output=capture_output,
        check=check,
    )


def run_shell(command, env=None):
    return subprocess.run(
        command,
        shell=True,
        env=display_env(env),
        text=True,
        capture_output=True,
    )


def which_any(candidates):
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def find_browser_binary():
    return which_any(['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium'])


def file_read_text(path_value):
    with open(path_value, 'r', encoding='utf-8') as handle:
        return handle.read()


def file_write_text(path_value, text_value):
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


def detect_cpu_info():
    count = os.cpu_count() or 1
    model = 'Unknown CPU'
    try:
        with open('/proc/cpuinfo', 'r', encoding='utf-8', errors='ignore') as handle:
            cpuinfo = handle.read()
        match = re.search(r'model name\s*:\s*(.+)', cpuinfo)
        if match:
            model = match.group(1).strip()
    except Exception:
        pass
    return str(count) + ' cores detected · ' + model


def profile_has_previous_session(profile_dir):
    candidates = [
        os.path.join(profile_dir, 'Default'),
        os.path.join(profile_dir, 'Local State'),
        os.path.join(profile_dir, 'First Run'),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return True
    return False


def prune_profile(profile_dir):
    removed = []
    trash_names = [
        'Cache',
        'Code Cache',
        'GPUCache',
        'DawnCache',
        'DawnGraphiteCache',
        'GrShaderCache',
        'GraphiteDawnCache',
        'ShaderCache',
        'Media Cache',
        'Service Worker/CacheStorage',
        'Default/Cache',
        'Default/Code Cache',
        'Default/GPUCache',
        'Default/Media Cache',
        'Default/Service Worker/CacheStorage',
    ]
    for name in trash_names:
        path_value = os.path.join(profile_dir, name)
        if os.path.isdir(path_value):
            shutil.rmtree(path_value, ignore_errors=True)
            removed.append(path_value)
    return removed


def html_message_box(title_text, body_lines, accent='#22c55e'):
    parts = []
    parts.append('<div style="padding:12px;border:1px solid ' + accent + ';border-radius:14px;background:#0f172a;color:#e2e8f0;">')
    parts.append('<div style="font-weight:700;color:' + accent + ';margin-bottom:6px;">' + html.escape(title_text) + '</div>')
    for line in body_lines:
        parts.append('<div style="margin-top:4px;">' + html.escape(line) + '</div>')
    parts.append('</div>')
    return ''.join(parts)


def list_download_files_html(downloads_dir, limit_count=60):
    items = []
    if not os.path.isdir(downloads_dir):
        return html_message_box('Downloads', ['No downloads directory yet.'], '#38bdf8')

    paths = []
    for name in os.listdir(downloads_dir):
        full_path = os.path.join(downloads_dir, name)
        try:
            stat_info = os.stat(full_path)
            paths.append((stat_info.st_mtime, name, stat_info.st_size))
        except Exception:
            continue

    paths.sort(reverse=True)
    if not paths:
        return html_message_box('Downloads', ['No files downloaded yet.', downloads_dir], '#38bdf8')

    items.append('<div style="padding:12px;border:1px solid #334155;border-radius:14px;background:#020617;color:#e2e8f0;">')
    items.append('<div style="font-weight:700;color:#38bdf8;margin-bottom:8px;">Saved downloads</div>')
    items.append('<div style="font-size:12px;color:#94a3b8;margin-bottom:8px;">' + html.escape(downloads_dir) + '</div>')
    items.append('<ul style="margin:0;padding-left:18px;">')
    shown = 0
    for _, name, size_value in paths:
        shown += 1
        if shown > limit_count:
            break
        size_mb = '{:.2f}'.format(float(size_value) / (1024.0 * 1024.0))
        items.append('<li style="margin:4px 0;">' + html.escape(name) + ' <span style="color:#94a3b8;">(' + size_mb + ' MB)</span></li>')
    items.append('</ul></div>')
    return ''.join(items)


def github_headers(token_value):
    return {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token_value.strip(),
        'X-GitHub-Api-Version': '2022-11-28',
    }


def github_get_user(requests_module, token_value):
    return requests_module.get('https://api.github.com/user', headers=github_headers(token_value), timeout=60)


def github_get_repo(requests_module, token_value, owner_value, repo_value):
    url_value = 'https://api.github.com/repos/' + owner_value + '/' + repo_value
    return requests_module.get(url_value, headers=github_headers(token_value), timeout=60)


def github_validate_token(requests_module, token_value):
    response = github_get_user(requests_module, token_value)
    if response.status_code != 200:
        raise RuntimeError('GitHub token invalid or missing required scopes')
    data = response.json()
    login_value = str(data.get('login') or '')
    name_value = str(data.get('name') or '')
    return {
        'login': login_value,
        'name': name_value,
        'id': str(data.get('id') or ''),
    }


def github_check_repo_access(requests_module, token_value, owner_value, repo_value):
    response = github_get_repo(requests_module, token_value, owner_value, repo_value)
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
        'permissions': permissions,
    }


def github_upsert_file(requests_module, token_value, owner_value, repo_value, branch_value, path_value, content_text, commit_message):
    api_url = 'https://api.github.com/repos/' + owner_value + '/' + repo_value + '/contents/' + path_value
    headers = github_headers(token_value)
    sha_value = None
    get_response = requests_module.get(api_url, headers=headers, params={'ref': branch_value}, timeout=60)
    if get_response.status_code == 200:
        sha_value = get_response.json().get('sha')
    elif get_response.status_code != 404:
        get_response.raise_for_status()
    payload = {
        'message': commit_message,
        'content': base64.b64encode(content_text.encode('utf-8')).decode('ascii'),
        'branch': branch_value,
    }
    if sha_value:
        payload['sha'] = sha_value
    put_response = requests_module.put(api_url, headers=headers, json=payload, timeout=60)
    put_response.raise_for_status()
    return put_response.json()


def github_upsert_many(requests_module, token_value, owner_value, repo_value, branch_value, files_map, commit_prefix):
    results = []
    for path_value, content_text in files_map.items():
        results.append(
            github_upsert_file(
                requests_module,
                token_value,
                owner_value,
                repo_value,
                branch_value,
                path_value,
                content_text,
                commit_prefix + ' · ' + path_value,
            )
        )
    return results


def build_readme_text(owner_value, repo_value, branch_value, prefix_value):
    prefix_clean = prefix_value.strip('/')
    if prefix_clean:
        prefix_clean = prefix_clean + '/'
    lines = [
        '# Browser Controller Bundle',
        '',
        'This repo stores the production Kaggle browser controller bundle.',
        '',
        'Recommended launcher target files:',
        '',
        '- ' + prefix_clean + 'browser_controller_main.py',
        '- ' + prefix_clean + 'browser_controller_support.py',
        '',
        'Repo: https://github.com/' + owner_value + '/' + repo_value + '/tree/' + branch_value,
        '',
        'The launcher should fetch the raw Python files directly instead of parsing README code blocks.',
    ]
    return '\n'.join(lines).rstrip() + '\n'


# ===== browser_controller_main.py =====
# See the dedicated browser_controller_main.py panel/file in the website for the runnable main module.
# This combined file is informational only.
