import os
import re
import io
import json
import html
import time
import base64
import shlex
import shutil
import zipfile
import tempfile
import subprocess
from urllib.parse import quote_plus, quote

try:
    import requests
except Exception:
    requests = None

try:
    from PIL import Image
except Exception:
    Image = None

DISPLAY_VALUE = ':99'
SCREEN_W = 1440
SCREEN_H = 900
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
    captures_dir = os.path.join(root, 'captures')
    logs_dir = os.path.join(root, 'logs')
    desktop_dir = os.path.join(root, 'desktop-home')
    state_json = os.path.join(root, 'state.json')

    for path_value in [
        root,
        runtime_dir,
        profile_dir,
        downloads_dir,
        bundle_dir,
        captures_dir,
        logs_dir,
        desktop_dir,
    ]:
        os.makedirs(path_value, exist_ok=True)

    os.environ['DISPLAY'] = DISPLAY_VALUE
    os.environ['XDG_RUNTIME_DIR'] = runtime_dir

    return {
        'root': root,
        'runtime_dir': runtime_dir,
        'profile_dir': profile_dir,
        'downloads_dir': downloads_dir,
        'bundle_dir': bundle_dir,
        'captures_dir': captures_dir,
        'logs_dir': logs_dir,
        'desktop_dir': desktop_dir,
        'state_json': state_json,
        'persistent': root.startswith('/kaggle/working/'),
    }


def display_env(extra_env=None):
    env = dict(os.environ)
    env['DISPLAY'] = DISPLAY_VALUE
    env.setdefault('XDG_RUNTIME_DIR', ensure_state_dirs()['runtime_dir'])
    if extra_env:
        env.update(extra_env)
    return env


def file_read_text(path_value, default=''):
    try:
        with open(path_value, 'r', encoding='utf-8') as handle:
            return handle.read()
    except Exception:
        return default


def file_write_text(path_value, text_value):
    parent = os.path.dirname(path_value)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path_value, 'w', encoding='utf-8') as handle:
        handle.write(text_value)
    return path_value


def load_json(path_value, default=None):
    if default is None:
        default = {}
    try:
        with open(path_value, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        return default


def save_json(path_value, data_value):
    file_write_text(path_value, json.dumps(data_value, indent=2, ensure_ascii=False))
    return path_value


def append_log(log_name, text_value):
    state = ensure_state_dirs()
    log_path = os.path.join(state['logs_dir'], log_name)
    with open(log_path, 'a', encoding='utf-8') as handle:
        handle.write('[' + now_text() + '] ' + str(text_value).rstrip() + '\n')
    return log_path


def run_list(args, timeout=120, check=False, env=None, cwd=None, input_text=None):
    try:
        completed = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=display_env(env),
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError as exc:
        result = {
            'cmd': list(args),
            'returncode': 127,
            'stdout': '',
            'stderr': str(exc),
            'ok': False,
        }
        if check:
            raise RuntimeError(result['stderr'])
        return result
    except Exception as exc:
        result = {
            'cmd': list(args),
            'returncode': 1,
            'stdout': '',
            'stderr': str(exc),
            'ok': False,
        }
        if check:
            raise RuntimeError(result['stderr'])
        return result

    result = {
        'cmd': list(args),
        'returncode': completed.returncode,
        'stdout': completed.stdout,
        'stderr': completed.stderr,
        'ok': completed.returncode == 0,
    }
    if check and completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or 'Command failed').strip())
    return result


def run_shell(command_text, timeout=120, check=False, env=None, cwd=None):
    try:
        completed = subprocess.run(
            command_text,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=display_env(env),
            cwd=cwd,
            check=False,
        )
    except Exception as exc:
        result = {
            'cmd': command_text,
            'returncode': 1,
            'stdout': '',
            'stderr': str(exc),
            'ok': False,
        }
        if check:
            raise RuntimeError(result['stderr'])
        return result

    result = {
        'cmd': command_text,
        'returncode': completed.returncode,
        'stdout': completed.stdout,
        'stderr': completed.stderr,
        'ok': completed.returncode == 0,
    }
    if check and completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or 'Command failed').strip())
    return result


