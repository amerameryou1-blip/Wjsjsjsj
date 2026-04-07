SUPPORT = globals().get('__browser_support__')
if not SUPPORT:
    import browser_controller_support as support_module
    SUPPORT = {
        name: getattr(support_module, name)
        for name in dir(support_module)
        if not name.startswith('__')
    }

import os
import html
import traceback

import requests
import ipywidgets as widgets
from IPython.display import display

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
ANTIGRAVITY_DOWNLOAD_URL = SUPPORT['ANTIGRAVITY_DOWNLOAD_URL']
ANTIGRAVITY_HOME_URL = SUPPORT['ANTIGRAVITY_HOME_URL']
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
github_check_repo_access = SUPPORT['github_check_repo_access']
github_upsert_many = SUPPORT['github_upsert_many']
html_card = SUPPORT['html_card']
html_code_block = SUPPORT['html_code_block']
build_readme_text = SUPPORT['build_readme_text']
now_text = SUPPORT['now_text']

STATE = ensure_state_dirs()
CONFIG_PATH = STATE['config_path']
LOG_PATH = os.path.join(STATE['logs_dir'], 'dashboard.log')
BUNDLE_PATHS = globals().get('__browser_bundle_paths__', {})


def log_line(text_value):
    line = '[' + now_text() + '] ' + text_value
    print(line)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    except Exception:
        pass


def load_initial_bundle():
    bundle_from_paths = {}
    for file_name, local_path in BUNDLE_PATHS.items():
        if not os.path.exists(local_path):
            continue
        bundle_from_paths[file_name] = {
            'name': file_name,
            'repo_path': file_name,
            'url': '',
            'local_path': local_path,
            'content': file_read_text(local_path),
        }
    bundle_from_cache = load_bundle_from_directory(STATE['bundle_dir'], BUNDLE_FILE_ORDER)
    bundle_from_cwd = load_bundle_from_directory(os.getcwd(), BUNDLE_FILE_ORDER)
    return merge_bundle_maps(bundle_from_cwd, bundle_from_cache, bundle_from_paths)


def build_intro_html(owner_value, repo_value, branch_value, prefix_value):
    prefix_clean = prefix_value.strip('/')
    launcher_path = repo_path(prefix_value, DEFAULT_LAUNCHER_PATH)
    launcher_raw = 'https://raw.githubusercontent.com/' + owner_value + '/' + repo_value + '/' + branch_value + '/' + launcher_path
    tree_url = 'https://github.com/' + owner_value + '/' + repo_value + '/tree/' + branch_value
    lines = [
        'Step 1: upload the bundle files to GitHub from the website or from the form below.',
        'Step 2: copy kaggle_launcher.py into one Kaggle notebook cell.',
        'Step 3: run the cell and this dashboard will load from your repository.',
        'Repo tree: ' + tree_url,
        'Raw launcher URL: ' + launcher_raw,
    ]
    return html_card('Kaggle bundle dashboard', lines, '#38bdf8')


def build_file_meta_html(bundle_map):
    lines = []
    for line in bundle_summary_lines(bundle_map):
        lines.append(line)
    if not lines:
        lines = ['No bundle files loaded yet.']
    return html_card('Local bundle cache', lines, '#8b5cf6')


