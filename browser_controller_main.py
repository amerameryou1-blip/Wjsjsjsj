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
import traceback

import requests
import ipywidgets as widgets
from IPython.display import HTML, display

DEFAULT_OWNER = SUPPORT['DEFAULT_OWNER']
DEFAULT_REPO = SUPPORT['DEFAULT_REPO']
DEFAULT_BRANCH = SUPPORT['DEFAULT_BRANCH']
DEFAULT_PREFIX = SUPPORT['DEFAULT_PREFIX']
DEFAULT_README_PATH = SUPPORT['DEFAULT_README_PATH']
DEFAULT_SUPPORT_PATH = SUPPORT['DEFAULT_SUPPORT_PATH']
DEFAULT_MAIN_PATH = SUPPORT['DEFAULT_MAIN_PATH']
DEFAULT_FULL_PATH = SUPPORT['DEFAULT_FULL_PATH']
DEFAULT_LAUNCHER_PATH = SUPPORT['DEFAULT_LAUNCHER_PATH']
BUNDLE_FILE_ORDER = SUPPORT['BUNDLE_FILE_ORDER']
GOOGLE_HOME_URL = SUPPORT['GOOGLE_HOME_URL']
ANTIGRAVITY_HOME_URL = SUPPORT['ANTIGRAVITY_HOME_URL']
ANTIGRAVITY_DOWNLOAD_URL = SUPPORT['ANTIGRAVITY_DOWNLOAD_URL']
ANTIGRAVITY_DEB_COMMANDS = SUPPORT['ANTIGRAVITY_DEB_COMMANDS']
ANTIGRAVITY_RPM_COMMANDS = SUPPORT['ANTIGRAVITY_RPM_COMMANDS']
ensure_state_dirs = SUPPORT['ensure_state_dirs']
file_read_text = SUPPORT['file_read_text']
file_write_text = SUPPORT['file_write_text']
load_json = SUPPORT['load_json']
save_json = SUPPORT['save_json']
repo_path = SUPPORT['repo_path']
fetch_bundle_files = SUPPORT['fetch_bundle_files']
load_bundle_from_directory = SUPPORT['load_bundle_from_directory']
merge_bundle_maps = SUPPORT['merge_bundle_maps']
bundle_summary_lines = SUPPORT['bundle_summary_lines']
github_validate_token = SUPPORT['github_validate_token']
github_repo_info = SUPPORT['github_repo_info']
github_upload_bundle = SUPPORT['github_upload_bundle']
html_card = SUPPORT['html_card']
html_code_block = SUPPORT['html_code_block']
build_readme_text = SUPPORT['build_readme_text']
now_text = SUPPORT['now_text']

STATE = ensure_state_dirs()
CONFIG_PATH = STATE['config_path']
LOG_PATH = STATE['log_path']
BUNDLE_PATHS = globals().get('__browser_bundle_paths__', {})


def log_line(text_value):
    line = '[' + now_text() + '] ' + str(text_value)
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    except Exception:
        pass


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