def run_background(command_value, log_name='process.log', env=None, cwd=None, shell=False):
    state = ensure_state_dirs()
    log_path = os.path.join(state['logs_dir'], log_name)
    log_handle = open(log_path, 'a', encoding='utf-8')
    proc = subprocess.Popen(
        command_value,
        shell=shell,
        cwd=cwd,
        env=display_env(env),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    proc._browser_controller_log_handle = log_handle
    return proc


def available_command(candidates):
    for item in candidates:
        resolved = shutil.which(item)
        if resolved:
            return resolved
    return None


def detect_cpu_info():
    cpu_model = ''
    cpu_count = os.cpu_count() or 0
    memory_gb = 0.0

    try:
        cpuinfo_text = file_read_text('/proc/cpuinfo', '')
        match = re.search(r'^model name\s*:\s*(.+)$', cpuinfo_text, re.MULTILINE)
        if match:
            cpu_model = match.group(1).strip()
    except Exception:
        cpu_model = ''

    try:
        meminfo_text = file_read_text('/proc/meminfo', '')
        match = re.search(r'^MemTotal:\s*(\d+)\s+kB$', meminfo_text, re.MULTILINE)
        if match:
            memory_gb = round(int(match.group(1)) / 1024.0 / 1024.0, 2)
    except Exception:
        memory_gb = 0.0

    return {
        'cpu_model': cpu_model or 'Unknown CPU',
        'cpu_count': cpu_count,
        'memory_gb': memory_gb,
    }


def find_browser_binary():
    return available_command([
        'google-chrome',
        'google-chrome-stable',
        'chromium-browser',
        'chromium',
    ])


def profile_has_previous_session(profile_dir=None):
    state = ensure_state_dirs()
    profile_dir = profile_dir or state['profile_dir']
    return os.path.isdir(profile_dir) and any(os.scandir(profile_dir))


def prune_profile(profile_dir=None):
    state = ensure_state_dirs()
    profile_dir = profile_dir or state['profile_dir']
    removable = [
        'Default/Cache',
        'Default/Code Cache',
        'Default/GPUCache',
        'Default/Service Worker/CacheStorage',
        'GrShaderCache',
        'ShaderCache',
        'Crashpad',
    ]
    removed = []
    for relative_path in removable:
        full_path = os.path.join(profile_dir, relative_path)
        if os.path.exists(full_path):
            shutil.rmtree(full_path, ignore_errors=True)
            removed.append(relative_path)
    return removed


def prepare_browser_profile(state=None):
    state = state or ensure_state_dirs()
    default_dir = os.path.join(state['profile_dir'], 'Default')
    os.makedirs(default_dir, exist_ok=True)
    preferences_path = os.path.join(default_dir, 'Preferences')
    preferences = load_json(preferences_path, {})

    preferences.setdefault('download', {})
    preferences['download']['default_directory'] = state['downloads_dir']
    preferences['download']['prompt_for_download'] = False
    preferences['download']['directory_upgrade'] = True
    preferences.setdefault('profile', {})
    preferences['profile']['default_content_setting_values'] = preferences['profile'].get('default_content_setting_values', {})
    preferences['profile']['default_content_setting_values']['notifications'] = 2
    preferences.setdefault('browser', {})
    preferences['browser']['check_default_browser'] = False

    save_json(preferences_path, preferences)
    return preferences_path


def is_display_live():
    result = run_list(['xdpyinfo', '-display', DISPLAY_VALUE], timeout=10)
    return result['returncode'] == 0


def ensure_xvfb_running(state=None, width=None, height=None):
    state = state or ensure_state_dirs()
    width = width or SCREEN_W
    height = height or SCREEN_H

    if is_display_live():
        return {'ok': True, 'started': False, 'message': 'Xvfb already running on ' + DISPLAY_VALUE}

    proc = run_background(
        ['Xvfb', DISPLAY_VALUE, '-screen', '0', str(width) + 'x' + str(height) + 'x24', '-ac', '+extension', 'RANDR'],
        log_name='xvfb.log',
    )
    for _ in range(30):
        time.sleep(0.25)
        if is_display_live():
            append_log('xvfb.log', 'Xvfb ready on ' + DISPLAY_VALUE + ' pid=' + str(proc.pid))
            return {'ok': True, 'started': True, 'pid': proc.pid, 'message': 'Started Xvfb on ' + DISPLAY_VALUE}

    return {'ok': False, 'started': True, 'pid': proc.pid, 'message': 'Xvfb did not become ready'}


def set_root_background(color='#0f172a'):
    return run_list(['xsetroot', '-solid', color], timeout=10)


def start_window_manager(state=None):
    state = state or ensure_state_dirs()
    binary = available_command(['openbox', 'fluxbox'])
    if not binary:
        return None
    return run_background([binary], log_name='window-manager.log')


def launch_terminal(state=None, command_text=''):
    state = state or ensure_state_dirs()
    terminal = available_command(['xterm'])
    if not terminal:
        return None

    args = [terminal, '-fa', 'Monospace', '-fs', '11', '-geometry', '120x32+40+40']
    if command_text:
        args += ['-e', 'bash', '-lc', command_text]
    return run_background(args, log_name='terminal.log')


def launch_file_manager(state=None, path_value=''):
    state = state or ensure_state_dirs()
    path_value = path_value or state['downloads_dir']
    binary = available_command(['pcmanfm', 'thunar', 'nautilus', 'xdg-open'])
    if not binary:
        return None

    name = os.path.basename(binary)
    if name == 'pcmanfm':
        args = [binary, path_value]
    elif name == 'thunar':
        args = [binary, path_value]
    elif name == 'nautilus':
        args = [binary, path_value]
    else:
        args = [binary, path_value]
    return run_background(args, log_name='file-manager.log')


def ensure_desktop_session(state=None):
    state = state or ensure_state_dirs()
    result = ensure_xvfb_running(state)
    set_root_background('#111827')
    messages = [result['message']]

    wm_proc = start_window_manager(state)
    if wm_proc:
        messages.append('Window manager pid=' + str(wm_proc.pid))
    else:
        messages.append('No window manager package found')

    desktop_proc = None
    desktop_binary = available_command(['pcmanfm'])
    if desktop_binary:
        desktop_proc = run_background([desktop_binary, '--desktop', '--profile', 'browser-controller'], log_name='desktop.log')
        messages.append('Desktop surface pid=' + str(desktop_proc.pid))

    terminal_proc = launch_terminal(state)
    if terminal_proc:
        messages.append('Terminal pid=' + str(terminal_proc.pid))

    file_manager_proc = launch_file_manager(state, state['downloads_dir'])
    if file_manager_proc:
        messages.append('Downloads window pid=' + str(file_manager_proc.pid))

    append_log('session.log', ' | '.join(messages))
    return {'ok': True, 'message': ' | '.join(messages)}


def launch_browser(state=None, url_value=None):
    state = state or ensure_state_dirs()
    url_value = (url_value or URL_GOOGLE).strip() or URL_GOOGLE
    browser_binary = find_browser_binary()
    if not browser_binary:
        raise RuntimeError('No Chrome or Chromium browser binary was found')

    prepare_browser_profile(state)
    args = [
        browser_binary,
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-features=TranslateUI',
        '--disable-notifications',
        '--window-position=0,0',
        '--window-size=' + str(SCREEN_W) + ',' + str(SCREEN_H),
        '--user-data-dir=' + state['profile_dir'],
        '--new-window',
        url_value,
    ]
    proc = run_background(args, log_name='browser.log')
    append_log('browser.log', 'Opened ' + url_value + ' pid=' + str(proc.pid))
    return proc


def xdotool(args):
    return run_list(['xdotool'] + list(args), timeout=20)


def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, int(value)))


