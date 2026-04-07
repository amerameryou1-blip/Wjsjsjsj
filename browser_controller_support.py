import io
import os
import re
import json
import time
import html
import base64
import shutil
import zipfile
import subprocess
from urllib.parse import quote_plus, quote, urlparse, unquote

try:
    import requests
except Exception:
    requests = None

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

DISPLAY_VALUE = ':99'
SCREEN_W = 1600
SCREEN_H = 900
STATE_DIR_NAME = 'zorin_kaggle_desktop'
URL_GOOGLE = 'https://www.google.com/'
URL_GITHUB = 'https://github.com/'
URL_KAGGLE = 'https://www.kaggle.com/'
URL_ZORIN = 'https://zorin.com/os/'
URL_XFCE_DOCS = 'https://docs.xfce.org/'
DEFAULT_OWNER = 'amerameryou1-blip'
DEFAULT_REPO = 'Wjsjsjsj'
DEFAULT_BRANCH = 'main'
DEFAULT_PREFIX = ''
DEFAULT_MAIN_PATH = 'browser_controller_main.py'
DEFAULT_SUPPORT_PATH = 'browser_controller_support.py'
DEFAULT_README_PATH = 'README.md'

RESEARCH_NOTES = [
    'Kaggle persistence target: /kaggle/working.',
    'Zorin OS is Ubuntu-based and its Windows-like variants are built around GNOME and Xfce.',
    'Xfce Whisker Menu provides searchable app launching for a Start-menu-like flow.',
    'ipyevents can suppress default context-menu actions with prevent_default_action=True.',
    'xdotool supports mousedown/mouseup separately, which is important for real drag-and-hold behavior.',
    'scrot supports explicit output files and overwrite mode, so capture should reuse one file instead of generating endless numbered names.',
]


def now_text():
    return time.strftime('%Y-%m-%d %H:%M:%S')



def detect_state_root():
    kaggle_root = '/kaggle/working'
    if os.path.isdir(kaggle_root):
        return os.path.join(kaggle_root, STATE_DIR_NAME)
    return os.path.join('/tmp', STATE_DIR_NAME)



def ensure_state_dirs():
    root = detect_state_root()
    runtime_dir = os.path.join(root, 'runtime')
    home_dir = os.path.join(root, 'home')
    downloads_dir = os.path.join(root, 'downloads')
    browser_profile_dir = os.path.join(root, 'browser-profile')
    bundle_dir = os.path.join(root, 'bundle-cache')
    captures_dir = os.path.join(root, 'captures')
    logs_dir = os.path.join(root, 'logs')
    wallpaper_dir = os.path.join(root, 'wallpapers')
    launchers_dir = os.path.join(root, 'launchers')
    cache_dir = os.path.join(root, 'cache')
    temp_dir = os.path.join(root, 'temp')
    desktop_dir = os.path.join(home_dir, 'Desktop')
    documents_dir = os.path.join(home_dir, 'Documents')
    state_json = os.path.join(root, 'state.json')
    install_report = os.path.join(root, 'install-report.json')
    launcher_report = os.path.join(root, 'launcher-report.json')
    session_report = os.path.join(root, 'session-report.json')

    dirs = [
        root,
        runtime_dir,
        home_dir,
        downloads_dir,
        browser_profile_dir,
        bundle_dir,
        captures_dir,
        logs_dir,
        wallpaper_dir,
        launchers_dir,
        cache_dir,
        temp_dir,
        desktop_dir,
        documents_dir,
    ]
    for path_value in dirs:
        os.makedirs(path_value, exist_ok=True)

    os.environ['DISPLAY'] = DISPLAY_VALUE
    os.environ['XDG_RUNTIME_DIR'] = runtime_dir

    return {
        'root': root,
        'runtime_dir': runtime_dir,
        'home_dir': home_dir,
        'downloads_dir': downloads_dir,
        'browser_profile_dir': browser_profile_dir,
        'bundle_dir': bundle_dir,
        'captures_dir': captures_dir,
        'logs_dir': logs_dir,
        'wallpaper_dir': wallpaper_dir,
        'launchers_dir': launchers_dir,
        'cache_dir': cache_dir,
        'temp_dir': temp_dir,
        'desktop_dir': desktop_dir,
        'documents_dir': documents_dir,
        'state_json': state_json,
        'install_report': install_report,
        'launcher_report': launcher_report,
        'session_report': session_report,
        'persistent': root.startswith('/kaggle/working/'),
    }



