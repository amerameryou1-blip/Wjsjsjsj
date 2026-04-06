SUPPORT = globals().get('__browser_support__', {})
if not SUPPORT:
    raise RuntimeError('Support module not loaded by launcher')

import os
import time
import html
import json
import shutil
import threading
import subprocess
from io import BytesIO

import requests
import ipywidgets as widgets
from PIL import Image, ImageDraw
from IPython.display import display, HTML
from xvfbwrapper import Xvfb

try:
    from ipyevents import Event
except Exception:
    Event = None

DISPLAY_VALUE = SUPPORT['DISPLAY_VALUE']
SCREEN_W = SUPPORT['SCREEN_W']
SCREEN_H = SUPPORT['SCREEN_H']
URL_GOOGLE = SUPPORT['URL_GOOGLE']
URL_GOOGLE_LOGIN = SUPPORT['URL_GOOGLE_LOGIN']
URL_KAGGLE_CPU_SEARCH = SUPPORT['URL_KAGGLE_CPU_SEARCH']
URL_CODEX_WEB = SUPPORT['URL_CODEX_WEB']
URL_CODEX_APP = SUPPORT['URL_CODEX_APP']
URL_CODEX_CLI_RELEASES = SUPPORT['URL_CODEX_CLI_RELEASES']
URL_ANTIGRAVITY_APP = SUPPORT['URL_ANTIGRAVITY_APP']
DEFAULT_OWNER = SUPPORT['DEFAULT_OWNER']
DEFAULT_REPO = SUPPORT['DEFAULT_REPO']
DEFAULT_BRANCH = SUPPORT['DEFAULT_BRANCH']
DEFAULT_PREFIX = SUPPORT['DEFAULT_PREFIX']
DEFAULT_MAIN_PATH = SUPPORT['DEFAULT_MAIN_PATH']
DEFAULT_SUPPORT_PATH = SUPPORT['DEFAULT_SUPPORT_PATH']
DEFAULT_README_PATH = SUPPORT['DEFAULT_README_PATH']

ensure_state_dirs = SUPPORT['ensure_state_dirs']
run_shell = SUPPORT['run_shell']
run_list = SUPPORT['run_list']
find_browser_binary = SUPPORT['find_browser_binary']
file_read_text = SUPPORT['file_read_text']
file_write_text = SUPPORT['file_write_text']
load_json = SUPPORT['load_json']
save_json = SUPPORT['save_json']
detect_cpu_info = SUPPORT['detect_cpu_info']
profile_has_previous_session = SUPPORT['profile_has_previous_session']
prune_profile = SUPPORT['prune_profile']
html_message_box = SUPPORT['html_message_box']
list_download_files_html = SUPPORT['list_download_files_html']
github_validate_token = SUPPORT['github_validate_token']
github_check_repo_access = SUPPORT['github_check_repo_access']
github_upsert_file = SUPPORT['github_upsert_file']
github_upsert_many = SUPPORT['github_upsert_many']
build_readme_text = SUPPORT['build_readme_text']
now_text = SUPPORT['now_text']

STATE = ensure_state_dirs()
FRAME_PATH = os.path.join(STATE['root'], 'frame.png')
LOG_PATH = os.path.join(STATE['logs_dir'], 'runtime.log')
FRAME_COUNT = 0
LAST_ACTION = 'Ready'
SHOT_INTERVAL = 2
SHOT_WIDTH = 1120
SHOT_JPEG_QUALITY = 72
CURSOR_X = SCREEN_W // 2
CURSOR_Y = SCREEN_H // 2
CURSOR_STEP = 40
STOP_EVENT = threading.Event()
XVFB_HANDLE = None
BROWSER_PROCESS = None
SCREENSHOT_THREAD = None
HEARTBEAT_THREAD = None
BROWSER_BIN = None
IMAGE_EVENT = None

img = None
status = None
heartbeat = None
url = None
type_txt = None
info_html = None
downloads_html = None
state_html = None
github_status_html = None
github_token = None
github_owner = None
github_repo = None
github_branch = None
github_prefix = None
github_mode = None
github_commit_message = None


def log_line(text_value):
    line = '[' + now_text() + '] ' + text_value
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    except Exception:
        pass


def status_text():
    return 'Frame #' + str(FRAME_COUNT) + ' - ' + LAST_ACTION + ' · Cursor ' + str(CURSOR_X) + ',' + str(CURSOR_Y)


def set_status(text_value):
    global LAST_ACTION
    LAST_ACTION = text_value
    if status is not None:
        status.value = status_text()
    log_line(text_value)


def set_github_status(title_text, lines, accent='#f59e0b'):
    if github_status_html is not None:
        github_status_html.value = html_message_box(title_text, lines, accent)


def xdotool(command_text):
    return run_shell('xdotool ' + command_text)


def xkey(key_text):
    xdotool('key ' + key_text)


def xtype(text_value):
    safe_text = text_value.replace('\\', '\\\\').replace('"', '\\"')
    run_shell('xdotool type --delay 1 -- "' + safe_text + '"')