def move_mouse(x_value, y_value):
    x_value = clamp(x_value, 0, SCREEN_W - 1)
    y_value = clamp(y_value, 0, SCREEN_H - 1)
    return xdotool(['mousemove', str(x_value), str(y_value)])


def mouse_down(button=1):
    return xdotool(['mousedown', str(button)])


def mouse_up(button=1):
    return xdotool(['mouseup', str(button)])


def click(button=1, repeat=1, delay_ms=100):
    return xdotool(['click', '--repeat', str(repeat), '--delay', str(delay_ms), str(button)])


def scroll_vertical(steps):
    steps = int(steps)
    if steps == 0:
        return {'ok': True, 'returncode': 0, 'stdout': '', 'stderr': ''}
    button = '5' if steps > 0 else '4'
    return xdotool(['click', '--repeat', str(abs(steps)), button])


def send_key(key_sequence):
    return xdotool(['key', '--clearmodifiers', key_sequence])


def type_text(text_value, delay_ms=12):
    fd, temp_path = tempfile.mkstemp(prefix='browser-controller-type-', suffix='.txt')
    os.close(fd)
    try:
        file_write_text(temp_path, text_value)
        return xdotool(['type', '--clearmodifiers', '--delay', str(delay_ms), '--file', temp_path])
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def get_active_window_title():
    window_result = xdotool(['getactivewindow'])
    if window_result['returncode'] != 0:
        return ''
    window_id = (window_result['stdout'] or '').strip()
    if not window_id:
        return ''
    title_result = xdotool(['getwindowname', window_id])
    return (title_result['stdout'] or '').strip()


