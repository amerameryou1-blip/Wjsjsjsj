SUPPORT = globals().get('__browser_support__')
if not SUPPORT:
    import browser_controller_support as support_module
    SUPPORT = {
        name: getattr(support_module, name)
        for name in dir(support_module)
        if not name.startswith('__')
    }

import os
import json

import requests
import ipywidgets as widgets
from IPython.display import HTML, display

DEFAULT_OWNER = SUPPORT['DEFAULT_OWNER']
DEFAULT_REPO = SUPPORT['DEFAULT_REPO']
DEFAULT_BRANCH = SUPPORT['DEFAULT_BRANCH']
DEFAULT_PREFIX = SUPPORT['DEFAULT_PREFIX']
DEFAULT_README_PATH = SUPPORT['DEFAULT_README_PATH']
DEFAULT_LAUNCHER_PATH = SUPPORT['DEFAULT_LAUNCHER_PATH']
BUNDLE_FILE_ORDER = SUPPORT['BUNDLE_FILE_ORDER']
GOOGLE_HOME_URL = SUPPORT['GOOGLE_HOME_URL']
ANTIGRAVITY_DOWNLOAD_URL = SUPPORT['ANTIGRAVITY_DOWNLOAD_URL']
ANTIGRAVITY_DEB_COMMANDS = SUPPORT['ANTIGRAVITY_DEB_COMMANDS']
ANTIGRAVITY_RPM_COMMANDS = SUPPORT['ANTIGRAVITY_RPM_COMMANDS']
ensure_state_dirs = SUPPORT['ensure_state_dirs']
file_read_text = SUPPORT['file_read_text']
load_json = SUPPORT['load_json']
save_json = SUPPORT['save_json']
repo_path = SUPPORT['repo_path']
fetch_bundle_files = SUPPORT['fetch_bundle_files']
load_bundle_from_directory = SUPPORT['load_bundle_from_directory']
merge_bundle_maps = SUPPORT['merge_bundle_maps']
bundle_summary_lines = SUPPORT['bundle_summary_lines']
html_card = SUPPORT['html_card']
html_code_block = SUPPORT['html_code_block']
build_readme_text = SUPPORT['build_readme_text']
now_text = SUPPORT['now_text']

STATE = ensure_state_dirs()
CONFIG_PATH = STATE['config_path']
BUNDLE_PATHS = globals().get('__browser_bundle_paths__', {})


def open_url(url_value):
    safe_url = json.dumps(str(url_value))
    display(HTML('<script>window.open(' + safe_url + ', "_blank")</script>'))


def load_initial_bundle():
    from_paths = {}
    for file_name, local_path in (BUNDLE_PATHS or {}).items():
        if os.path.exists(local_path):
            from_paths[file_name] = {
                'name': file_name,
                'repo_path': file_name,
                'url': '',
                'local_path': local_path,
                'content': file_read_text(local_path),
            }
    from_cache = load_bundle_from_directory(STATE['bundle_dir'], BUNDLE_FILE_ORDER)
    from_cwd = load_bundle_from_directory(os.getcwd(), BUNDLE_FILE_ORDER)
    return merge_bundle_maps(from_cwd, from_cache, from_paths)