def xmove(x_value, y_value):
    global CURSOR_X, CURSOR_Y
    CURSOR_X = max(0, min(SCREEN_W - 1, int(x_value)))
    CURSOR_Y = max(0, min(SCREEN_H - 1, int(y_value)))
    xdotool('mousemove ' + str(CURSOR_X) + ' ' + str(CURSOR_Y))


def xclick(button_number):
    xdotool('click ' + str(int(button_number)))


def move_cursor_by(dx_value, dy_value, label_text):
    xmove(CURSOR_X + dx_value, CURSOR_Y + dy_value)
    set_status(label_text)


def act_move_left(_=None):
    move_cursor_by(-CURSOR_STEP, 0, 'Cursor left')


def act_move_right(_=None):
    move_cursor_by(CURSOR_STEP, 0, 'Cursor right')


def act_move_up(_=None):
    move_cursor_by(0, -CURSOR_STEP, 'Cursor up')


def act_move_down(_=None):
    move_cursor_by(0, CURSOR_STEP, 'Cursor down')


def act_click_cursor(_=None):
    xmove(CURSOR_X, CURSOR_Y)
    time.sleep(0.03)
    xclick(1)
    set_status('Cursor click')


def act_rclick_cursor(_=None):
    xmove(CURSOR_X, CURSOR_Y)
    time.sleep(0.03)
    xclick(3)
    set_status('Cursor right click')