def get_clipboard_text():
    commands = [
        ['xclip', '-selection', 'clipboard', '-out'],
        ['xclip', '-selection', 'primary', '-out'],
        ['xsel', '--clipboard', '--output'],
        ['xsel', '--primary', '--output'],
    ]
    for command_value in commands:
        result = run_list(command_value, timeout=10)
        if result['returncode'] == 0 and result['stdout']:
            return result['stdout']
    return ''


def _pipe_text(command_value, text_value):
    try:
        proc = subprocess.Popen(
            command_value,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=display_env(),
        )
        proc.communicate(text_value, timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


def set_clipboard_text(text_value):
    ok = False
    ok = _pipe_text(['xclip', '-selection', 'clipboard', '-in'], text_value) or ok
    ok = _pipe_text(['xclip', '-selection', 'primary', '-in'], text_value) or ok
    ok = _pipe_text(['xsel', '--clipboard', '--input'], text_value) or ok
    ok = _pipe_text(['xsel', '--primary', '--input'], text_value) or ok
    if not ok:
        state = ensure_state_dirs()
        file_write_text(os.path.join(state['root'], 'clipboard-fallback.txt'), text_value)
    return ok


def smart_paste_text(text_value, terminal_mode=False):
    set_clipboard_text(text_value)
    if terminal_mode:
        first = send_key('ctrl+shift+v')
        second = send_key('Shift+Insert')
        return first if first['returncode'] == 0 else second
    return send_key('ctrl+v')


def capture_screen_bytes(state=None, max_width=1280):
    state = state or ensure_state_dirs()
    os.makedirs(state['captures_dir'], exist_ok=True)
    temp_path = os.path.join(state['captures_dir'], 'current-screen.png')
    result = run_list(['scrot', '-z', temp_path], timeout=30)
    if result['returncode'] != 0 or not os.path.exists(temp_path):
        raise RuntimeError((result['stderr'] or result['stdout'] or 'Screenshot capture failed').strip())

    with open(temp_path, 'rb') as handle:
        data_value = handle.read()

    if Image is not None and max_width:
        image = Image.open(io.BytesIO(data_value))
        try:
            if image.width > max_width:
                ratio = float(max_width) / float(image.width)
                resized = image.resize((max_width, max(1, int(image.height * ratio))))
                buffer = io.BytesIO()
                resized.save(buffer, format='PNG')
                data_value = buffer.getvalue()
        finally:
            image.close()

    return data_value


def human_size(size_value):
    size_value = float(size_value)
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    index = 0
    while size_value >= 1024.0 and index < len(units) - 1:
        size_value /= 1024.0
        index += 1
    if index == 0:
        return str(int(size_value)) + ' ' + units[index]
    return ('%.2f' % size_value).rstrip('0').rstrip('.') + ' ' + units[index]


def list_download_files(state=None, limit=100):
    state = state or ensure_state_dirs()
    items = []
    for root_value, _, file_names in os.walk(state['downloads_dir']):
        for file_name in file_names:
            full_path = os.path.join(root_value, file_name)
            try:
                stat_value = os.stat(full_path)
            except Exception:
                continue
            items.append({
                'path': full_path,
                'name': os.path.relpath(full_path, state['downloads_dir']),
                'size': stat_value.st_size,
                'mtime': stat_value.st_mtime,
            })
    items.sort(key=lambda item: item['mtime'], reverse=True)
    return items[:limit]


def list_download_files_html(state=None, limit=50):
    state = state or ensure_state_dirs()
    files = list_download_files(state, limit=limit)
    if not files:
        return html_message_box('info', 'Downloads', 'No files are in the managed downloads folder yet.')

    rows = []
    for item in files:
        rows.append(
            '<tr>'
            '<td style="padding:6px 8px;border-bottom:1px solid #1f2937;">' + html.escape(item['name']) + '</td>'
            '<td style="padding:6px 8px;border-bottom:1px solid #1f2937;white-space:nowrap;">' + human_size(item['size']) + '</td>'
            '<td style="padding:6px 8px;border-bottom:1px solid #1f2937;white-space:nowrap;">' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['mtime'])) + '</td>'
            '</tr>'
        )

    return (
        '<div style="border:1px solid #1f2937;border-radius:16px;overflow:hidden;background:#020617;color:#e2e8f0;">'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<thead><tr style="background:#0f172a;text-align:left;">'
        '<th style="padding:8px;">File</th><th style="padding:8px;">Size</th><th style="padding:8px;">Updated</th>'
        '</tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table></div>'
    )