def render_screen_html(pointer, action_text, linux_target):
    left = max(0, min(100, int(pointer['x'])))
    top = max(0, min(100, int(pointer['y'])))
    distro_label = 'Debian / Ubuntu' if linux_target == 'deb' else 'Fedora / RHEL / SUSE'
    return (
        '<div style="margin-top:12px;border:1px solid rgba(255,255,255,0.12);border-radius:24px;overflow:hidden;background:#020617;color:#fff;">'
        '<div style="padding:12px 16px;background:rgba(255,255,255,0.05);border-bottom:1px solid rgba(255,255,255,0.08);font-size:12px;color:#cbd5e1;">live-control-screen</div>'
        '<div style="padding:18px;">'
        '<div style="padding:14px 16px;border:1px solid rgba(255,255,255,0.08);border-radius:18px;background:rgba(255,255,255,0.05);">'
        '<div style="font-size:13px;color:#67e8f9;text-transform:uppercase;letter-spacing:.16em;">Visible screen</div>'
        '<div style="font-size:16px;margin-top:8px;color:#e2e8f0;">This is the simple interface running inside Kaggle.</div>'
        '</div>'
        '<div style="position:relative;margin-top:16px;height:320px;border-radius:22px;overflow:hidden;border:1px solid rgba(255,255,255,0.1);background:linear-gradient(135deg, rgba(8,47,73,.7), rgba(15,23,42,.98));">'
        '<div style="position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.05) 1px, transparent 1px),linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px);background-size:34px 34px;"></div>'
        '<div style="position:relative;z-index:1;padding:18px;height:100%;display:flex;flex-direction:column;justify-content:space-between;">'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
        '<div style="padding:14px;border-radius:18px;background:rgba(2,6,23,.62);border:1px solid rgba(255,255,255,.08);">'
        '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.16em;color:#94a3b8;">Last action</div>'
        '<div style="margin-top:8px;font-size:18px;font-weight:800;">' + str(action_text) + '</div>'
        '</div>'
        '<div style="padding:14px;border-radius:18px;background:rgba(2,6,23,.62);border:1px solid rgba(255,255,255,.08);">'
        '<div style="font-size:11px;text-transform:uppercase;letter-spacing:.16em;color:#94a3b8;">Linux</div>'
        '<div style="margin-top:8px;font-size:18px;font-weight:800;">' + distro_label + '</div>'
        '</div>'
        '</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">'
        '<div style="padding:12px;border-radius:18px;background:rgba(255,255,255,.08);text-align:center;">Google</div>'
        '<div style="padding:12px;border-radius:18px;background:rgba(255,255,255,.08);text-align:center;">Kaggle</div>'
        '<div style="padding:12px;border-radius:18px;background:rgba(255,255,255,.08);text-align:center;">Antigravity</div>'
        '</div>'
        '<div style="position:absolute;width:18px;height:18px;border-radius:999px;background:#22d3ee;border:2px solid #fff;box-shadow:0 0 24px rgba(34,211,238,.95);left:calc(' + str(left) + '% - 9px);top:calc(' + str(top) + '% - 9px);"></div>'
        '</div>'
        '</div>'
        '</div>'
    )