def act_center_cursor(_=None):
    xmove(SCREEN_W // 2, SCREEN_H // 2)
    set_status('Cursor centered')


def browser_go(target_url):
    xkey('ctrl+l')
    time.sleep(0.15)
    xtype(target_url)
    time.sleep(0.1)
    xkey('Return')


def browser_new_tab(target_url):
    xkey('ctrl+l')
    time.sleep(0.15)
    xtype(target_url)
    time.sleep(0.1)
    xkey('alt+Return')
    time.sleep(0.25)
    xkey('ctrl+9')


def act_go(_=None):
    target = url.value.strip() or URL_GOOGLE
    browser_go(target)
    set_status('Go to ' + target)


def act_back(_=None):
    xkey('Alt+Left')
    set_status('Back')


def act_fwd(_=None):
    xkey('Alt+Right')
    set_status('Forward')


def act_reload(_=None):
    xkey('F5')
    set_status('Reload')


def act_home(_=None):
    browser_go(URL_GOOGLE)
    set_status('Home')


def act_enter(_=None):
    xkey('Return')
    set_status('Enter')


def act_esc(_=None):
    xkey('Escape')
    set_status('Esc')


def act_tab(_=None):
    xkey('Tab')
    set_status('Tab')


def act_up(_=None):
    xkey('Up')
    set_status('Up')


def act_down(_=None):
    xkey('Down')
    set_status('Down')


def act_pgup(_=None):
    xkey('Page_Up')
    set_status('Page Up')


def act_pgdn(_=None):
    xkey('Page_Down')
    set_status('Page Down')


def act_copy(_=None):
    xkey('ctrl+c')
    set_status('Copy')


def act_paste(_=None):
    xkey('ctrl+v')
    set_status('Paste')


def act_sel_all(_=None):
    xkey('ctrl+a')
    set_status('Select all')


def act_right_click(_=None):
    xclick(3)
    set_status('Right click')


def act_scroll_up(_=None):
    xclick(4)
    set_status('Scroll up')


def act_scroll_down(_=None):
    xclick(5)
    set_status('Scroll down')


def act_zoom_in(_=None):
    xkey('ctrl+plus')
    set_status('Zoom in')


def act_zoom_out(_=None):
    xkey('ctrl+minus')
    set_status('Zoom out')


def act_fast(_=None):
    global SHOT_INTERVAL
    SHOT_INTERVAL = 1
    set_status('Fast mode 1s')


def act_slow(_=None):
    global SHOT_INTERVAL
    SHOT_INTERVAL = 5
    set_status('Slow mode 5s')


def act_type_submit(_=None):
    text_value = type_txt.value.strip('\n')
    if not text_value:
        set_status('Nothing to type')
        return
    xtype(text_value)
    xkey('Return')
    set_status('Typed text and pressed Enter')


def act_type_only(_=None):
    text_value = type_txt.value.strip('\n')
    if not text_value:
        set_status('Nothing to type')
        return
    xtype(text_value)
    set_status('Typed text only')


def open_google_login(_=None):
    browser_new_tab(URL_GOOGLE_LOGIN)
    set_status('Opened Google login')


def open_codex_web(_=None):
    browser_new_tab(URL_CODEX_WEB)
    set_status('Opened Codex web')


def open_codex_app_page(_=None):
    browser_new_tab(URL_CODEX_APP)
    set_status('Opened Codex app page')


def open_codex_releases(_=None):
    browser_new_tab(URL_CODEX_CLI_RELEASES)
    set_status('Opened Codex releases')


def open_antigravity_page(_=None):
    browser_new_tab(URL_ANTIGRAVITY_APP)
    set_status('Opened Antigravity download page')


def open_both_apps(_=None):
    browser_new_tab(URL_ANTIGRAVITY_APP)
    time.sleep(0.3)
    browser_new_tab(URL_CODEX_APP)
    set_status('Opened Antigravity and Codex app pages')


def open_kaggle_cpu(_=None):
    browser_new_tab(URL_KAGGLE_CPU_SEARCH)
    set_status('Opened Kaggle CPU search')


def open_chrome_downloads(_=None):
    browser_new_tab('chrome://downloads/')
    set_status('Opened browser downloads')


def refresh_downloads_panel(_=None):
    downloads_html.value = list_download_files_html(STATE['downloads_dir'])
    set_status('Refreshed downloads panel')


def prune_browser_cache(_=None):
    removed = prune_profile(STATE['profile_dir'])
    set_status('Pruned browser cache paths: ' + str(len(removed)))
    refresh_state_panel()


def clear_downloads(_=None):
    removed_count = 0
    for name in os.listdir(STATE['downloads_dir']):
        full_path = os.path.join(STATE['downloads_dir'], name)
        try:
            if os.path.isdir(full_path):
                shutil.rmtree(full_path, ignore_errors=True)
            else:
                os.remove(full_path)
            removed_count += 1
        except Exception:
            pass
    refresh_downloads_panel()
    set_status('Cleared downloads: ' + str(removed_count))


def state_payload():
    payload = load_json(STATE['state_json'], {})
    payload['last_url'] = url.value.strip() if url is not None else ''
    payload['last_action'] = LAST_ACTION
    payload['last_saved_at'] = now_text()
    payload['cursor_x'] = CURSOR_X
    payload['cursor_y'] = CURSOR_Y
    payload['github_owner'] = github_owner.value.strip() if github_owner is not None else DEFAULT_OWNER
    payload['github_repo'] = github_repo.value.strip() if github_repo is not None else DEFAULT_REPO
    payload['github_branch'] = github_branch.value.strip() if github_branch is not None else DEFAULT_BRANCH
    payload['github_prefix'] = github_prefix.value.strip() if github_prefix is not None else DEFAULT_PREFIX
    payload['github_commit_message'] = github_commit_message.value.strip() if github_commit_message is not None else 'Update browser controller bundle from Kaggle'
    return payload


def save_runtime_state(_=None):
    save_json(STATE['state_json'], state_payload())
    refresh_state_panel()
    set_status('Saved persistent state')


def load_runtime_state():
    return load_json(STATE['state_json'], {})


def refresh_state_panel():
    saved = load_runtime_state()
    lines = []
    lines.append('State root: ' + STATE['root'])
    lines.append('Persistent path: ' + ('yes' if STATE['persistent'] else 'no'))
    lines.append('Chrome profile: ' + STATE['profile_dir'])
    lines.append('Downloads: ' + STATE['downloads_dir'])
    lines.append('Previous browser session found: ' + ('yes' if profile_has_previous_session(STATE['profile_dir']) else 'no'))
    if saved.get('last_saved_at'):
        lines.append('Last saved: ' + str(saved.get('last_saved_at')))
    if saved.get('last_url'):
        lines.append('Last URL: ' + str(saved.get('last_url')))
    state_html.value = html_message_box('Session persistence', lines, '#a78bfa')


def detect_self_bundle_texts():
    bundle_paths = globals().get('__browser_bundle_paths__', {})
    main_text = ''
    support_text = ''

    if isinstance(bundle_paths, dict):
        main_path = bundle_paths.get('browser_controller_main.py')
        support_path = bundle_paths.get('browser_controller_support.py')
        if main_path and os.path.exists(main_path):
            main_text = file_read_text(main_path)
        if support_path and os.path.exists(support_path):
            support_text = file_read_text(support_path)

    if not main_text:
        raise RuntimeError('Missing main source text for upload')
    if not support_text:
        raise RuntimeError('Missing support source text for upload')
    return main_text, support_text


def github_form_values():
    return {
        'token': github_token.value.strip(),
        'owner': github_owner.value.strip() or DEFAULT_OWNER,
        'repo': github_repo.value.strip() or DEFAULT_REPO,
        'branch': github_branch.value.strip() or DEFAULT_BRANCH,
        'prefix': github_prefix.value.strip().strip('/'),
        'mode': github_mode.value,
        'commit': github_commit_message.value.strip() or 'Update browser controller bundle from Kaggle',
    }


def validate_github_access(_=None):
    values = github_form_values()
    if not values['token']:
        set_status('Paste GitHub token first')
        set_github_status('GitHub upload', ['Paste a GitHub token, then validate access.'], '#f59e0b')
        return
    try:
        user_info = github_validate_token(requests, values['token'])
        repo_info = github_check_repo_access(requests, values['token'], values['owner'], values['repo'])
        lines = [
            'Authenticated as: ' + (user_info.get('login') or 'unknown'),
            'Repo: ' + repo_info.get('full_name', values['owner'] + '/' + values['repo']),
            'Default branch: ' + repo_info.get('default_branch', ''),
            'Push permission: ' + ('yes' if repo_info.get('can_push') else 'no'),
            'Target branch: ' + values['branch'],
            'Target prefix: ' + (values['prefix'] or '(repo root)'),
        ]
        set_github_status('GitHub upload ready', lines, '#22c55e')
        set_status('GitHub token and repo access validated')
    except Exception as exc:
        set_github_status('GitHub upload failed', [str(exc)], '#ef4444')
        set_status('GitHub validation failed: ' + str(exc)[:120])


def push_bundle_to_github(_=None):
    values = github_form_values()
    if not values['token']:
        set_status('Paste GitHub token first')
        return

    try:
        main_text, support_text = detect_self_bundle_texts()
        prefix_part = values['prefix'] + '/' if values['prefix'] else ''
        files_map = {
            prefix_part + DEFAULT_MAIN_PATH: main_text,
            prefix_part + DEFAULT_SUPPORT_PATH: support_text,
        }
        if values['mode'] == 'Bundle + README':
            files_map[prefix_part + DEFAULT_README_PATH] = build_readme_text(values['owner'], values['repo'], values['branch'], values['prefix'])
        github_upsert_many(requests, values['token'], values['owner'], values['repo'], values['branch'], files_map, values['commit'])
        save_runtime_state()
        set_github_status(
            'GitHub upload complete',
            [
                'Uploaded files: ' + ', '.join(sorted(files_map.keys())),
                'Repo: ' + values['owner'] + '/' + values['repo'],
                'Branch: ' + values['branch'],
                'Commit prefix: ' + values['commit'],
            ],
            '#22c55e'
        )
        set_status('GitHub upload complete')
    except Exception as exc:
        set_github_status('GitHub upload failed', [str(exc)], '#ef4444')
        set_status('GitHub upload failed: ' + str(exc)[:120])


def capture_frame_once():
    attempts = [
        'scrot ' + FRAME_PATH + ' -o',
        'import -window root ' + FRAME_PATH,
    ]
    for command in attempts:
        run_shell(command)
        if os.path.exists(FRAME_PATH) and os.path.getsize(FRAME_PATH) > 0:
            return True
    return False


def draw_cursor_overlay(pil_img):
    draw = ImageDraw.Draw(pil_img)
    x_val = int(round((float(CURSOR_X) / float(SCREEN_W)) * pil_img.size[0]))
    y_val = int(round((float(CURSOR_Y) / float(SCREEN_H)) * pil_img.size[1]))
    x_val = max(0, min(pil_img.size[0] - 1, x_val))
    y_val = max(0, min(pil_img.size[1] - 1, y_val))

    r_outer = max(10, int(round(min(pil_img.size) * 0.02)))
    r_inner = max(4, int(round(r_outer * 0.45)))
    line_len = max(14, int(round(r_outer * 1.7)))
    line_gap = max(6, int(round(r_outer * 0.45)))
    color_main = '#00ff66'
    color_outline = '#000000'

    draw.ellipse((x_val - r_outer - 2, y_val - r_outer - 2, x_val + r_outer + 2, y_val + r_outer + 2), outline=color_outline, width=4)
    draw.ellipse((x_val - r_outer, y_val - r_outer, x_val + r_outer, y_val + r_outer), outline=color_main, width=3)
    draw.ellipse((x_val - r_inner, y_val - r_inner, x_val + r_inner, y_val + r_inner), fill=color_main, outline='white', width=1)

    draw.line((x_val - line_len, y_val, x_val - line_gap, y_val), fill=color_outline, width=5)
    draw.line((x_val + line_gap, y_val, x_val + line_len, y_val), fill=color_outline, width=5)
    draw.line((x_val, y_val - line_len, x_val, y_val - line_gap), fill=color_outline, width=5)
    draw.line((x_val, y_val + line_gap, x_val, y_val + line_len), fill=color_outline, width=5)

    draw.line((x_val - line_len, y_val, x_val - line_gap, y_val), fill=color_main, width=3)
    draw.line((x_val + line_gap, y_val, x_val + line_len, y_val), fill=color_main, width=3)
    draw.line((x_val, y_val - line_len, x_val, y_val - line_gap), fill=color_main, width=3)
    draw.line((x_val, y_val + line_gap, x_val, y_val + line_len), fill=color_main, width=3)


def refresh_frame_widget():
    if not os.path.exists(FRAME_PATH) or os.path.getsize(FRAME_PATH) <= 0:
        return False
    try:
        pil_img = Image.open(FRAME_PATH).convert('RGB')
        width_value, height_value = pil_img.size
        if width_value > SHOT_WIDTH:
            new_height = int(round((float(SHOT_WIDTH) / float(width_value)) * float(height_value)))
            pil_img = pil_img.resize((SHOT_WIDTH, max(1, new_height)), Image.LANCZOS)
        draw_cursor_overlay(pil_img)
        buffer = BytesIO()
        pil_img.save(buffer, format='JPEG', quality=SHOT_JPEG_QUALITY, optimize=True, progressive=True)
        img.value = buffer.getvalue()
        return True
    except Exception:
        try:
            with open(FRAME_PATH, 'rb') as handle:
                img.value = handle.read()
            return True
        except Exception:
            return False


def screenshot_loop():
    global FRAME_COUNT
    while not STOP_EVENT.is_set():
        ok = capture_frame_once()
        if ok and refresh_frame_widget():
            FRAME_COUNT += 1
            status.value = status_text()
        else:
            status.value = 'Frame #' + str(FRAME_COUNT) + ' - Failed to capture screenshot'
        time.sleep(SHOT_INTERVAL)


def heartbeat_loop():
    while not STOP_EVENT.is_set():
        heartbeat.value = 'Heartbeat: ' + time.strftime('%H:%M:%S')
        time.sleep(20)


def _ag_click(coords):
    try:
        x_str, y_str = coords.split(',')
        x_val = max(0, min(SCREEN_W - 1, int(float(x_str))))
        y_val = max(0, min(SCREEN_H - 1, int(float(y_str))))
        xmove(x_val, y_val)
        time.sleep(0.05)
        xclick(1)
        set_status('Left click at ' + str(x_val) + ',' + str(y_val))
    except Exception as exc:
        set_status('Click error: ' + str(exc)[:120])


def _ag_rclick(coords):
    try:
        x_str, y_str = coords.split(',')
        x_val = max(0, min(SCREEN_W - 1, int(float(x_str))))
        y_val = max(0, min(SCREEN_H - 1, int(float(y_str))))
        xmove(x_val, y_val)
        time.sleep(0.05)
        xclick(3)
        set_status('Right click at ' + str(x_val) + ',' + str(y_val))
    except Exception as exc:
        set_status('Right click error: ' + str(exc)[:120])


def coords_from_dom_event(event_value):
    data_x = event_value.get('dataX')
    data_y = event_value.get('dataY')
    rel_x = event_value.get('relativeX')
    rel_y = event_value.get('relativeY')
    width_val = event_value.get('boundingRectWidth') or event_value.get('boundingRect', {}).get('width') or event_value.get('target', {}).get('width') or 0
    height_val = event_value.get('boundingRectHeight') or event_value.get('boundingRect', {}).get('height') or event_value.get('target', {}).get('height') or 0

    if data_x is not None and data_y is not None:
        x_val = int(float(data_x))
        y_val = int(float(data_y))
        return max(0, min(SCREEN_W - 1, x_val)), max(0, min(SCREEN_H - 1, y_val))

    if rel_x is not None and rel_y is not None and width_val and height_val:
        x_scaled = int(round((float(rel_x) / float(width_val)) * SCREEN_W))
        y_scaled = int(round((float(rel_y) / float(height_val)) * SCREEN_H))
        return max(0, min(SCREEN_W - 1, x_scaled)), max(0, min(SCREEN_H - 1, y_scaled))

    if rel_x is not None and rel_y is not None:
        x_val = int(float(rel_x))
        y_val = int(float(rel_y))
        return max(0, min(SCREEN_W - 1, x_val)), max(0, min(SCREEN_H - 1, y_val))

    raise RuntimeError('No usable coordinates in event')


def handle_image_dom_event(event_value):
    try:
        event_type = str(event_value.get('type') or '')
        x_val, y_val = coords_from_dom_event(event_value)
        xmove(x_val, y_val)
        time.sleep(0.03)
        if event_type == 'contextmenu':
            xclick(3)
            set_status('Right click at ' + str(x_val) + ',' + str(y_val))
        else:
            xclick(1)
            set_status('Left click at ' + str(x_val) + ',' + str(y_val))
    except Exception as exc:
        set_status('Image event error: ' + str(exc)[:120])


def bind_image_events():
    global IMAGE_EVENT
    if img is None:
        return False
    if Event is None:
        return False
    try:
        IMAGE_EVENT = Event(
            source=img,
            watched_events=['click', 'mousedown', 'mouseup', 'contextmenu', 'touchstart', 'touchend']
        )
        IMAGE_EVENT.prevent_default_action = True
        IMAGE_EVENT.wait = 0
        IMAGE_EVENT.throttle_or_debounce = 'throttle'
        IMAGE_EVENT.on_dom_event(handle_image_dom_event)
        set_status('Image click bridge ready')
        return True
    except Exception as exc:
        IMAGE_EVENT = None
        set_status('Image bridge fallback: ' + str(exc)[:120])
        return False


def shutdown_runtime(_=None):
    STOP_EVENT.set()
    save_runtime_state()
    try:
        if BROWSER_PROCESS is not None:
            BROWSER_PROCESS.terminate()
    except Exception:
        pass
    try:
        if XVFB_HANDLE is not None:
            XVFB_HANDLE.stop()
    except Exception:
        pass
    set_status('Stopped runtime')


def launch_runtime():
    global XVFB_HANDLE, BROWSER_PROCESS, BROWSER_BIN

    BROWSER_BIN = find_browser_binary()
    if not BROWSER_BIN:
        raise RuntimeError('No browser binary found after launcher setup')

    XVFB_HANDLE = Xvfb(width=SCREEN_W, height=SCREEN_H, colordepth=24, display=99)
    XVFB_HANDLE.start()
    time.sleep(1.0)

    browser_command = [
        BROWSER_BIN,
        '--no-sandbox',
        '--disable-gpu',
        '--window-size=1280,800',
        '--disable-dev-shm-usage',
        '--disable-setuid-sandbox',
        '--user-data-dir=' + STATE['profile_dir'],
        '--download-default-directory=' + STATE['downloads_dir'],
        '--homepage=' + URL_GOOGLE,
        URL_GOOGLE,
    ]
    env = dict(os.environ)
    env['DISPLAY'] = DISPLAY_VALUE
    env['XDG_RUNTIME_DIR'] = STATE['runtime_dir']
    BROWSER_PROCESS = subprocess.Popen(browser_command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.0)


def build_image_bridge_script():
    return """
<script>
(function() {
  function kernelExecute(name, payload) {
    try {
      if (window.google && window.google.colab && window.google.colab.kernel && window.google.colab.kernel.invokeFunction) {
        window.google.colab.kernel.invokeFunction(name, [payload], {});
        return true;
      }
    } catch (e) {}
    try {
      if (window.Jupyter && window.Jupyter.notebook && window.Jupyter.notebook.kernel) {
        window.Jupyter.notebook.kernel.execute(name + '(\"' + payload + '\")');
        return true;
      }
    } catch (e) {}
    try {
      if (window.IPython && window.IPython.notebook && window.IPython.notebook.kernel) {
        window.IPython.notebook.kernel.execute(name + '(\"' + payload + '\")');
        return true;
      }
    } catch (e) {}
    return false;
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function findImage() {
    var images = Array.from(document.querySelectorAll('img'));
    images = images.filter(function(node) {
      var rect = node.getBoundingClientRect();
      return rect.width > 140 && rect.height > 90;
    });
    if (!images.length) return null;
    var best = images[0];
    var bestArea = 0;
    images.forEach(function(node) {
      var rect = node.getBoundingClientRect();
      var area = rect.width * rect.height;
      if (area > bestArea) {
        bestArea = area;
        best = node;
      }
    });
    return best;
  }

  function coordsFromPoint(image, clientX, clientY) {
    var rect = image.getBoundingClientRect();
    if (!rect.width || !rect.height) return '0,0';
    var x = Math.round(((clientX - rect.left) / rect.width) * 1280);
    var y = Math.round(((clientY - rect.top) / rect.height) * 800);
    return clamp(x, 0, 1279) + ',' + clamp(y, 0, 799);
  }

  function flash(image) {
    var old = image.style.boxShadow;
    image.style.boxShadow = '0 0 0 3px rgba(34,197,94,0.75), 0 0 28px rgba(34,197,94,0.45)';
    setTimeout(function() { image.style.boxShadow = old || '0 0 0 2px rgba(34,197,94,0.45)'; }, 180);
  }

  function sendLeft(image, clientX, clientY) {
    var payload = coordsFromPoint(image, clientX, clientY);
    flash(image);
    kernelExecute('_ag_click', payload);
  }

  function sendRight(image, clientX, clientY) {
    var payload = coordsFromPoint(image, clientX, clientY);
    flash(image);
    kernelExecute('_ag_rclick', payload);
  }

  function attach() {
    var image = findImage();
    if (!image) {
      setTimeout(attach, 500);
      return;
    }
    if (image.dataset.bcAttached === '1') {
      return;
    }
    image.dataset.bcAttached = '1';
    image.style.cursor = 'crosshair';
    image.style.border = '2px solid #22c55e';
    image.style.boxShadow = '0 0 0 2px rgba(34,197,94,0.45)';
    image.style.touchAction = 'none';
    image.style.webkitUserSelect = 'none';
    image.style.userSelect = 'none';

    var touchTimer = null;
    var touchMoved = false;
    var longPressed = false;
    var startX = 0;
    var startY = 0;

    image.addEventListener('pointerdown', function(ev) {
      if (ev.pointerType === 'touch') {
        startX = ev.clientX;
        startY = ev.clientY;
        touchMoved = false;
        longPressed = false;
        if (touchTimer) clearTimeout(touchTimer);
        touchTimer = setTimeout(function() {
          longPressed = true;
          sendRight(image, startX, startY);
          touchTimer = null;
        }, 520);
      }
    }, true);

    image.addEventListener('pointermove', function(ev) {
      if (ev.pointerType === 'touch') {
        if (Math.abs(ev.clientX - startX) > 10 || Math.abs(ev.clientY - startY) > 10) {
          touchMoved = true;
          if (touchTimer) {
            clearTimeout(touchTimer);
            touchTimer = null;
          }
        }
      }
    }, true);

    image.addEventListener('pointerup', function(ev) {
      if (ev.pointerType === 'touch') {
        if (touchTimer) {
          clearTimeout(touchTimer);
          touchTimer = null;
        }
        if (!touchMoved && !longPressed) {
          sendLeft(image, ev.clientX, ev.clientY);
        }
        ev.preventDefault();
        ev.stopPropagation();
      }
    }, true);

    image.addEventListener('click', function(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      sendLeft(image, ev.clientX, ev.clientY);
      return false;
    }, true);

    image.addEventListener('mousedown', function(ev) {
      if (ev.button === 0) {
        ev.preventDefault();
        ev.stopPropagation();
      }
    }, true);

    image.addEventListener('contextmenu', function(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      sendRight(image, ev.clientX, ev.clientY);
      return false;
    }, true);

    image.addEventListener('touchstart', function(ev) {
      if (!ev.changedTouches || !ev.changedTouches.length) return;
      touchMoved = false;
      longPressed = false;
      var touch = ev.changedTouches[0];
      startX = touch.clientX;
      startY = touch.clientY;
      if (touchTimer) clearTimeout(touchTimer);
      touchTimer = setTimeout(function() {
        longPressed = true;
        sendRight(image, startX, startY);
        touchTimer = null;
      }, 520);
    }, { passive: false, capture: true });

    image.addEventListener('touchmove', function(ev) {
      if (!ev.changedTouches || !ev.changedTouches.length) return;
      var touch = ev.changedTouches[0];
      if (Math.abs(touch.clientX - startX) > 10 || Math.abs(touch.clientY - startY) > 10) {
        touchMoved = true;
        if (touchTimer) {
          clearTimeout(touchTimer);
          touchTimer = null;
        }
      }
    }, { passive: false, capture: true });

    image.addEventListener('touchend', function(ev) {
      if (!ev.changedTouches || !ev.changedTouches.length) return;
      var touch = ev.changedTouches[0];
      if (touchTimer) {
        clearTimeout(touchTimer);
        touchTimer = null;
      }
      if (!touchMoved && !longPressed) {
        sendLeft(image, touch.clientX, touch.clientY);
      }
      ev.preventDefault();
      ev.stopPropagation();
    }, { passive: false, capture: true });
  }

  attach();
  setInterval(attach, 1500);
})();
</script>
"""


def try_register_callbacks():
    try:
        from google.colab import output
        output.register_callback('_ag_click', _ag_click)
        output.register_callback('_ag_rclick', _ag_rclick)
    except Exception:
        pass


def create_button(label_text, handler, style_text=''):
    button = widgets.Button(
        description=label_text,
        button_style=style_text,
        layout=widgets.Layout(width='150px', min_width='150px', height='50px', margin='5px')
    )
    button.style.font_weight = '600'
    button.style.font_size = '13px'
    button.on_click(handler)
    return button


def restore_state_into_widgets():
    global CURSOR_X, CURSOR_Y
    payload = load_runtime_state()
    if payload.get('last_url'):
        url.value = str(payload.get('last_url'))
    try:
        CURSOR_X = max(0, min(SCREEN_W - 1, int(payload.get('cursor_x', CURSOR_X))))
        CURSOR_Y = max(0, min(SCREEN_H - 1, int(payload.get('cursor_y', CURSOR_Y))))
    except Exception:
        pass
    if payload.get('github_owner'):
        github_owner.value = str(payload.get('github_owner'))
    if payload.get('github_repo'):
        github_repo.value = str(payload.get('github_repo'))
    if payload.get('github_branch'):
        github_branch.value = str(payload.get('github_branch'))
    if payload.get('github_prefix'):
        github_prefix.value = str(payload.get('github_prefix'))
    if payload.get('github_commit_message'):
        github_commit_message.value = str(payload.get('github_commit_message'))


def build_ui():
    global img, status, heartbeat, url, type_txt, info_html, downloads_html, state_html, github_status_html
    global github_token, github_owner, github_repo, github_branch, github_prefix, github_mode, github_commit_message

    img = widgets.Image(format='jpeg', width='100%', layout=widgets.Layout(width='100%', max_width='1120px', object_fit='contain', border='2px solid #22c55e'))
    status = widgets.Label(value='Frame #0 - last action')
    heartbeat = widgets.Label(value='Heartbeat: starting')
    url = widgets.Text(value=URL_GOOGLE, placeholder='Enter URL')
    type_txt = widgets.Textarea(value='', placeholder='Enter text to type here', layout=widgets.Layout(height='90px'))

    github_token = widgets.Password(value='', placeholder='Paste GitHub token here')
    github_owner = widgets.Text(value=DEFAULT_OWNER, placeholder='GitHub owner')
    github_repo = widgets.Text(value=DEFAULT_REPO, placeholder='GitHub repo')
    github_branch = widgets.Text(value=DEFAULT_BRANCH, placeholder='GitHub branch')
    github_prefix = widgets.Text(value=DEFAULT_PREFIX, placeholder='Repo subfolder prefix, optional')
    github_mode = widgets.Dropdown(options=['Bundle only', 'Bundle + README'], value='Bundle only', description='Publish')
    github_commit_message = widgets.Text(value='Update browser controller bundle from Kaggle', placeholder='Commit message prefix')

    cpu_text = detect_cpu_info()
    persistence_text = 'Persistent storage enabled under /kaggle/working' if STATE['persistent'] else 'Temporary storage only'
    previous_session = 'yes' if profile_has_previous_session(STATE['profile_dir']) else 'no'

    info_html = widgets.HTML(html_message_box(
        'Desktop-like Kaggle browser controller',
        [
            'CPU: ' + cpu_text,
            'Persistence: ' + persistence_text,
            'Existing Chrome session found: ' + previous_session,
            'Visible green crosshair is drawn on every frame so you can see the controlled cursor.',
            'Image stream is balanced for mobile: clearer than before but still compressed.',
            'If direct touch click is flaky on Kaggle mobile, use Move Cursor + Click Cursor buttons.',
            'Chrome profile and downloads are saved so Google login and downloaded files survive reruns when Kaggle persistence is enabled.',
        ],
        '#22c55e'
    ))
    downloads_html = widgets.HTML(list_download_files_html(STATE['downloads_dir']))
    state_html = widgets.HTML('')
    github_status_html = widgets.HTML(html_message_box('GitHub upload', ['Paste token, validate access, then upload bundle.'], '#f59e0b'))

    row1 = widgets.HBox([
        create_button('Go URL', act_go, 'success'),
        create_button('Back', act_back),
        create_button('Forward', act_fwd),
        create_button('Reload', act_reload),
        create_button('Home', act_home),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    row2 = widgets.HBox([
        create_button('Enter', act_enter),
        create_button('Escape', act_esc),
        create_button('Tab', act_tab),
        create_button('Arrow Up', act_up),
        create_button('Arrow Down', act_down),
        create_button('Page Up', act_pgup),
        create_button('Page Down', act_pgdn),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    row3 = widgets.HBox([
        create_button('Copy', act_copy),
        create_button('Paste', act_paste),
        create_button('Select All', act_sel_all),
        create_button('Right Click', act_right_click),
        create_button('Scroll Up', act_scroll_up),
        create_button('Scroll Down', act_scroll_down),
        create_button('Zoom In', act_zoom_in),
        create_button('Zoom Out', act_zoom_out),
        create_button('Fast 1s', act_fast, 'warning'),
        create_button('Slow 5s', act_slow),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    row4 = widgets.HBox([
        create_button('Type + Enter', act_type_submit, 'success'),
        create_button('Type Only', act_type_only),
        create_button('Google Login', open_google_login),
        create_button('Downloads', open_chrome_downloads),
        create_button('Kaggle CPU', open_kaggle_cpu),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    row5 = widgets.HBox([
        create_button('Codex Web', open_codex_web),
        create_button('Codex App Page', open_codex_app_page),
        create_button('Codex Releases', open_codex_releases),
        create_button('Antigravity App', open_antigravity_page),
        create_button('Open Both Apps', open_both_apps),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    row6 = widgets.HBox([
        create_button('Move Left', act_move_left),
        create_button('Move Up', act_move_up),
        create_button('Move Down', act_move_down),
        create_button('Move Right', act_move_right),
        create_button('Center Cursor', act_center_cursor),
        create_button('Click Cursor', act_click_cursor, 'success'),
        create_button('Right Click Cursor', act_rclick_cursor),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    row7 = widgets.HBox([
        create_button('Refresh Downloads', refresh_downloads_panel),
        create_button('Save Session', save_runtime_state),
        create_button('Prune Browser Cache', prune_browser_cache),
        create_button('Clear Downloads', clear_downloads),
        create_button('Stop Runtime', shutdown_runtime, 'danger'),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    github_row1 = widgets.HBox([github_token], layout=widgets.Layout(flex_flow='row wrap'))
    github_row2 = widgets.HBox([github_owner, github_repo, github_branch], layout=widgets.Layout(flex_flow='row wrap'))
    github_row3 = widgets.HBox([github_prefix, github_mode], layout=widgets.Layout(flex_flow='row wrap'))
    github_row4 = widgets.HBox([
        github_commit_message,
        create_button('Validate GitHub', validate_github_access),
        create_button('Upload Bundle', push_bundle_to_github, 'success'),
    ], layout=widgets.Layout(flex_flow='row wrap'))

    refresh_state_panel()
    restore_state_into_widgets()

    display(widgets.VBox([
        info_html,
        img,
        status,
        heartbeat,
        url,
        type_txt,
        row1,
        row2,
        row3,
        row4,
        row5,
        row6,
        row7,
        widgets.HTML('<h3 style="margin:12px 0 6px;">Persistent session</h3>'),
        state_html,
        widgets.HTML('<h3 style="margin:12px 0 6px;">Downloads</h3>'),
        downloads_html,
        widgets.HTML('<h3 style="margin:12px 0 6px;">GitHub upload</h3>'),
        github_status_html,
        github_row1,
        github_row2,
        github_row3,
        github_row4,
    ]))

    bridge_ok = bind_image_events()
    display(HTML(build_image_bridge_script()))
    if bridge_ok:
        set_status('Ready - widget click bridge active')
    else:
        set_status('Ready - JS click bridge fallback active')


def start_threads():
    global SCREENSHOT_THREAD, HEARTBEAT_THREAD
    SCREENSHOT_THREAD = threading.Thread(target=screenshot_loop, daemon=True)
    HEARTBEAT_THREAD = threading.Thread(target=heartbeat_loop, daemon=True)
    SCREENSHOT_THREAD.start()
    HEARTBEAT_THREAD.start()


def main():
    launch_runtime()
    try_register_callbacks()
    build_ui()
    xmove(CURSOR_X, CURSOR_Y)
    start_threads()
    refresh_downloads_panel()
    save_runtime_state()


if __name__ == '__main__':
    main()