def launch_dashboard():
    bundle_store = load_initial_bundle()
    saved = load_json(CONFIG_PATH, {})
    pointer = {'x': 50, 'y': 50}
    action_log = []

    owner_input = widgets.Text(value=str(saved.get('owner') or DEFAULT_OWNER), description='Owner', layout=widgets.Layout(width='260px'))
    repo_input = widgets.Text(value=str(saved.get('repo') or DEFAULT_REPO), description='Repo', layout=widgets.Layout(width='260px'))
    branch_input = widgets.Text(value=str(saved.get('branch') or DEFAULT_BRANCH), description='Branch', layout=widgets.Layout(width='220px'))
    prefix_input = widgets.Text(value=str(saved.get('prefix') or DEFAULT_PREFIX), description='Prefix', layout=widgets.Layout(width='260px'))
    token_input = widgets.Password(value='', description='GitHub key', placeholder='Paste token here', layout=widgets.Layout(width='540px'))
    commit_input = widgets.Text(value=str(saved.get('commit_message') or 'Upload simple Linux controller bundle'), description='Commit', layout=widgets.Layout(width='540px'))
    google_query_input = widgets.Text(value='google antigravity linux', description='Google', layout=widgets.Layout(width='540px'))
    linux_selector = widgets.ToggleButtons(
        options=[('Debian / Ubuntu', 'deb'), ('Fedora / RHEL / SUSE', 'rpm')],
        value=str(saved.get('linux_target') or 'deb'),
        description='Linux',
        layout=widgets.Layout(width='520px'),
    )

    validate_button = widgets.Button(description='Validate key', button_style='info', icon='check')
    upload_button = widgets.Button(description='Upload bundle to GitHub', button_style='success', icon='upload')
    refetch_button = widgets.Button(description='Refetch repo files', button_style='primary', icon='refresh')
    google_button = widgets.Button(description='Open Google', button_style='', icon='globe')
    antigravity_button = widgets.Button(description='Open Antigravity', button_style='', icon='rocket')

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
    selected_file = DEFAULT_LAUNCHER_PATH if DEFAULT_LAUNCHER_PATH in available_files else available_files[0]
    file_selector = widgets.Dropdown(options=available_files, value=selected_file, description='File', layout=widgets.Layout(width='360px'))
    file_preview = widgets.Textarea(
        value=bundle_store.get(selected_file, {}).get('content', ''),
        layout=widgets.Layout(width='100%', height='420px'),
    )

    intro_html = widgets.HTML()
    status_html = widgets.HTML()
    files_html = widgets.HTML()
    mouse_html = widgets.HTML()
    log_html = widgets.HTML()
    linux_html = widgets.HTML()
    links_html = widgets.HTML()

    current_name = {'value': selected_file}

    def save_settings():
        save_json(CONFIG_PATH, {
            'owner': owner_input.value.strip(),
            'repo': repo_input.value.strip(),
            'branch': branch_input.value.strip(),
            'prefix': prefix_input.value.strip(),
            'commit_message': commit_input.value.strip(),
            'linux_target': linux_selector.value,
        })

    def set_status(title_text, lines, accent='#22c55e'):
        status_html.value = html_card(title_text, lines, accent)
        log_line(title_text + ' | ' + ' | '.join(str(line) for line in lines))

    def refresh_intro():
        owner_value = owner_input.value.strip() or DEFAULT_OWNER
        repo_value = repo_input.value.strip() or DEFAULT_REPO
        branch_value = branch_input.value.strip() or DEFAULT_BRANCH
        prefix_value = prefix_input.value.strip()
        launcher_path = repo_path(prefix_value, DEFAULT_LAUNCHER_PATH)
        launcher_url = 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + launcher_path
        intro_html.value = html_card('Simple flow', [
            '1. Paste your GitHub key.',
            '2. Click Upload bundle to GitHub.',
            '3. Copy kaggle_launcher.py from the website.',
            '4. Paste it into one Kaggle cell and run it.',
            'Launcher raw URL: ' + launcher_url,
        ], '#38bdf8')

    def refresh_files_html():
        files_html.value = html_card('Loaded files', bundle_summary_lines(bundle_store), '#8b5cf6')

    def refresh_linux_html():
        command_text = ANTIGRAVITY_DEB_COMMANDS if linux_selector.value == 'deb' else ANTIGRAVITY_RPM_COMMANDS
        linux_html.value = html_card('Linux install commands', [
            'Use the commands below on Linux.',
            'Debian/Ubuntu = deb.',
            'Fedora/RHEL/SUSE = rpm.',
            'Official page: ' + ANTIGRAVITY_DOWNLOAD_URL,
        ], '#f59e0b') + html_code_block(command_text)

    def refresh_mouse_html():
        mouse_html.value = html_card('Mouse control pad', [
            'Pointer X: ' + str(pointer['x']),
            'Pointer Y: ' + str(pointer['y']),
            'Use the arrows and click buttons below.',
        ], '#06b6d4')

    def refresh_log_html():
        if not action_log:
            lines = ['No control actions yet.']
        else:
            lines = action_log[-10:][::-1]
        log_html.value = html_card('Action log', lines, '#14b8a6')

    def refresh_links_html(message='Quick links are here for Google and Antigravity.'):
        links_html.value = html_card('Quick links', [
            message,
            'Google: ' + GOOGLE_HOME_URL,
            'Antigravity: ' + ANTIGRAVITY_DOWNLOAD_URL,
        ], '#f97316')

    def ensure_current_file_saved():
        name = current_name['value']
        if not name:
            return
        if name not in bundle_store:
            bundle_store[name] = {
                'name': name,
                'repo_path': name,
                'url': '',
                'local_path': os.path.join(STATE['bundle_dir'], name),
                'content': '',
            }
        bundle_store[name]['content'] = file_preview.value
        local_path = bundle_store[name].get('local_path') or os.path.join(STATE['bundle_dir'], name)
        bundle_store[name]['local_path'] = local_path
        file_write_text(local_path, file_preview.value)

    def select_file(name):
        current_name['value'] = name
        file_preview.value = bundle_store.get(name, {}).get('content', '')

    def update_file_options():
        options = [name for name in BUNDLE_FILE_ORDER if name in bundle_store] or BUNDLE_FILE_ORDER[:]
        file_selector.options = options
        if current_name['value'] not in options:
            current_name['value'] = options[0]
        file_selector.value = current_name['value']

    def add_action(text_value):
        action_log.append(now_text() + ' - ' + str(text_value))
        refresh_log_html()

    def move_pointer(dx, dy, action_name):
        pointer['x'] = max(0, min(100, pointer['x'] + dx))
        pointer['y'] = max(0, min(100, pointer['y'] + dy))
        add_action(action_name + ' -> (' + str(pointer['x']) + ', ' + str(pointer['y']) + ')')
        refresh_mouse_html()

    def collect_bundle_for_upload():
        ensure_current_file_saved()
        owner_value = owner_input.value.strip() or DEFAULT_OWNER
        repo_value = repo_input.value.strip() or DEFAULT_REPO
        branch_value = branch_input.value.strip() or DEFAULT_BRANCH
        prefix_value = prefix_input.value.strip()
        if DEFAULT_README_PATH not in bundle_store or not bundle_store[DEFAULT_README_PATH].get('content', '').strip():
            readme_text = build_readme_text(owner_value, repo_value, branch_value, prefix_value)
            readme_path = os.path.join(STATE['bundle_dir'], DEFAULT_README_PATH)
            file_write_text(readme_path, readme_text)
            bundle_store[DEFAULT_README_PATH] = {
                'name': DEFAULT_README_PATH,
                'repo_path': repo_path(prefix_value, DEFAULT_README_PATH),
                'url': '',
                'local_path': readme_path,
                'content': readme_text,
            }
        return bundle_store

    def handle_validate(_):
        token_value = token_input.value.strip()
        if not token_value:
            set_status('Missing GitHub key', ['Paste your GitHub key first.'], '#ef4444')
            return
        save_settings()
        try:
            user_data = github_validate_token(requests, token_value)
            repo_data = github_repo_info(requests, token_value, owner_input.value.strip() or DEFAULT_OWNER, repo_input.value.strip() or DEFAULT_REPO)
            set_status('GitHub key works', [
                'User: ' + (user_data.get('login') or '(unknown)'),
                'Repo: ' + repo_data.get('full_name', ''),
                'Push access: ' + ('yes' if repo_data.get('can_push') else 'no'),
            ], '#22c55e')
        except Exception as exc:
            set_status('Validation failed', [str(exc)], '#ef4444')

    def handle_upload(_):
        token_value = token_input.value.strip()
        if not token_value:
            set_status('Missing GitHub key', ['Paste your GitHub key first.'], '#ef4444')
            return
        save_settings()
        try:
            bundle_map = collect_bundle_for_upload()
            results = github_upload_bundle(
                requests,
                token_value,
                owner_input.value.strip() or DEFAULT_OWNER,
                repo_input.value.strip() or DEFAULT_REPO,
                branch_input.value.strip() or DEFAULT_BRANCH,
                prefix_input.value.strip(),
                bundle_map,
                commit_input.value.strip() or 'Upload simple Linux controller bundle',
            )
            refresh_files_html()
            set_status('Upload complete', [
                'Uploaded ' + str(len(results)) + ' files.',
                'Next: copy kaggle_launcher.py from the website and run it in Kaggle.',
            ], '#22c55e')
        except Exception as exc:
            set_status('Upload failed', [str(exc)], '#ef4444')
            traceback.print_exc()

    def handle_refetch(_):
        save_settings()
        try:
            fetched = fetch_bundle_files(
                requests,
                owner_input.value.strip() or DEFAULT_OWNER,
                repo_input.value.strip() or DEFAULT_REPO,
                branch_input.value.strip() or DEFAULT_BRANCH,
                prefix_input.value.strip(),
                BUNDLE_FILE_ORDER,
                STATE['bundle_dir'],
            )
            for key, value in fetched.items():
                bundle_store[key] = value
            update_file_options()
            select_file(file_selector.value)
            refresh_files_html()
            set_status('Refetch complete', ['Bundle files were fetched from the repository again.'], '#22c55e')
        except Exception as exc:
            set_status('Refetch failed', [str(exc)], '#ef4444')

    def handle_google(_):
        query_value = google_query_input.value.strip()
        if query_value:
            url_value = GOOGLE_HOME_URL + 'search?q=' + requests.utils.quote(query_value)
        else:
            url_value = GOOGLE_HOME_URL
        open_url(url_value)
        refresh_links_html('Google button opened a new tab.')
        add_action('Opened Google')

    def handle_antigravity(_):
        open_url(ANTIGRAVITY_DOWNLOAD_URL)
        refresh_links_html('Antigravity button opened a new tab.')
        add_action('Opened Antigravity Linux page')

    def handle_file_change(change):
        if change.get('name') != 'value':
            return
        ensure_current_file_saved()
        select_file(change['new'])

    file_selector.observe(handle_file_change, names='value')
    validate_button.on_click(handle_validate)
    upload_button.on_click(handle_upload)
    refetch_button.on_click(handle_refetch)
    google_button.on_click(handle_google)
    antigravity_button.on_click(handle_antigravity)
    up_button.on_click(lambda _: move_pointer(0, -8, 'Move up'))
    left_button.on_click(lambda _: move_pointer(-8, 0, 'Move left'))
    right_button.on_click(lambda _: move_pointer(8, 0, 'Move right'))
    down_button.on_click(lambda _: move_pointer(0, 8, 'Move down'))
    left_click_button.on_click(lambda _: add_action('Left click'))
    right_click_button.on_click(lambda _: add_action('Right click'))
    double_click_button.on_click(lambda _: add_action('Double click'))
    scroll_up_button.on_click(lambda _: add_action('Scroll up'))
    scroll_down_button.on_click(lambda _: add_action('Scroll down'))

    refresh_intro()
    refresh_files_html()
    refresh_linux_html()
    refresh_mouse_html()
    refresh_log_html()
    refresh_links_html()
    set_status('Dashboard ready', [
        'This is the simple Kaggle interface.',
        'Paste your GitHub key, upload, then use the launcher.',
    ], '#22c55e')

    root = widgets.VBox([
        intro_html,
        status_html,
        widgets.HBox([owner_input, repo_input, branch_input, prefix_input]),
        token_input,
        commit_input,
        widgets.HBox([validate_button, upload_button, refetch_button]),
        google_query_input,
        widgets.HBox([google_button, antigravity_button]),
        linux_selector,
        linux_html,
        widgets.HBox([widgets.Label('Mouse pad:'), up_button, left_button, right_button, down_button]),
        widgets.HBox([left_click_button, right_click_button, double_click_button, scroll_up_button, scroll_down_button]),
        mouse_html,
        log_html,
        links_html,
        files_html,
        file_selector,
        file_preview,
    ], layout=widgets.Layout(width='100%'))

    display(root)


if __name__ == '__main__':
    launch_dashboard()