def zip_downloads(state=None, zip_name='downloads_bundle.zip'):
    state = state or ensure_state_dirs()
    zip_path = os.path.join(state['root'], zip_name)
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in list_download_files(state, limit=10000):
            archive.write(item['path'], arcname=item['name'])
    return zip_path


def _guess_filename_from_url(url_value):
    cleaned = (url_value or '').split('?')[0].rstrip('/')
    if '/' in cleaned:
        cleaned = cleaned.rsplit('/', 1)[-1]
    cleaned = cleaned.strip()
    if not cleaned:
        cleaned = 'downloaded_file'
    return cleaned


def download_file(url_value, state=None, filename=''):
    if not requests:
        raise RuntimeError('requests is not available in this environment')

    state = state or ensure_state_dirs()
    url_value = (url_value or '').strip()
    if not url_value:
        raise RuntimeError('A download URL is required')

    filename = (filename or '').strip() or _guess_filename_from_url(url_value)
    output_path = os.path.join(state['downloads_dir'], filename)
    response = requests.get(url_value, stream=True, timeout=120, allow_redirects=True)
    response.raise_for_status()

    with open(output_path, 'wb') as handle:
        for chunk in response.iter_content(chunk_size=1024 * 512):
            if chunk:
                handle.write(chunk)

    append_log('downloads.log', 'Downloaded ' + url_value + ' -> ' + output_path)
    return output_path


def resolve_run_path(path_value, state=None):
    state = state or ensure_state_dirs()
    path_value = (path_value or '').strip()
    if not path_value:
        raise RuntimeError('A file path is required')
    if os.path.isabs(path_value):
        return path_value
    candidate = os.path.join(state['downloads_dir'], path_value)
    if os.path.exists(candidate):
        return candidate
    return os.path.abspath(path_value)


def make_executable(path_value):
    current_mode = os.stat(path_value).st_mode
    os.chmod(path_value, current_mode | 0o111)
    return path_value


def extract_archive(path_value, state=None):
    state = state or ensure_state_dirs()
    path_value = resolve_run_path(path_value, state)
    extract_dir = os.path.join(state['downloads_dir'], os.path.basename(path_value) + '_extracted')
    os.makedirs(extract_dir, exist_ok=True)

    if zipfile.is_zipfile(path_value):
        with zipfile.ZipFile(path_value, 'r') as archive:
            archive.extractall(extract_dir)
        return extract_dir

    result = run_shell(
        'set -e; cd ' + shlex.quote(extract_dir) + ' && '
        + 'tar -xf ' + shlex.quote(path_value) + ' >/dev/null 2>&1 || '
        + '7z x -y ' + shlex.quote(path_value) + ' >/dev/null 2>&1 || '
        + 'unzip -o ' + shlex.quote(path_value) + ' >/dev/null 2>&1',
        timeout=240,
    )
    if result['returncode'] != 0:
        raise RuntimeError('Could not extract archive: ' + path_value)
    return extract_dir