def session_env(extra_env=None):
    paths = ensure_state_dirs()
    env = dict(os.environ)
    env['DISPLAY'] = DISPLAY_VALUE
    env['HOME'] = paths['home_dir']
    env['XDG_RUNTIME_DIR'] = paths['runtime_dir']
    env['XDG_CONFIG_HOME'] = os.path.join(paths['home_dir'], '.config')
    env['XDG_CACHE_HOME'] = os.path.join(paths['home_dir'], '.cache')
    env['XDG_DATA_HOME'] = os.path.join(paths['home_dir'], '.local', 'share')
    env['GTK_THEME'] = env.get('GTK_THEME', 'Arc-Dark')
    env.setdefault('LANG', 'C.UTF-8')
    env.setdefault('LC_ALL', 'C.UTF-8')
    env.setdefault('DBUS_FATAL_WARNINGS', '0')

    for key_name in ['XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME']:
        os.makedirs(env[key_name], exist_ok=True)

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
    paths = ensure_state_dirs()
    log_path = os.path.join(paths['logs_dir'], log_name)
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
            env=session_env(env),
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
            env=session_env(env),
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
    paths = ensure_state_dirs()
    log_path = os.path.join(paths['logs_dir'], log_name)
    log_handle = open(log_path, 'a', encoding='utf-8')
    process = subprocess.Popen(
        command_value,
        shell=shell,
        cwd=cwd,
        env=session_env(env),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    process._zorin_log_handle = log_handle
    return process



def available_command(candidates):
    for item in candidates:
        path_value = shutil.which(item)
        if path_value:
            return path_value
    return None



def human_size(size_value):
    size_float = float(size_value or 0)
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    for unit_name in units:
        if size_float < 1024 or unit_name == units[-1]:
            if unit_name == 'B':
                return str(int(size_float)) + ' ' + unit_name
            return ('%.1f' % size_float).rstrip('0').rstrip('.') + ' ' + unit_name
        size_float /= 1024.0
    return '0 B'



def detect_cpu_info():
    cpu_model = ''
    cpu_count = os.cpu_count() or 0
    memory_gb = 0.0

    cpuinfo_text = file_read_text('/proc/cpuinfo', '')
    match = re.search(r'^model name\s*:\s*(.+)$', cpuinfo_text, re.MULTILINE)
    if match:
        cpu_model = match.group(1).strip()

    meminfo_text = file_read_text('/proc/meminfo', '')
    match = re.search(r'^MemTotal:\s*(\d+)\s+kB$', meminfo_text, re.MULTILINE)
    if match:
        memory_gb = round(int(match.group(1)) / 1024.0 / 1024.0, 2)

    return {
        'cpu_model': cpu_model,
        'cpu_count': cpu_count,
        'memory_gb': memory_gb,
    }



def html_message_box(kind, title_text, body_text):
    palette = {
        'info': ('#0f172a', '#38bdf8', '#e2e8f0'),
        'success': ('#052e16', '#22c55e', '#dcfce7'),
        'warning': ('#451a03', '#f59e0b', '#fef3c7'),
        'error': ('#450a0a', '#ef4444', '#fee2e2'),
    }
    background, border, text_color = palette.get(kind, palette['info'])
    return (
        '<div style="padding:12px 14px;border:1px solid ' + border + ';border-radius:16px;background:' + background + ';color:' + text_color + ';">'
        '<div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.86;">' + html.escape(kind) + '</div>'
        '<div style="font-size:16px;font-weight:700;margin-top:4px;">' + html.escape(title_text) + '</div>'
        '<div style="font-size:13px;line-height:1.6;margin-top:6px;white-space:pre-wrap;">' + html.escape(body_text) + '</div>'
        '</div>'
    )



def write_svg_wallpaper(paths=None):
    if paths is None:
        paths = ensure_state_dirs()
    wallpaper_path = os.path.join(paths['wallpaper_dir'], 'zorin-kaggle.svg')
    svg_text = '''<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#081120"/>
      <stop offset="45%" stop-color="#0f2740"/>
      <stop offset="100%" stop-color="#0b1630"/>
    </linearGradient>
    <radialGradient id="glowA" cx="20%" cy="18%" r="55%">
      <stop offset="0%" stop-color="#3cc8ff" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#3cc8ff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowB" cx="80%" cy="75%" r="65%">
      <stop offset="0%" stop-color="#6b7cff" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="#6b7cff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1920" height="1080" fill="url(#bg)"/>
  <rect width="1920" height="1080" fill="url(#glowA)"/>
  <rect width="1920" height="1080" fill="url(#glowB)"/>
  <g opacity="0.16">
    <circle cx="260" cy="180" r="92" fill="#40d4ff"/>
    <circle cx="1620" cy="820" r="140" fill="#5f74ff"/>
    <circle cx="1400" cy="230" r="68" fill="#3ab9ff"/>
  </g>
  <g fill="none" stroke="#6ee7ff" stroke-opacity="0.16">
    <path d="M-80 870 C 300 680, 540 1040, 930 860 S 1500 560, 2000 760" stroke-width="3"/>
    <path d="M-120 920 C 250 730, 620 1070, 980 920 S 1450 650, 2020 820" stroke-width="2"/>
  </g>
  <g transform="translate(110,160)">
    <text x="0" y="0" fill="#ffffff" font-family="DejaVu Sans, Arial, sans-serif" font-size="78" font-weight="700">Zorin-style Kaggle Desktop</text>
    <text x="2" y="72" fill="#9edcff" font-family="DejaVu Sans, Arial, sans-serif" font-size="28">Windows-like XFCE layout recreated for Kaggle /kaggle/working persistence</text>
  </g>
</svg>
'''
    file_write_text(wallpaper_path, svg_text)
    return wallpaper_path



def write_desktop_entry(path_value, name, exec_line, icon_name, comment_text=''):
    content = (
        '[Desktop Entry]\n'
        'Version=1.0\n'
        'Type=Application\n'
        'Name=' + name + '\n'
        'Comment=' + comment_text + '\n'
        'Exec=' + exec_line + '\n'
        'Icon=' + icon_name + '\n'
        'Terminal=false\n'
        'Categories=Utility;\n'
        'StartupNotify=true\n'
    )
    file_write_text(path_value, content)
    try:
        os.chmod(path_value, 0o755)
    except Exception:
        pass
    return path_value



def write_desktop_shortcuts(paths=None):
    if paths is None:
        paths = ensure_state_dirs()

    browser_name = available_command(['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'firefox', 'firefox-esr']) or 'xdg-open'
    terminal_name = available_command(['xfce4-terminal', 'xterm']) or 'xterm'
    files_name = available_command(['thunar', 'xdg-open']) or 'xdg-open'

    entries = [
        ('Browser.desktop', 'Web Browser', browser_name + ' ' + URL_GOOGLE, 'web-browser', 'Open the browser in the Zorin-style desktop session'),
        ('Terminal.desktop', 'Terminal', terminal_name, 'utilities-terminal', 'Open a terminal inside the Kaggle desktop'),
        ('Files.desktop', 'Files', files_name + ' ' + paths['downloads_dir'], 'system-file-manager', 'Open saved downloads'),
        ('Kaggle Working.desktop', 'Kaggle Working', files_name + ' /kaggle/working', 'folder', 'Open Kaggle working storage'),
        ('Downloads.desktop', 'Downloads', files_name + ' ' + paths['downloads_dir'], 'folder-download', 'Open the persistent downloads folder'),
    ]

    created = []
    for file_name, name, exec_line, icon_name, comment_text in entries:
        desktop_path = os.path.join(paths['desktop_dir'], file_name)
        created.append(write_desktop_entry(desktop_path, name, exec_line, icon_name, comment_text))
    return created



def _xfce_channel_dir(paths):
    return os.path.join(paths['home_dir'], '.config', 'xfce4', 'xfconf', 'xfce-perchannel-xml')



def write_xfce_configs(paths=None):
    if paths is None:
        paths = ensure_state_dirs()

    wallpaper_path = write_svg_wallpaper(paths)
    config_dir = _xfce_channel_dir(paths)
    os.makedirs(config_dir, exist_ok=True)
    panel_dir = os.path.join(paths['home_dir'], '.config', 'xfce4', 'panel')
    os.makedirs(panel_dir, exist_ok=True)
    gtk3_dir = os.path.join(paths['home_dir'], '.config', 'gtk-3.0')
    os.makedirs(gtk3_dir, exist_ok=True)

    xsettings_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xsettings" version="1.0">
  <property name="Net" type="empty">
    <property name="ThemeName" type="string" value="Arc-Dark"/>
    <property name="IconThemeName" type="string" value="Papirus-Dark"/>
    <property name="DoubleClickTime" type="int" value="400"/>
  </property>
  <property name="Gtk" type="empty">
    <property name="CursorThemeName" type="string" value="Adwaita"/>
    <property name="CursorThemeSize" type="int" value="24"/>
    <property name="FontName" type="string" value="DejaVu Sans 10"/>
    <property name="MonospaceFontName" type="string" value="DejaVu Sans Mono 10"/>
    <property name="ButtonImages" type="bool" value="true"/>
    <property name="MenuImages" type="bool" value="true"/>
  </property>
</channel>
'''

    xfwm4_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="theme" type="string" value="Arc-Dark"/>
    <property name="title_font" type="string" value="DejaVu Sans Bold 10"/>
    <property name="button_layout" type="string" value="O|HMC"/>
    <property name="workspace_count" type="int" value="1"/>
    <property name="use_compositing" type="bool" value="false"/>
    <property name="double_click_action" type="string" value="maximize"/>
  </property>
</channel>
'''

    xfce_panel_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-panel" version="1.0">
  <property name="panels" type="uint" value="1">
    <property name="panel-0" type="empty">
      <property name="position" type="string" value="p=8;x=0;y=0"/>
      <property name="length" type="uint" value="100"/>
      <property name="position-locked" type="bool" value="true"/>
      <property name="size" type="uint" value="40"/>
      <property name="length-adjust" type="bool" value="true"/>
      <property name="background-style" type="uint" value="0"/>
      <property name="background-alpha" type="uint" value="100"/>
      <property name="enter-opacity" type="uint" value="100"/>
      <property name="leave-opacity" type="uint" value="100"/>
      <property name="mode" type="uint" value="0"/>
      <property name="autohide-behavior" type="uint" value="0"/>
      <property name="plugin-ids" type="array">
        <value type="int" value="101"/>
        <value type="int" value="102"/>
        <value type="int" value="103"/>
        <value type="int" value="104"/>
        <value type="int" value="105"/>
      </property>
    </property>
  </property>
  <property name="plugins" type="empty">
    <property name="plugin-101" type="string" value="whiskermenu"/>
    <property name="plugin-102" type="string" value="separator">
      <property name="expand" type="bool" value="false"/>
      <property name="style" type="uint" value="0"/>
    </property>
    <property name="plugin-103" type="string" value="tasklist"/>
    <property name="plugin-104" type="string" value="separator">
      <property name="expand" type="bool" value="true"/>
      <property name="style" type="uint" value="0"/>
    </property>
    <property name="plugin-105" type="string" value="clock">
      <property name="mode" type="uint" value="2"/>
      <property name="digital-format" type="string" value="%a %d %b  %H:%M"/>
    </property>
  </property>
</channel>
'''

    desktop_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-desktop" version="1.0">
  <property name="desktop-icons" type="empty">
    <property name="style" type="int" value="2"/>
    <property name="file-icons" type="empty">
      <property name="show-home" type="bool" value="true"/>
      <property name="show-filesystem" type="bool" value="true"/>
      <property name="show-trash" type="bool" value="true"/>
      <property name="show-removable" type="bool" value="false"/>
    </property>
  </property>
</channel>
'''

    gtk_css = '''.xfce4-panel {
  background: #101826;
}
.xfce4-panel widget,
.xfce4-panel button {
  color: #e2e8f0;
}
'''

    file_write_text(os.path.join(config_dir, 'xsettings.xml'), xsettings_xml)
    file_write_text(os.path.join(config_dir, 'xfwm4.xml'), xfwm4_xml)
    file_write_text(os.path.join(config_dir, 'xfce4-panel.xml'), xfce_panel_xml)
    file_write_text(os.path.join(config_dir, 'xfce4-desktop.xml'), desktop_xml)
    file_write_text(os.path.join(gtk3_dir, 'gtk.css'), gtk_css)
    write_desktop_shortcuts(paths)

    return {
        'wallpaper_path': wallpaper_path,
        'config_dir': config_dir,
        'panel_config_path': os.path.join(config_dir, 'xfce4-panel.xml'),
    }



def install_or_repair_stack(include_browser=True):
    paths = ensure_state_dirs()
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'

    core_packages = [
        'dbus-x11',
        'xvfb',
        'xdotool',
        'x11-apps',
        'x11-utils',
        'scrot',
        'imagemagick',
        'xclip',
        'xsel',
        'curl',
        'wget',
        'ca-certificates',
        'file',
        'procps',
        'unzip',
        'zip',
        'p7zip-full',
        'jq',
        'xfce4',
        'xfce4-goodies',
        'xfce4-terminal',
        'xfce4-whiskermenu-plugin',
        'thunar',
        'mousepad',
        'ristretto',
        'file-roller',
        'arc-theme',
        'papirus-icon-theme',
        'fonts-dejavu-core',
        'fonts-liberation',
    ]

    browser_candidates = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'firefox', 'firefox-esr']
    browser_found_before = available_command(browser_candidates) is not None

    update_result = run_shell('apt-get update -y', timeout=1800)
    install_result = run_shell('apt-get install -y ' + ' '.join(core_packages), timeout=7200)

    browser_install = {'ok': browser_found_before, 'stdout': '', 'stderr': '', 'method': 'existing'}
    if include_browser and not browser_found_before:
        chrome_deb = os.path.join(paths['cache_dir'], 'google-chrome-stable_current_amd64.deb')
        download_result = run_shell(
            'wget -q -O ' + chrome_deb + ' https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb',
            timeout=1800,
        )
        if download_result['ok']:
            install_chrome = run_shell('apt-get install -y ' + chrome_deb + ' || apt-get -f install -y', timeout=3600)
            browser_install = dict(install_chrome)
            browser_install['method'] = 'google-chrome-deb'
        else:
            chromium_try = run_shell('apt-get install -y chromium-browser || apt-get install -y chromium || true', timeout=3600)
            browser_install = dict(chromium_try)
            browser_install['method'] = 'chromium-fallback'

    browser_found_after = available_command(browser_candidates)
    report = {
        'timestamp': now_text(),
        'state_root': paths['root'],
        'persistent': paths['persistent'],
        'packages': core_packages,
        'update': update_result,
        'install': install_result,
        'browser_install': browser_install,
        'browser_found': browser_found_after,
        'cpu': detect_cpu_info(),
        'research_notes': RESEARCH_NOTES,
    }
    save_json(paths['install_report'], report)
    append_log('install.log', 'install_or_repair_stack: ' + json.dumps({'browser_found': browser_found_after, 'persistent': paths['persistent']}))
    return report



def process_lines(match_text):
    result = run_shell("pgrep -af " + subprocess.list2cmdline([match_text]) + " || true", timeout=30)
    lines = [line.strip() for line in (result['stdout'] or '').splitlines() if line.strip()]
    return lines



def ensure_xvfb_running():
    running = process_lines('Xvfb ' + DISPLAY_VALUE)
    if running:
        return {
            'ok': True,
            'started': False,
            'display': DISPLAY_VALUE,
            'processes': running,
        }

    run_background(
        ['Xvfb', DISPLAY_VALUE, '-screen', '0', str(SCREEN_W) + 'x' + str(SCREEN_H) + 'x24', '-ac', '+extension', 'RANDR'],
        log_name='xvfb.log',
    )
    for _ in range(30):
        probe = run_shell('xdpyinfo -display ' + DISPLAY_VALUE + ' >/dev/null 2>&1', timeout=15)
        if probe['returncode'] == 0:
            running = process_lines('Xvfb ' + DISPLAY_VALUE)
            return {
                'ok': True,
                'started': True,
                'display': DISPLAY_VALUE,
                'processes': running,
            }
        time.sleep(0.5)
    return {
        'ok': False,
        'started': True,
        'display': DISPLAY_VALUE,
        'processes': process_lines('Xvfb'),
    }



def _set_wallpaper_paths_live(wallpaper_path):
    known_paths = [
        '/backdrop/screen0/monitor0/workspace0/last-image',
        '/backdrop/screen0/monitorVirtual-1/workspace0/last-image',
        '/backdrop/screen0/monitorVirtual1/workspace0/last-image',
        '/backdrop/screen0/monitorLVDS1/workspace0/last-image',
    ]
    for property_path in known_paths:
        run_list(['xfconf-query', '-c', 'xfce4-desktop', '-p', property_path, '-n', '-t', 'string', '-s', wallpaper_path], timeout=30)
    listed = run_list(['xfconf-query', '-c', 'xfce4-desktop', '-l'], timeout=30)
    for line in (listed.get('stdout') or '').splitlines():
        property_path = line.strip()
        if property_path.endswith('/last-image'):
            run_list(['xfconf-query', '-c', 'xfce4-desktop', '-p', property_path, '-s', wallpaper_path], timeout=30)



def apply_zorin_layout():
    paths = ensure_state_dirs()
    written = write_xfce_configs(paths)

    run_shell('pkill -f xfce4-panel || true', timeout=30)
    run_shell('pkill -f xfdesktop || true', timeout=30)
    time.sleep(0.6)
    panel_cmd = available_command(['xfce4-panel'])
    desktop_cmd = available_command(['xfdesktop'])
    settings_cmd = available_command(['xfsettingsd'])
    thunar_cmd = available_command(['thunar'])

    if settings_cmd:
        run_background([settings_cmd], log_name='xfsettingsd.log')
    if desktop_cmd:
        run_background([desktop_cmd, '--reload'], log_name='xfdesktop.log')
    if panel_cmd:
        run_background([panel_cmd], log_name='xfce4-panel.log')
    if thunar_cmd:
        run_background([thunar_cmd, '--daemon'], log_name='thunar.log')

    _set_wallpaper_paths_live(written['wallpaper_path'])
    run_shell("xsetroot -solid '#0b1630' || true", timeout=30)

    report = {
        'timestamp': now_text(),
        'wallpaper_path': written['wallpaper_path'],
        'home_dir': paths['home_dir'],
        'desktop_dir': paths['desktop_dir'],
        'persistent': paths['persistent'],
    }
    save_json(paths['session_report'], report)
    append_log('session.log', 'apply_zorin_layout completed')
    return report



def ensure_desktop_session():
    paths = ensure_state_dirs()
    ensure_xvfb_running()
    write_xfce_configs(paths)

    session_running = process_lines('xfce4-session') or process_lines('startxfce4') or process_lines('xfwm4')
    if not session_running:
        if available_command(['startxfce4']) and available_command(['dbus-launch']):
            run_background(
                ['dbus-launch', '--exit-with-session', 'startxfce4'],
                log_name='xfce-session.log',
                cwd=paths['home_dir'],
            )
        else:
            run_background(
                "dbus-launch --exit-with-session sh -lc 'xfsettingsd & xfwm4 & xfdesktop & xfce4-panel & thunar --daemon & wait'",
                log_name='xfce-session.log',
                cwd=paths['home_dir'],
                shell=True,
            )
        time.sleep(4)

    layout_report = apply_zorin_layout()
    browser_path = find_browser_binary()
    report = {
        'timestamp': now_text(),
        'display': DISPLAY_VALUE,
        'screen': str(SCREEN_W) + 'x' + str(SCREEN_H),
        'browser': browser_path,
        'state_root': paths['root'],
        'persistent': paths['persistent'],
        'session_processes': process_lines('xfce4-session') + process_lines('xfwm4') + process_lines('xfce4-panel'),
        'layout': layout_report,
    }
    save_json(paths['session_report'], report)
    return report



def find_browser_binary():
    return available_command(['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'firefox', 'firefox-esr'])



def launch_browser(url_value=''):
    paths = ensure_state_dirs()
    ensure_desktop_session()
    browser = find_browser_binary()
    url_value = (url_value or URL_GOOGLE).strip() or URL_GOOGLE
    if browser is None:
        return {'ok': False, 'message': 'No browser binary found'}

    base_name = os.path.basename(browser)
    if 'chrome' in base_name or 'chromium' in base_name or 'brave' in base_name:
        args = [
            browser,
            '--user-data-dir=' + paths['browser_profile_dir'],
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--new-window',
            '--window-size=' + str(SCREEN_W - 50) + ',' + str(SCREEN_H - 120),
            url_value,
        ]
    elif 'firefox' in base_name:
        profile_dir = os.path.join(paths['browser_profile_dir'], 'firefox-profile')
        os.makedirs(profile_dir, exist_ok=True)
        args = [browser, '--new-instance', '--profile', profile_dir, url_value]
    else:
        args = [browser, url_value]

    run_background(args, log_name='browser.log', cwd=paths['home_dir'])
    append_log('session.log', 'launch_browser ' + url_value)
    return {'ok': True, 'browser': browser, 'url': url_value}



def launch_terminal():
    ensure_desktop_session()
    terminal = available_command(['xfce4-terminal', 'xterm'])
    if terminal is None:
        return {'ok': False, 'message': 'No terminal binary found'}
    run_background([terminal], log_name='terminal.log')
    return {'ok': True, 'terminal': terminal}



def launch_file_manager(path_value=''):
    ensure_desktop_session()
    paths = ensure_state_dirs()
    target = path_value or paths['downloads_dir']
    manager = available_command(['thunar', 'xdg-open'])
    if manager is None:
        return {'ok': False, 'message': 'No file manager found'}
    run_background([manager, target], log_name='files.log')
    return {'ok': True, 'manager': manager, 'target': target}



def clamp_int(value, low, high):
    try:
        number = int(round(float(value)))
    except Exception:
        number = low
    return max(low, min(high, number))



def move_mouse(x_value, y_value):
    x_value = clamp_int(x_value, 0, SCREEN_W - 1)
    y_value = clamp_int(y_value, 0, SCREEN_H - 1)
    return run_list(['xdotool', 'mousemove', str(x_value), str(y_value)], timeout=10)



def mouse_down(button_value=1):
    return run_list(['xdotool', 'mousedown', str(int(button_value))], timeout=10)



def mouse_up(button_value=1):
    return run_list(['xdotool', 'mouseup', str(int(button_value))], timeout=10)



def click(button_value=1, repeat=1):
    args = ['xdotool', 'click']
    if repeat and int(repeat) > 1:
        args += ['--repeat', str(int(repeat)), '--delay', '110']
    args.append(str(int(button_value)))
    return run_list(args, timeout=10)



def scroll_vertical(amount):
    button_value = 4 if int(amount) < 0 else 5
    repeat = max(1, min(20, abs(int(amount))))
    return click(button_value, repeat=repeat)



def send_key(key_text):
    key_text = (key_text or '').strip()
    if not key_text:
        return {'ok': False, 'message': 'No key provided'}
    return run_list(['xdotool', 'key', '--clearmodifiers', key_text], timeout=15)



def type_text(text_value):
    text_value = '' if text_value is None else str(text_value)
    return run_list(['xdotool', 'type', '--delay', '1', text_value], timeout=120)



def get_active_window_title():
    first = run_list(['xdotool', 'getactivewindow'], timeout=10)
    window_id = (first.get('stdout') or '').strip()
    if not window_id:
        return ''
    second = run_list(['xdotool', 'getwindowname', window_id], timeout=10)
    return (second.get('stdout') or '').strip()



def set_clipboard_text(text_value):
    text_value = '' if text_value is None else str(text_value)
    if available_command(['xclip']):
        return run_list(['xclip', '-selection', 'clipboard'], timeout=15, input_text=text_value)
    if available_command(['xsel']):
        return run_list(['xsel', '--clipboard', '--input'], timeout=15, input_text=text_value)
    return {'ok': False, 'message': 'No clipboard tool found'}



def get_clipboard_text():
    if available_command(['xclip']):
        result = run_list(['xclip', '-selection', 'clipboard', '-o'], timeout=15)
        return result.get('stdout', '') if result.get('ok') else ''
    if available_command(['xsel']):
        result = run_list(['xsel', '--clipboard', '--output'], timeout=15)
        return result.get('stdout', '') if result.get('ok') else ''
    return ''



def smart_paste_text(text_value):
    text_value = '' if text_value is None else str(text_value)
    set_clipboard_text(text_value)
    first = send_key('ctrl+shift+v')
    second = send_key('shift+Insert')
    return {
        'ok': bool(first.get('ok') or second.get('ok')),
        'attempts': [first, second],
    }



def _fallback_capture_image(message_text):
    if Image is None or ImageDraw is None:
        return ('Kaggle desktop screenshot unavailable\n\n' + message_text).encode('utf-8', errors='ignore')

    image = Image.new('RGB', (SCREEN_W, SCREEN_H), '#111827')
    draw = ImageDraw.Draw(image)
    font = None
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    draw.rectangle((42, 42, SCREEN_W - 42, SCREEN_H - 42), outline='#38bdf8', width=4)
    lines = [
        'Kaggle desktop screen unavailable',
        '',
        message_text,
        '',
        'Try: Install / Repair -> Start desktop -> Open browser -> Refresh screen',
    ]
    y_value = 110
    for line in lines:
        draw.text((90, y_value), line, fill='#f8fafc' if line else '#111827', font=font)
        y_value += 34

    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()



def capture_screen_bytes():
    paths = ensure_state_dirs()
    ensure_xvfb_running()
    capture_path = os.path.join(paths['captures_dir'], 'current-screen.png')
    capture_result = run_list(
        ['scrot', '-D', DISPLAY_VALUE, '--overwrite', '--silent', '--file', capture_path],
        timeout=45,
    )
    if not capture_result['ok'] or not os.path.exists(capture_path):
        import_result = run_shell('import -display ' + DISPLAY_VALUE + ' -window root ' + capture_path + ' || true', timeout=45)
        if not os.path.exists(capture_path):
            message = (capture_result.get('stderr') or capture_result.get('stdout') or import_result.get('stderr') or 'No capture output file produced').strip()
            return _fallback_capture_image(message)

    try:
        with open(capture_path, 'rb') as handle:
            return handle.read()
    except Exception as exc:
        return _fallback_capture_image(str(exc))



def sanitize_file_name(name_value):
    cleaned = re.sub(r'[^A-Za-z0-9._ -]+', '_', (name_value or '').strip())
    cleaned = cleaned.strip('. ').strip() or 'downloaded_file'
    return cleaned[:180]



def list_download_files():
    paths = ensure_state_dirs()
    items = []
    for item_name in sorted(os.listdir(paths['downloads_dir'])):
        path_value = os.path.join(paths['downloads_dir'], item_name)
        try:
            stat_value = os.stat(path_value)
        except Exception:
            continue
        items.append({
            'name': item_name,
            'path': path_value,
            'is_dir': os.path.isdir(path_value),
            'size': stat_value.st_size,
            'size_text': human_size(stat_value.st_size),
            'mtime': stat_value.st_mtime,
            'mtime_text': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat_value.st_mtime)),
        })
    items.sort(key=lambda item: item['mtime'], reverse=True)
    return items



def list_download_files_html():
    files = list_download_files()
    if not files:
        return '<div style="padding:10px 12px;border:1px dashed #334155;border-radius:12px;color:#94a3b8;">No files saved yet.</div>'
    parts = ['<div style="display:grid;gap:8px;">']
    for item in files[:40]:
        icon = '📁' if item['is_dir'] else '📄'
        parts.append(
            '<div style="padding:10px 12px;border:1px solid #1e293b;border-radius:12px;background:#020617;color:#e2e8f0;">'
            + icon + ' <b>' + html.escape(item['name']) + '</b>'
            + '<div style="font-size:12px;color:#94a3b8;margin-top:4px;">' + html.escape(item['size_text']) + ' • ' + html.escape(item['mtime_text']) + '</div>'
            + '</div>'
        )
    parts.append('</div>')
    return ''.join(parts)



def _guess_file_name_from_url(url_value):
    parsed = urlparse(url_value)
    name_value = unquote(os.path.basename(parsed.path or '')).strip()
    if not name_value:
        name_value = 'downloaded_file'
    return sanitize_file_name(name_value)



def download_file(url_value, file_name=''):
    paths = ensure_state_dirs()
    url_value = (url_value or '').strip()
    if not url_value:
        return {'ok': False, 'message': 'No URL provided'}

    target_name = sanitize_file_name(file_name or _guess_file_name_from_url(url_value))
    target_path = os.path.join(paths['downloads_dir'], target_name)

    if requests is not None:
        try:
            response = requests.get(url_value, stream=True, timeout=180)
            response.raise_for_status()
            content_disposition = response.headers.get('content-disposition', '')
            match = re.search(r'filename="?([^";]+)"?', content_disposition)
            if match and not file_name:
                target_name = sanitize_file_name(match.group(1))
                target_path = os.path.join(paths['downloads_dir'], target_name)
            with open(target_path, 'wb') as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)
            append_log('downloads.log', 'downloaded ' + url_value + ' -> ' + target_path)
            return {'ok': True, 'path': target_path, 'name': target_name}
        except Exception as exc:
            append_log('downloads.log', 'requests download failed: ' + str(exc))

    shell_result = run_shell('wget -O ' + subprocess.list2cmdline([target_path]) + ' ' + subprocess.list2cmdline([url_value]), timeout=3600)
    return {'ok': shell_result['ok'], 'path': target_path, 'name': target_name, 'result': shell_result}



def extract_archive(file_name):
    paths = ensure_state_dirs()
    source_path = os.path.join(paths['downloads_dir'], file_name)
    if not os.path.exists(source_path):
        return {'ok': False, 'message': 'File not found'}

    base_name = re.sub(r'(\.tar\.gz|\.tar\.xz|\.tar\.bz2|\.zip|\.7z|\.tar|\.gz)$', '', os.path.basename(source_path), flags=re.IGNORECASE)
    target_dir = os.path.join(paths['downloads_dir'], sanitize_file_name(base_name) + '_extracted')
    os.makedirs(target_dir, exist_ok=True)

    lower = source_path.lower()
    if lower.endswith('.zip'):
        with zipfile.ZipFile(source_path, 'r') as archive:
            archive.extractall(target_dir)
        return {'ok': True, 'target_dir': target_dir}

    result = run_shell('7z x -y -o' + subprocess.list2cmdline([target_dir]) + ' ' + subprocess.list2cmdline([source_path]), timeout=3600)
    if result['ok']:
        return {'ok': True, 'target_dir': target_dir, 'result': result}

    tar_result = run_shell('tar -xf ' + subprocess.list2cmdline([source_path]) + ' -C ' + subprocess.list2cmdline([target_dir]), timeout=3600)
    return {'ok': tar_result['ok'], 'target_dir': target_dir, 'result': tar_result}



def run_downloaded_file(file_name):
    paths = ensure_state_dirs()
    target_path = os.path.join(paths['downloads_dir'], file_name)
    if not os.path.exists(target_path):
        return {'ok': False, 'message': 'Target does not exist'}

    lower_name = target_path.lower()
    if os.path.isdir(target_path):
        return launch_file_manager(target_path)

    if lower_name.endswith(('.zip', '.7z', '.tar', '.tar.gz', '.tar.xz', '.tar.bz2', '.gz')):
        return extract_archive(file_name)

    if lower_name.endswith(('.appimage', '.sh', '.run')):
        try:
            os.chmod(target_path, 0o755)
        except Exception:
            pass
        env = {}
        if lower_name.endswith('.appimage'):
            env['APPIMAGE_EXTRACT_AND_RUN'] = '1'
        run_background(['sh', '-lc', subprocess.list2cmdline([target_path])], log_name='apps.log', cwd=os.path.dirname(target_path), env=env)
        return {'ok': True, 'path': target_path, 'mode': 'executable'}

    opener = available_command(['xdg-open', 'gio'])
    opener_name = os.path.basename(opener) if opener else ''
    if opener_name == 'gio':
        run_background(['gio', 'open', target_path], log_name='apps.log')
    elif opener:
        run_background([opener, target_path], log_name='apps.log')
    else:
        run_background(['sh', '-lc', subprocess.list2cmdline([target_path])], log_name='apps.log', cwd=os.path.dirname(target_path))
    return {'ok': True, 'path': target_path, 'mode': 'open'}



def zip_downloads(zip_name='downloads_bundle.zip'):
    paths = ensure_state_dirs()
    zip_name = sanitize_file_name(zip_name)
    if not zip_name.lower().endswith('.zip'):
        zip_name += '.zip'
    target_path = os.path.join(paths['downloads_dir'], zip_name)
    with zipfile.ZipFile(target_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for item in list_download_files():
            if os.path.abspath(item['path']) == os.path.abspath(target_path):
                continue
            if item['is_dir']:
                for root_value, _, file_names in os.walk(item['path']):
                    for file_name in file_names:
                        full_path = os.path.join(root_value, file_name)
                        rel_path = os.path.relpath(full_path, paths['downloads_dir'])
                        archive.write(full_path, rel_path)
            else:
                archive.write(item['path'], item['name'])
    return target_path



def github_headers(token_value):
    return {
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token_value,
        'X-GitHub-Api-Version': '2022-11-28',
    }



def github_request(method_value, url_value, token_value, json_body=None):
    if requests is None:
        raise RuntimeError('requests is required for GitHub operations')
    response = requests.request(method_value, url_value, headers=github_headers(token_value), json=json_body, timeout=180)
    text_value = response.text or ''
    try:
        payload = response.json() if text_value else {}
    except Exception:
        payload = {'message': text_value}
    if response.status_code >= 400:
        raise RuntimeError((payload.get('message') or (str(response.status_code) + ' GitHub API error')).strip())
    return payload



def github_validate_token(token_value):
    payload = github_request('GET', 'https://api.github.com/user', token_value)
    return {
        'ok': True,
        'login': payload.get('login', ''),
        'name': payload.get('name', ''),
    }



def github_check_repo_access(token_value, owner_value, repo_value):
    payload = github_request('GET', 'https://api.github.com/repos/' + owner_value + '/' + repo_value, token_value)
    permissions = payload.get('permissions') or {}
    return {
        'ok': True,
        'full_name': payload.get('full_name', ''),
        'default_branch': payload.get('default_branch', ''),
        'permissions': permissions,
    }



def github_get_file_sha(token_value, owner_value, repo_value, path_value, branch_value):
    url_value = 'https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}'.format(
        owner=owner_value,
        repo=repo_value,
        path=quote(path_value),
        branch=quote(branch_value),
    )
    if requests is None:
        raise RuntimeError('requests is required for GitHub operations')
    response = requests.get(url_value, headers=github_headers(token_value), timeout=180)
    if response.status_code == 404:
        return None
    payload = response.json()
    if response.status_code >= 400:
        raise RuntimeError((payload.get('message') or 'GitHub lookup failed').strip())
    return payload.get('sha')



def github_upsert_file(token_value, owner_value, repo_value, branch_value, path_value, content_value, commit_message='Update file'):
    sha_value = github_get_file_sha(token_value, owner_value, repo_value, path_value, branch_value)
    encoded = base64.b64encode(content_value.encode('utf-8')).decode('ascii')
    body = {
        'message': commit_message,
        'content': encoded,
        'branch': branch_value,
    }
    if sha_value:
        body['sha'] = sha_value
    url_value = 'https://api.github.com/repos/{owner}/{repo}/contents/{path}'.format(
        owner=owner_value,
        repo=repo_value,
        path=quote(path_value),
    )
    payload = github_request('PUT', url_value, token_value, json_body=body)
    return {
        'ok': True,
        'path': path_value,
        'sha': ((payload.get('content') or {}).get('sha') if isinstance(payload, dict) else ''),
    }



def github_upsert_many(token_value, owner_value, repo_value, branch_value, file_map, prefix=''):
    results = []
    prefix_value = (prefix or '').strip('/ ')
    for path_name, content_value in file_map.items():
        final_path = '/'.join(part for part in [prefix_value, path_name] if part)
        results.append(
            github_upsert_file(
                token_value,
                owner_value,
                repo_value,
                branch_value,
                final_path,
                content_value,
                commit_message='Update ' + final_path + ' from Zorin Kaggle desktop pack',
            )
        )
    return results