def launch_dashboard():
    bundle_store = load_initial_bundle()
    saved_config = load_json(CONFIG_PATH, {})

    owner_input = widgets.Text(
        value=str(saved_config.get('owner') or DEFAULT_OWNER),
        description='Owner',
        layout=widgets.Layout(width='260px'),
    )
    repo_input = widgets.Text(
        value=str(saved_config.get('repo') or DEFAULT_REPO),
        description='Repo',
        layout=widgets.Layout(width='260px'),
    )
    branch_input = widgets.Text(
        value=str(saved_config.get('branch') or DEFAULT_BRANCH),
        description='Branch',
        layout=widgets.Layout(width='220px'),
    )
    prefix_input = widgets.Text(
        value=str(saved_config.get('prefix') or DEFAULT_PREFIX),
        description='Prefix',
        layout=widgets.Layout(width='260px'),
    )
    token_input = widgets.Password(
        value='',
        description='Token',
        placeholder='Paste GitHub token here',
        layout=widgets.Layout(width='540px'),
    )
    commit_input = widgets.Text(
        value=str(saved_config.get('commit_message') or 'Upload Kaggle bundle from dashboard'),
        description='Commit',
        layout=widgets.Layout(width='540px'),
    )

    validate_button = widgets.Button(description='Validate token', button_style='info', icon='check')
    upload_button = widgets.Button(description='Upload bundle to GitHub', button_style='success', icon='upload')
    refresh_button = widgets.Button(description='Refetch from repo', button_style='primary', icon='refresh')
    antigravity_button = widgets.Button(description='Show Antigravity commands', button_style='', icon='rocket')

    selector_options = [name for name in BUNDLE_FILE_ORDER if name in bundle_store]
    if DEFAULT_LAUNCHER_PATH not in selector_options:
        selector_options = selector_options or BUNDLE_FILE_ORDER
    selected_name = selector_options[0] if selector_options else DEFAULT_LAUNCHER_PATH
    if DEFAULT_LAUNCHER_PATH in selector_options:
        selected_name = DEFAULT_LAUNCHER_PATH

    file_selector = widgets.Dropdown(
        options=selector_options,
        value=selected_name,
        description='File',
        layout=widgets.Layout(width='360px'),
    )
    file_preview = widgets.Textarea(
        value=bundle_store.get(selected_name, {}).get('content', ''),
        layout=widgets.Layout(width='100%', height='520px'),
    )

    intro_html = widgets.HTML()
    status_html = widgets.HTML(value=html_card('Status', ['Dashboard ready. Paste a token to upload or refetch files from the repo.'], '#22c55e'))
    files_html = widgets.HTML()
    output = widgets.Output(layout=widgets.Layout(width='100%'))

    current_file = {'name': selected_name}

    def save_settings():
        save_json(
            CONFIG_PATH,
            {
                'owner': owner_input.value.strip(),
                'repo': repo_input.value.strip(),
                'branch': branch_input.value.strip(),
                'prefix': prefix_input.value.strip(),
                'commit_message': commit_input.value.strip(),
            },
        )

    def refresh_intro():
        intro_html.value = build_intro_html(
            owner_input.value.strip() or DEFAULT_OWNER,
            repo_input.value.strip() or DEFAULT_REPO,
            branch_input.value.strip() or DEFAULT_BRANCH,
            prefix_input.value.strip(),
        )

    def refresh_file_list():
        options = [name for name in BUNDLE_FILE_ORDER if name in bundle_store]
        if not options:
            options = BUNDLE_FILE_ORDER[:]
        file_selector.options = options
        if current_file['name'] not in options:
            current_file['name'] = options[0]
            file_selector.value = options[0]
        files_html.value = build_file_meta_html(bundle_store)

    def persist_current_preview():
        name = current_file['name']
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

    def set_status(title_text, lines, accent='#22c55e'):
        status_html.value = html_card(title_text, lines, accent)
        log_line(title_text + ' | ' + ' | '.join(lines))

    def select_file(name):
        current_file['name'] = name
        file_preview.value = bundle_store.get(name, {}).get('content', '')

    def on_selector_change(change):
        if change.get('name') != 'value':
            return
        persist_current_preview()
        select_file(change['new'])

    def collect_upload_map():
        persist_current_preview()
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
        files_map = {}
        for file_name in BUNDLE_FILE_ORDER:
            item = bundle_store.get(file_name)
            if not item:
                continue
            files_map[repo_path(prefix_value, file_name)] = item.get('content', '')
        return files_map

    def handle_validate(_):
        token_value = token_input.value.strip()
        if not token_value:
            set_status('Missing token', ['Paste a GitHub token first.'], '#ef4444')
            return
        save_settings()
        with output:
            output.clear_output()
        try:
            user_data = github_validate_token(requests, token_value)
            repo_data = github_check_repo_access(
                requests,
                token_value,
                owner_input.value.strip() or DEFAULT_OWNER,
                repo_input.value.strip() or DEFAULT_REPO,
            )
            lines = [
                'Signed in as: ' + (user_data.get('login') or '(unknown)'),
                'Repository: ' + repo_data.get('full_name', ''),
                'Push access: ' + ('yes' if repo_data.get('can_push') else 'no'),
                'Default branch: ' + repo_data.get('default_branch', ''),
            ]
            set_status('GitHub token looks good', lines, '#22c55e')
        except Exception as exc:
            set_status('Token validation failed', [str(exc)], '#ef4444')

    def handle_upload(_):
        token_value = token_input.value.strip()
        if not token_value:
            set_status('Missing token', ['Paste a GitHub token first.'], '#ef4444')
            return
        save_settings()
        owner_value = owner_input.value.strip() or DEFAULT_OWNER
        repo_value = repo_input.value.strip() or DEFAULT_REPO
        branch_value = branch_input.value.strip() or DEFAULT_BRANCH
        try:
            files_map = collect_upload_map()
            if not files_map:
                set_status('Nothing to upload', ['No local bundle files are loaded.'], '#ef4444')
                return
            github_upsert_many(
                requests,
                token_value,
                owner_value,
                repo_value,
                branch_value,
                files_map,
                commit_input.value.strip() or 'Upload Kaggle bundle',
            )
            set_status(
                'Upload complete',
                [
                    'Uploaded ' + str(len(files_map)) + ' files to ' + owner_value + '/' + repo_value,
                    'Branch: ' + branch_value,
                    'Prefix: ' + (prefix_input.value.strip() or '(repo root)'),
                ],
                '#22c55e',
            )
        except Exception as exc:
            set_status('Upload failed', [str(exc)], '#ef4444')
            with output:
                output.clear_output()
                print(traceback.format_exc())

    def handle_refetch(_):
        save_settings()
        owner_value = owner_input.value.strip() or DEFAULT_OWNER
        repo_value = repo_input.value.strip() or DEFAULT_REPO
        branch_value = branch_input.value.strip() or DEFAULT_BRANCH
        prefix_value = prefix_input.value.strip()
        try:
            persist_current_preview()
            fetched = fetch_bundle_files(
                requests,
                owner_value,
                repo_value,
                branch_value,
                prefix_value,
                BUNDLE_FILE_ORDER,
                STATE['bundle_dir'],
            )
            bundle_store.update(fetched)
            refresh_file_list()
            if current_file['name'] in bundle_store:
                select_file(current_file['name'])
            set_status(
                'Bundle refreshed',
                [
                    'Fetched ' + str(len(fetched)) + ' files from GitHub.',
                    'Repo: ' + owner_value + '/' + repo_value,
                    'Branch: ' + branch_value,
                ],
                '#38bdf8',
            )
        except Exception as exc:
            set_status('Refetch failed', [str(exc)], '#ef4444')
            with output:
                output.clear_output()
                print(traceback.format_exc())

    def handle_antigravity(_):
        with output:
            output.clear_output()
            display(widgets.HTML(html_card('Antigravity links', [ANTIGRAVITY_HOME_URL, ANTIGRAVITY_DOWNLOAD_URL], '#f59e0b')))
            display(widgets.HTML(html_code_block('Debian / Ubuntu', ANTIGRAVITY_DEB_COMMANDS)))
            display(widgets.HTML(html_code_block('Fedora / RPM', ANTIGRAVITY_RPM_COMMANDS)))
        set_status('Antigravity commands shown', ['Scroll below the dashboard for the install commands.'], '#f59e0b')

    def on_config_change(_):
        refresh_intro()
        save_settings()

    file_selector.observe(on_selector_change)
    owner_input.observe(on_config_change, names='value')
    repo_input.observe(on_config_change, names='value')
    branch_input.observe(on_config_change, names='value')
    prefix_input.observe(on_config_change, names='value')

    validate_button.on_click(handle_validate)
    upload_button.on_click(handle_upload)
    refresh_button.on_click(handle_refetch)
    antigravity_button.on_click(handle_antigravity)

    refresh_intro()
    refresh_file_list()

    toolbar = widgets.HBox(
        [validate_button, upload_button, refresh_button, antigravity_button],
        layout=widgets.Layout(flex_flow='row wrap', gap='10px'),
    )
    repo_row_1 = widgets.HBox(
        [owner_input, repo_input, branch_input],
        layout=widgets.Layout(flex_flow='row wrap', gap='10px'),
    )
    repo_row_2 = widgets.HBox(
        [prefix_input, token_input],
        layout=widgets.Layout(flex_flow='row wrap', gap='10px'),
    )
    preview_header = widgets.HTML(
        value=''.join([
            '<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;font-size:13px;color:#cbd5e1;margin:4px 0 10px 0;">',
            'The launcher is selected by default. You can edit any file below, then upload the updated bundle to GitHub.',
            '</div>',
        ])
    )

    display(
        widgets.VBox(
            [
                intro_html,
                status_html,
                repo_row_1,
                repo_row_2,
                commit_input,
                toolbar,
                files_html,
                file_selector,
                preview_header,
                file_preview,
                output,
            ],
            layout=widgets.Layout(width='100%', gap='8px'),
        )
    )

    set_status(
        'Dashboard ready',
        [
            'GitHub upload is in the form above: paste token, then click “Upload bundle to GitHub”.',
            'kaggle_launcher.py is selected first so you can copy it into another notebook if needed.',
        ],
        '#22c55e',
    )


if __name__ == '__main__':
    launch_dashboard()