def run_downloaded_file(path_value, state=None, args_text=''):
    state = state or ensure_state_dirs()
    path_value = resolve_run_path(path_value, state)
    args_text = (args_text or '').strip()

    if not os.path.exists(path_value):
        raise RuntimeError('File does not exist: ' + path_value)

    if os.path.isdir(path_value):
        proc = launch_file_manager(state, path_value)
        if not proc:
            raise RuntimeError('No file manager was available')
        return proc

    lower_path = path_value.lower()
    if lower_path.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.tar.xz', '.7z')):
        extract_dir = extract_archive(path_value, state)
        proc = launch_file_manager(state, extract_dir)
        if proc:
            return proc
        raise RuntimeError('Archive extracted to ' + extract_dir)

    if lower_path.endswith('.appimage') or lower_path.endswith('.sh') or os.access(path_value, os.X_OK):
        make_executable(path_value)
        command_text = 'cd ' + shlex.quote(os.path.dirname(path_value) or state['downloads_dir']) + ' && ' + shlex.quote(path_value)
        if args_text:
            command_text += ' ' + args_text
        return run_background(['bash', '-lc', command_text], log_name='app-run.log')

    opener = available_command(['xdg-open'])
    if opener:
        return run_background([opener, path_value], log_name='app-open.log')

    raise RuntimeError('No opener was available for: ' + path_value)


def html_message_box(kind, title_text, body_text):
    tone_map = {
        'info': ('#38bdf8', '#0f172a'),
        'success': ('#34d399', '#052e16'),
        'warning': ('#f59e0b', '#451a03'),
        'error': ('#fb7185', '#4c0519'),
    }
    border, background = tone_map.get(kind, tone_map['info'])
    return (
        '<div style="border:1px solid ' + border + ';background:' + background + ';padding:14px 16px;border-radius:16px;color:#e5e7eb;">'
        '<div style="font-weight:700;margin-bottom:6px;">' + html.escape(title_text) + '</div>'
        '<div style="font-size:13px;line-height:1.55;">' + body_text + '</div>'
        '</div>'
    )


def build_github_contents_url(owner_value, repo_value, path_value):
    encoded_path = '/'.join(quote(segment, safe='') for segment in path_value.split('/'))
    return 'https://api.github.com/repos/' + owner_value + '/' + repo_value + '/contents/' + encoded_path


def github_request(token_value, method_value, url_value, json_body=None):
    if not requests:
        raise RuntimeError('requests is not available in this environment')

    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token_value,
        'X-GitHub-Api-Version': '2022-11-28',
    }
    response = requests.request(method_value, url_value, headers=headers, json=json_body, timeout=120)
    if response.status_code >= 400:
        message = response.text
        try:
            payload = response.json()
            if isinstance(payload, dict) and payload.get('message'):
                message = payload.get('message')
        except Exception:
            pass
        error = RuntimeError(message)
        error.status = response.status_code
        raise error
    if response.text.strip():
        return response.json()
    return {}


def github_validate_token(token_value):
    return github_request(token_value, 'GET', 'https://api.github.com/user')


def github_check_repo_access(token_value, owner_value, repo_value):
    return github_request(token_value, 'GET', 'https://api.github.com/repos/' + owner_value + '/' + repo_value)


def github_get_existing_sha(token_value, owner_value, repo_value, branch_value, path_value):
    url_value = build_github_contents_url(owner_value, repo_value, path_value) + '?ref=' + quote(branch_value, safe='')
    try:
        response = github_request(token_value, 'GET', url_value)
        return response.get('sha')
    except Exception as exc:
        if getattr(exc, 'status', None) == 404:
            return None
        raise


def github_upsert_file(token_value, owner_value, repo_value, branch_value, path_value, content_value, message_value=None):
    sha_value = github_get_existing_sha(token_value, owner_value, repo_value, branch_value, path_value)
    body = {
        'message': message_value or ('Update ' + path_value + ' from Kaggle desktop controller'),
        'content': base64.b64encode(content_value.encode('utf-8')).decode('ascii'),
        'branch': branch_value,
    }
    if sha_value:
        body['sha'] = sha_value
    return github_request(token_value, 'PUT', build_github_contents_url(owner_value, repo_value, path_value), json_body=body)


def github_upsert_many(token_value, owner_value, repo_value, branch_value, files_map, message_prefix='Update'):
    results = []
    for path_value, content_value in files_map.items():
        response = github_upsert_file(
            token_value,
            owner_value,
            repo_value,
            branch_value,
            path_value,
            content_value,
            message_value=message_prefix + ' ' + path_value,
        )
        results.append({'path': path_value, 'response': response})
    return results