def launch_dashboard():
    bundle_store = load_initial_bundle()
    saved = load_json(CONFIG_PATH, {})
    pointer = {
        'x': int(saved.get('pointer_x', 42) or 42),
        'y': int(saved.get('pointer_y', 45) or 45),
    }
    linux_target = {'value': str(saved.get('linux_target') or 'deb')}
    actions = ['Dashboard ready.']

    intro_html = widgets.HTML()
    status_html = widgets.HTML()
    screen_html = widgets.HTML()
    files_html = widgets.HTML()
    linux_html = widgets.HTML()
    log_html = widgets.HTML()

    refetch_button = widgets.Button(description='Refetch bundle', button_style='info', layout=widgets.Layout(width='180px'))
    google_button = widgets.Button(description='Open Google', layout=widgets.Layout(width='160px'))
    kaggle_button = widgets.Button(description='Open Kaggle', layout=widgets.Layout(width='160px'))
    antigravity_button = widgets.Button(description='Open Antigravity', layout=widgets.Layout(width='180px'))

    distro_buttons = widgets.ToggleButtons(
        options=[('Debian / Ubuntu', 'deb'), ('Fedora / RHEL / SUSE', 'rpm')],
        value=linux_target['value'],
        description='Linux',
        layout=widgets.Layout(width='520px'),
    )

    up_button = widgets.Button(description='↑', layout=widgets.Layout(width='64px'))
    left_button = widgets.Button(description='←', layout=widgets.Layout(width='64px'))
    right_button = widgets.Button(description='→', layout=widgets.Layout(width='64px'))
    down_button = widgets.Button(description='↓', layout=widgets.Layout(width='64px'))
    left_click_button = widgets.Button(description='Left click', layout=widgets.Layout(width='110px'))
    right_click_button = widgets.Button(description='Right click', layout=widgets.Layout(width='110px'))
    double_click_button = widgets.Button(description='Double click', layout=widgets.Layout(width='110px'))
    scroll_up_button = widgets.Button(description='Scroll up', layout=widgets.Layout(width='110px'))
    scroll_down_button = widgets.Button(description='Scroll down', layout=widgets.Layout(width='110px'))

    available_files = [name for name in BUNDLE_FILE_ORDER if name in bundle_store] or BUNDLE_FILE_ORDER[:]
    selected_file = {'value': DEFAULT_LAUNCHER_PATH if DEFAULT_LAUNCHER_PATH in available_files else available_files[0]}
    file_selector = widgets.Dropdown(options=available_files, value=selected_file['value'], description='File', layout=widgets.Layout(width='360px'))
    file_preview = widgets.Textarea(value=bundle_store.get(selected_file['value'], {}).get('content', ''), layout=widgets.Layout(width='100%', height='420px'))

    def save_settings():
        save_json(CONFIG_PATH, {
            'pointer_x': pointer['x'],
            'pointer_y': pointer['y'],
            'linux_target': linux_target['value'],
        })

    def set_status(title_text, lines, accent='#22d3ee'):
        status_html.value = html_card(title_text, lines, accent)

    def add_action(text_value):
        actions.append(now_text() + ' - ' + str(text_value))
        refresh_log()
        refresh_screen()
        save_settings()

    def refresh_intro():
        launcher_url = 'https://raw.githubusercontent.com/' + DEFAULT_OWNER + '/' + DEFAULT_REPO + '/' + DEFAULT_BRANCH + '/' + repo_path(DEFAULT_PREFIX, DEFAULT_LAUNCHER_PATH)
        intro_html.value = html_card('Simple Kaggle flow', [
            'The website uploads the bundle for you.',
            'This dashboard is what opens after you paste the launcher into Kaggle.',
            'Launcher URL: ' + launcher_url,
        ], '#67e8f9')

    def refresh_files():
        files_html.value = html_card('Loaded bundle files', bundle_summary_lines(bundle_store), '#a78bfa')

    def refresh_linux():
        command_text = ANTIGRAVITY_DEB_COMMANDS if linux_target['value'] == 'deb' else ANTIGRAVITY_RPM_COMMANDS
        linux_html.value = html_card('Linux commands', [
            'Use these commands on Linux when you need Antigravity.',
            'Official page: ' + ANTIGRAVITY_DOWNLOAD_URL,
        ], '#f59e0b') + html_code_block(command_text)

    def refresh_screen():
        screen_html.value = render_screen_html(pointer, actions[-1], linux_target['value'])

    def refresh_log():
        log_html.value = html_card('Recent actions', actions[-8:][::-1], '#34d399')

    def select_file(name):
        selected_file['value'] = name
        file_preview.value = bundle_store.get(name, {}).get('content', '')

    def update_file_options():
        options = [name for name in BUNDLE_FILE_ORDER if name in bundle_store] or BUNDLE_FILE_ORDER[:]
        file_selector.options = options
        if selected_file['value'] not in options:
            selected_file['value'] = options[0]
        file_selector.value = selected_file['value']

    def move_pointer(dx, dy, label):
        pointer['x'] = max(0, min(100, pointer['x'] + dx))
        pointer['y'] = max(0, min(100, pointer['y'] + dy))
        add_action(label + ' -> (' + str(pointer['x']) + ', ' + str(pointer['y']) + ')')

    def handle_refetch(_):
        try:
            fetched = fetch_bundle_files(
                requests,
                DEFAULT_OWNER,
                DEFAULT_REPO,
                DEFAULT_BRANCH,
                DEFAULT_PREFIX,
                BUNDLE_FILE_ORDER,
                STATE['bundle_dir'],
            )
            for key, value in fetched.items():
                bundle_store[key] = value
            if DEFAULT_README_PATH not in bundle_store:
                bundle_store[DEFAULT_README_PATH] = {
                    'name': DEFAULT_README_PATH,
                    'repo_path': DEFAULT_README_PATH,
                    'url': '',
                    'local_path': os.path.join(STATE['bundle_dir'], DEFAULT_README_PATH),
                    'content': build_readme_text(DEFAULT_OWNER, DEFAULT_REPO, DEFAULT_BRANCH, DEFAULT_PREFIX),
                }
            update_file_options()
            select_file(file_selector.value)
            refresh_files()
            set_status('Bundle refreshed', ['Latest files downloaded from GitHub.'], '#22c55e')
            add_action('Bundle refreshed from GitHub')
        except Exception as exc:
            set_status('Refetch failed', [str(exc)], '#ef4444')

    def handle_google(_):
        open_url(GOOGLE_HOME_URL)
        add_action('Opened Google')

    def handle_kaggle(_):
        open_url('https://www.kaggle.com/code')
        add_action('Opened Kaggle')

    def handle_antigravity(_):
        open_url(ANTIGRAVITY_DOWNLOAD_URL)
        add_action('Opened Antigravity')

    def handle_distro(change):
        linux_target['value'] = change['new']
        refresh_linux()
        refresh_screen()
        save_settings()

    def handle_file_select(change):
        if change['name'] == 'value' and change['new']:
            select_file(change['new'])

    refetch_button.on_click(handle_refetch)
    google_button.on_click(handle_google)
    kaggle_button.on_click(handle_kaggle)
    antigravity_button.on_click(handle_antigravity)
    distro_buttons.observe(handle_distro, names='value')
    file_selector.observe(handle_file_select, names='value')

    up_button.on_click(lambda _: move_pointer(0, -5, 'Pointer up'))
    left_button.on_click(lambda _: move_pointer(-5, 0, 'Pointer left'))
    right_button.on_click(lambda _: move_pointer(5, 0, 'Pointer right'))
    down_button.on_click(lambda _: move_pointer(0, 5, 'Pointer down'))
    left_click_button.on_click(lambda _: add_action('Left click'))
    right_click_button.on_click(lambda _: add_action('Right click'))
    double_click_button.on_click(lambda _: add_action('Double click'))
    scroll_up_button.on_click(lambda _: add_action('Scroll up'))
    scroll_down_button.on_click(lambda _: add_action('Scroll down'))

    refresh_intro()
    refresh_files()
    refresh_linux()
    refresh_screen()
    refresh_log()
    set_status('Dashboard ready', ['Visible screen loaded.', 'Use the buttons below to move the pointer or open quick links.'], '#22c55e')

    controls_row_1 = widgets.HBox([refetch_button, google_button, kaggle_button, antigravity_button])
    pointer_row_1 = widgets.HBox([widgets.HTML('<div style="width:64px"></div>'), up_button, widgets.HTML('<div style="width:64px"></div>')])
    pointer_row_2 = widgets.HBox([left_button, down_button, right_button])
    click_row = widgets.HBox([left_click_button, right_click_button, double_click_button, scroll_up_button, scroll_down_button])

    display(widgets.VBox([
        intro_html,
        status_html,
        screen_html,
        controls_row_1,
        distro_buttons,
        linux_html,
        pointer_row_1,
        pointer_row_2,
        click_row,
        log_html,
        files_html,
        widgets.HBox([file_selector]),
        file_preview,
    ]))


if __name__ == '__main__':
    launch_dashboard()
