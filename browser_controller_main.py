SUPPORT = globals().get('__browser_support__', globals())
if not SUPPORT:
    raise RuntimeError('Support module not loaded by launcher')

import io
import os
import time
import json
import html
import threading
import traceback

import ipywidgets as widgets
from IPython.display import HTML, Javascript, FileLink, FileLinks, clear_output, display

try:
    from PIL import Image as PILImage
    from PIL import ImageDraw, ImageFont
except Exception:
    PILImage = None
    ImageDraw = None
    ImageFont = None

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
ensure_xvfb_running = SUPPORT['ensure_xvfb_running']
ensure_desktop_session = SUPPORT['ensure_desktop_session']
launch_browser = SUPPORT['launch_browser']
launch_terminal = SUPPORT['launch_terminal']
launch_file_manager = SUPPORT['launch_file_manager']
move_mouse = SUPPORT['move_mouse']
mouse_down = SUPPORT['mouse_down']
mouse_up = SUPPORT['mouse_up']
click = SUPPORT['click']
scroll_vertical = SUPPORT['scroll_vertical']
send_key = SUPPORT['send_key']
type_text = SUPPORT['type_text']
get_active_window_title = SUPPORT['get_active_window_title']
get_clipboard_text = SUPPORT['get_clipboard_text']
set_clipboard_text = SUPPORT['set_clipboard_text']
smart_paste_text = SUPPORT['smart_paste_text']
capture_screen_bytes = SUPPORT['capture_screen_bytes']
list_download_files = SUPPORT['list_download_files']
zip_downloads = SUPPORT['zip_downloads']
download_file = SUPPORT['download_file']
run_downloaded_file = SUPPORT['run_downloaded_file']
extract_archive = SUPPORT['extract_archive']
human_size = SUPPORT['human_size']
now_text = SUPPORT['now_text']
append_log = SUPPORT['append_log']


CRITICAL_PROBLEMS = [
    ('Unreadable bundle', 'The old support and main files were collapsed into one line, making real maintenance nearly impossible.'),
    ('No desktop session bootstrap', 'There was no reliable desktop/window-manager startup path for Kaggle Xvfb sessions.'),
    ('Long-press opened notebook UI', 'Right-click and long-press behavior could trigger notebook context menus instead of remote desktop actions.'),
    ('Weak drag model', 'Mouse down and mouse up were not handled like a real remote desktop, so dragging and hold actions felt broken.'),
    ('Clipboard bridge was incomplete', 'There was no dependable path for remote clipboard read/write, terminal paste fallbacks, or copy-output helpers.'),
    ('Downloads were not first-class', 'There was no managed downloads folder, no refreshable file list, and no direct notebook download links.'),
    ('Running downloaded apps was clumsy', 'AppImage, shell scripts, archives, and folders were not handled through a clear run/open workflow.'),
    ('Browser profile was fragile', 'Downloads and browser state were not pinned cleanly to Kaggle persistent working storage.'),
    ('No shell diagnostics', 'There was no built-in command runner with copyable output for troubleshooting inside the same notebook.'),
    ('Poor visibility and recovery', 'Logging, status reporting, session summaries, and fallback behavior were not strong enough for real notebook use.'),
]


class KaggleDesktopController:
    def __init__(self):
        self.paths = ensure_state_dirs()
        self.saved_state = load_json(self.paths['state_json'], {})
        self.capture_lock = threading.Lock()
        self.auto_refresh_stop = threading.Event()
        self.auto_refresh_thread = None
        self.status_lines = []
        self.last_capture_at = ''
        self.last_error = ''
        self.pressed_buttons = set()
        self.browser_side_output_buffer = ''
        self.bundle_paths = globals().get('__browser_bundle_paths__', {})

        self._build_widgets()
        self._render()
        self._attach_events()
        self._startup_sequence()

    def _build_widgets(self):
        issue_items = []
        for index, (title_text, body_text) in enumerate(CRITICAL_PROBLEMS, start=1):
            issue_items.append(
                '<div style="padding:12px 14px;border:1px solid #1e293b;border-radius:16px;background:#020617;">'
                '<div style="font-size:12px;color:#38bdf8;letter-spacing:.08em;text-transform:uppercase;">Issue ' + str(index) + '</div>'
                '<div style="font-size:15px;font-weight:700;color:#f8fafc;margin-top:4px;">' + html.escape(title_text) + '</div>'
                '<div style="font-size:13px;line-height:1.6;color:#cbd5e1;margin-top:6px;">' + html.escape(body_text) + '</div>'
                '</div>'
            )

        self.header_html = widgets.HTML(
            value=(
                '<div style="padding:18px 20px;border:1px solid #1e293b;border-radius:24px;'
                'background:linear-gradient(135deg,#020617,#0f172a 55%,#111827);color:#f8fafc;">'
                '<div style="font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:#38bdf8;">Kaggle desktop controller</div>'
                '<div style="font-size:30px;font-weight:800;margin-top:8px;">Kaggle browser desktop fix pack</div>'
                '<div style="font-size:14px;line-height:1.7;color:#cbd5e1;margin-top:10px;max-width:900px;">'
                'This notebook UI now focuses on the Kaggle environment: start a desktop, open Chromium, drag with real button-down/button-up behavior, '
                'download files, run AppImages or shell scripts, read and write the remote clipboard, and copy command output back to your browser clipboard.'
                '</div>'
                '</div>'
            )
        )
        self.issues_html = widgets.HTML(
            value=(
                '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;">'
                + ''.join(issue_items)
                + '</div>'
            )
        )

        self.status_html = widgets.HTML()
        self.log_html = widgets.HTML(value=html_message_box('info', 'Activity log', 'Starting notebook controller...'))

        self.screen_widget = widgets.Image(
            format='png',
            layout=widgets.Layout(width='100%', max_width='1280px', height='auto', border='1px solid #334155'),
        )
        self.pointer_help_html = widgets.HTML(
            value=(
                '<div style="font-size:13px;color:#cbd5e1;line-height:1.65;">'
                '<b>Pointer fixes:</b> the screenshot surface blocks context-menu defaults, translates press/release separately, '
                'supports drag + hold, and throttles noisy move events. If paste shortcuts fail in a terminal, use <b>Paste text</b> or <b>Type text</b>. '
                'If the screen looks stale, click <b>Refresh screen</b>.'
                '</div>'
            )
        )

        self.url_input = widgets.Text(
            value=self.saved_state.get('last_url', URL_GOOGLE),
            placeholder='https://example.com',
            description='URL',
            layout=widgets.Layout(width='100%'),
        )
        self.refresh_interval = widgets.Dropdown(
            options=[('0.7s', 0.7), ('1.0s', 1.0), ('1.5s', 1.5), ('2.0s', 2.0), ('3.0s', 3.0)],
            value=self.saved_state.get('refresh_seconds', 1.0),
            description='Auto',
            layout=widgets.Layout(width='170px'),
        )
        self.auto_refresh_toggle = widgets.ToggleButton(
            value=self.saved_state.get('auto_refresh', True),
            description='Auto refresh',
            icon='refresh',
            layout=widgets.Layout(width='150px'),
        )

        self.start_desktop_button = widgets.Button(description='Start desktop', icon='desktop')
        self.open_browser_button = widgets.Button(description='Open browser', icon='globe')
        self.open_terminal_button = widgets.Button(description='Open terminal', icon='terminal')
        self.open_files_button = widgets.Button(description='Open downloads', icon='folder-open')
        self.refresh_screen_button = widgets.Button(description='Refresh screen', icon='camera')
        self.release_buttons_button = widgets.Button(description='Release mouse', icon='hand-stop-o')

        self.quick_google_button = widgets.Button(description='Google')
        self.quick_login_button = widgets.Button(description='Login')
        self.quick_codex_button = widgets.Button(description='Codex web')
        self.quick_codex_docs_button = widgets.Button(description='Codex app')
        self.quick_releases_button = widgets.Button(description='CLI releases')
        self.quick_antigravity_button = widgets.Button(description='AntiGravity')

        self.left_click_button = widgets.Button(description='Left click')
        self.double_click_button = widgets.Button(description='Double click')
        self.right_click_button = widgets.Button(description='Right click')
        self.middle_click_button = widgets.Button(description='Middle click')
        self.scroll_up_button = widgets.Button(description='Scroll up')
        self.scroll_down_button = widgets.Button(description='Scroll down')

        self.clipboard_area = widgets.Textarea(
            value=self.saved_state.get('clipboard_text', ''),
            placeholder='Paste text here for remote clipboard, terminal paste, or typing.',
            layout=widgets.Layout(width='100%', height='150px'),
        )
        self.remote_clipboard_button = widgets.Button(description='Read remote clipboard', icon='download')
        self.set_remote_clipboard_button = widgets.Button(description='Set remote clipboard', icon='upload')
        self.paste_remote_button = widgets.Button(description='Paste text', icon='paste')
        self.type_text_button = widgets.Button(description='Type text', icon='keyboard-o')
        self.copy_area_button = widgets.Button(description='Copy area to browser', icon='copy')
        self.copy_remote_to_browser_button = widgets.Button(description='Copy remote clipboard to browser', icon='clone')
        self.shortcut_copy_button = widgets.Button(description='Send Ctrl+C')
        self.shortcut_cut_button = widgets.Button(description='Send Ctrl+X')
        self.shortcut_paste_button = widgets.Button(description='Send Ctrl+V')
        self.shortcut_term_paste_button = widgets.Button(description='Send Ctrl+Shift+V')
        self.terminal_paste_mode = widgets.ToggleButtons(
            options=['Normal app', 'Terminal'],
            value=self.saved_state.get('paste_mode', 'Normal app'),
            description='Target',
            layout=widgets.Layout(width='320px'),
        )

        self.command_input = widgets.Text(
            value=self.saved_state.get('last_command', ''),
            placeholder='Example: ls -lah /kaggle/working',
            description='Shell',
            layout=widgets.Layout(width='100%'),
        )
        self.run_command_button = widgets.Button(description='Run shell command', icon='play')
        self.copy_output_button = widgets.Button(description='Copy output to browser', icon='copy')
        self.command_output = widgets.Textarea(
            value='',
            placeholder='Shell output appears here.',
            layout=widgets.Layout(width='100%', height='240px'),
        )

        self.download_url_input = widgets.Text(
            value=self.saved_state.get('last_download_url', ''),
            placeholder='https://example.com/file.AppImage',
            description='Download',
            layout=widgets.Layout(width='100%'),
        )
        self.download_name_input = widgets.Text(
            value=self.saved_state.get('last_download_name', ''),
            placeholder='Optional override name',
            description='Name',
            layout=widgets.Layout(width='100%'),
        )
        self.download_now_button = widgets.Button(description='Download now', icon='download')
        self.refresh_downloads_button = widgets.Button(description='Refresh files', icon='refresh')
        self.zip_downloads_button = widgets.Button(description='Zip downloads', icon='archive')

        self.run_path_input = widgets.Text(
            value=self.saved_state.get('last_run_path', ''),
            placeholder='downloads/my-app.AppImage or full path',
            description='Run path',
            layout=widgets.Layout(width='100%'),
        )
        self.run_args_input = widgets.Text(
            value=self.saved_state.get('last_run_args', ''),
            placeholder='Optional arguments',
            description='Args',
            layout=widgets.Layout(width='100%'),
        )
        self.run_file_button = widgets.Button(description='Run / open', icon='rocket')
        self.extract_file_button = widgets.Button(description='Extract archive', icon='folder-open-o')
        self.downloads_output = widgets.Output(layout=widgets.Layout(border='1px solid #1e293b', padding='12px'))

        bundle_default_owner = self.saved_state.get('bundle_owner', DEFAULT_OWNER)
        bundle_default_repo = self.saved_state.get('bundle_repo', DEFAULT_REPO)
        bundle_default_branch = self.saved_state.get('bundle_branch', DEFAULT_BRANCH)
        self.github_token_input = widgets.Password(
            value='',
            placeholder='Optional GitHub token',
            description='Token',
            layout=widgets.Layout(width='100%'),
        )
        self.github_owner_input = widgets.Text(value=bundle_default_owner, description='Owner', layout=widgets.Layout(width='100%'))
        self.github_repo_input = widgets.Text(value=bundle_default_repo, description='Repo', layout=widgets.Layout(width='100%'))
        self.github_branch_input = widgets.Text(value=bundle_default_branch, description='Branch', layout=widgets.Layout(width='100%'))
        self.push_bundle_button = widgets.Button(description='Push local bundle files', icon='github')
        self.github_result_html = widgets.HTML(
            value=html_message_box('info', 'GitHub sync', 'Optional: push the notebook-side bundle files back to your repository from inside Kaggle.')
        )

    def _render(self):
        display(HTML(
            '<style>'
            '.ipyevents-watched:focus{outline:none!important;box-shadow:none!important;}'
            '.widget-image img{image-rendering:auto;touch-action:none;-webkit-touch-callout:none;user-select:none;-webkit-user-select:none;}'
            '.jupyter-widgets.widget-tab > .p-TabBar .p-TabBar-tab{font-weight:600;}'
            '</style>'
        ))

        quick_links_row = widgets.HBox([
            self.quick_google_button,
            self.quick_login_button,
            self.quick_codex_button,
            self.quick_codex_docs_button,
            self.quick_releases_button,
            self.quick_antigravity_button,
        ])

        session_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Session and desktop</h3>'),
            widgets.HBox([self.start_desktop_button, self.open_terminal_button, self.open_files_button]),
            widgets.HBox([self.url_input, widgets.VBox([self.open_browser_button, self.refresh_screen_button])]),
            widgets.HBox([self.auto_refresh_toggle, self.refresh_interval, self.release_buttons_button]),
            quick_links_row,
        ])

        mouse_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Mouse quick actions</h3>'),
            widgets.HBox([
                self.left_click_button,
                self.double_click_button,
                self.right_click_button,
                self.middle_click_button,
                self.scroll_up_button,
                self.scroll_down_button,
            ]),
        ])

        screen_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Live desktop surface</h3>'),
            self.screen_widget,
            self.pointer_help_html,
        ])

        clipboard_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Clipboard and text bridge</h3>'),
            self.clipboard_area,
            widgets.HBox([self.remote_clipboard_button, self.set_remote_clipboard_button, self.copy_area_button, self.copy_remote_to_browser_button]),
            widgets.HBox([self.paste_remote_button, self.type_text_button, self.terminal_paste_mode]),
            widgets.HBox([self.shortcut_copy_button, self.shortcut_cut_button, self.shortcut_paste_button, self.shortcut_term_paste_button]),
        ])

        shell_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Shell tools</h3>'),
            widgets.HBox([self.command_input, widgets.VBox([self.run_command_button, self.copy_output_button])]),
            self.command_output,
        ])

        downloads_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Downloads and app runner</h3>'),
            self.download_url_input,
            self.download_name_input,
            widgets.HBox([self.download_now_button, self.refresh_downloads_button, self.zip_downloads_button]),
            self.run_path_input,
            self.run_args_input,
            widgets.HBox([self.run_file_button, self.extract_file_button]),
            self.downloads_output,
        ])

        github_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Optional GitHub push</h3>'),
            self.github_token_input,
            widgets.HBox([self.github_owner_input, self.github_repo_input, self.github_branch_input]),
            self.push_bundle_button,
            self.github_result_html,
        ])

        diagnostics_box = widgets.VBox([
            widgets.HTML(value='<h3 style="margin:0 0 8px 0;color:#f8fafc;">Diagnostics</h3>'),
            self.status_html,
            self.log_html,
        ])

        accordion = widgets.Accordion(children=[
            session_box,
            mouse_box,
            clipboard_box,
            shell_box,
            downloads_box,
            github_box,
            diagnostics_box,
        ])
        accordion.set_title(0, 'Session')
        accordion.set_title(1, 'Mouse')
        accordion.set_title(2, 'Clipboard')
        accordion.set_title(3, 'Shell')
        accordion.set_title(4, 'Downloads')
        accordion.set_title(5, 'GitHub')
        accordion.set_title(6, 'Diagnostics')
        accordion.selected_index = 0

        root = widgets.VBox([
            self.header_html,
            self.issues_html,
            screen_box,
            accordion,
        ])
        display(root)

    def _attach_events(self):
        self.start_desktop_button.on_click(lambda _: self._safe_action('Start desktop', self.start_desktop))
        self.open_browser_button.on_click(lambda _: self._safe_action('Open browser', self.open_browser))
        self.open_terminal_button.on_click(lambda _: self._safe_action('Open terminal', self.open_terminal))
        self.open_files_button.on_click(lambda _: self._safe_action('Open downloads folder', self.open_downloads_folder))
        self.refresh_screen_button.on_click(lambda _: self._safe_action('Refresh screen', self.refresh_screen))
        self.release_buttons_button.on_click(lambda _: self._safe_action('Release mouse buttons', self.release_all_buttons))

        self.quick_google_button.on_click(lambda _: self._safe_action('Open Google', lambda: self.open_url(URL_GOOGLE)))
        self.quick_login_button.on_click(lambda _: self._safe_action('Open Google login', lambda: self.open_url(URL_GOOGLE_LOGIN)))
        self.quick_codex_button.on_click(lambda _: self._safe_action('Open Codex web', lambda: self.open_url(URL_CODEX_WEB)))
        self.quick_codex_docs_button.on_click(lambda _: self._safe_action('Open Codex app', lambda: self.open_url(URL_CODEX_APP)))
        self.quick_releases_button.on_click(lambda _: self._safe_action('Open Codex CLI releases', lambda: self.open_url(URL_CODEX_CLI_RELEASES)))
        self.quick_antigravity_button.on_click(lambda _: self._safe_action('Open AntiGravity', lambda: self.open_url(URL_ANTIGRAVITY_APP)))

        self.left_click_button.on_click(lambda _: self._safe_action('Left click', lambda: self.pointer_click(1, 1)))
        self.double_click_button.on_click(lambda _: self._safe_action('Double click', lambda: self.pointer_click(1, 2)))
        self.right_click_button.on_click(lambda _: self._safe_action('Right click', lambda: self.pointer_click(3, 1)))
        self.middle_click_button.on_click(lambda _: self._safe_action('Middle click', lambda: self.pointer_click(2, 1)))
        self.scroll_up_button.on_click(lambda _: self._safe_action('Scroll up', lambda: scroll_vertical(-3)))
        self.scroll_down_button.on_click(lambda _: self._safe_action('Scroll down', lambda: scroll_vertical(3)))

        self.remote_clipboard_button.on_click(lambda _: self._safe_action('Read remote clipboard', self.read_remote_clipboard))
        self.set_remote_clipboard_button.on_click(lambda _: self._safe_action('Set remote clipboard', self.write_remote_clipboard))
        self.paste_remote_button.on_click(lambda _: self._safe_action('Paste text', self.paste_remote_text))
        self.type_text_button.on_click(lambda _: self._safe_action('Type text', self.type_text_from_area))
        self.copy_area_button.on_click(lambda _: self._safe_action('Copy area to browser clipboard', lambda: self.copy_to_browser_clipboard(self.clipboard_area.value, 'Clipboard area copied to browser clipboard.')))
        self.copy_remote_to_browser_button.on_click(lambda _: self._safe_action('Copy remote clipboard to browser', self.copy_remote_clipboard_to_browser))
        self.shortcut_copy_button.on_click(lambda _: self._safe_action('Send Ctrl+C', lambda: send_key('ctrl+c')))
        self.shortcut_cut_button.on_click(lambda _: self._safe_action('Send Ctrl+X', lambda: send_key('ctrl+x')))
        self.shortcut_paste_button.on_click(lambda _: self._safe_action('Send Ctrl+V', lambda: send_key('ctrl+v')))
        self.shortcut_term_paste_button.on_click(lambda _: self._safe_action('Send Ctrl+Shift+V', lambda: send_key('ctrl+shift+v')))

        self.run_command_button.on_click(lambda _: self._safe_action('Run shell command', self.run_shell_command))
        self.copy_output_button.on_click(lambda _: self._safe_action('Copy output', lambda: self.copy_to_browser_clipboard(self.command_output.value, 'Shell output copied to browser clipboard.')))

        self.download_now_button.on_click(lambda _: self._safe_action('Download file', self.download_now))
        self.refresh_downloads_button.on_click(lambda _: self._safe_action('Refresh downloads', self.refresh_downloads_view))
        self.zip_downloads_button.on_click(lambda _: self._safe_action('Zip downloads', self.zip_downloads_action))
        self.run_file_button.on_click(lambda _: self._safe_action('Run file', self.run_selected_file))
        self.extract_file_button.on_click(lambda _: self._safe_action('Extract archive', self.extract_selected_archive))

        self.push_bundle_button.on_click(lambda _: self._safe_action('Push bundle to GitHub', self.push_bundle_to_github))

        self.auto_refresh_toggle.observe(self._on_auto_refresh_change, names='value')
        self.refresh_interval.observe(self._on_refresh_interval_change, names='value')

        if Event is not None:
            self.pointer_events = Event(
                source=self.screen_widget,
                watched_events=['mousedown', 'mouseup', 'mousemove', 'wheel', 'contextmenu', 'dragstart', 'mouseleave', 'touchstart', 'touchmove', 'touchend', 'touchcancel'],
                prevent_default_action=True,
                wait=16,
                throttle_or_debounce='throttle',
            )
            self.pointer_events.on_dom_event(self.handle_pointer_event)
        else:
            self._log('ipyevents is not available; screenshot clicks are disabled.', kind='warning')

    def _startup_sequence(self):
        ready = ensure_xvfb_running(self.paths)
        self._log(ready['message'], kind='success' if ready.get('ok') else 'warning')
        self.refresh_screen()
        self.refresh_downloads_view()
        self.refresh_status()
        if self.auto_refresh_toggle.value:
            self.start_auto_refresh_loop()

    def _safe_action(self, label, callback):
        try:
            result = callback()
            self.save_state()
            self.refresh_status()
            return result
        except Exception as exc:
            self.last_error = str(exc)
            self._log(label + ' failed: ' + str(exc), kind='error')
            traceback_text = traceback.format_exc(limit=2)
            append_log('errors.log', label + ' failed\n' + traceback_text)
            self.refresh_status()

    def _log(self, text_value, kind='info'):
        line = '[' + now_text() + '] ' + str(text_value)
        self.status_lines.insert(0, {'kind': kind, 'text': line})
        self.status_lines = self.status_lines[:12]
        items = []
        tone_map = {
            'info': '#38bdf8',
            'success': '#34d399',
            'warning': '#f59e0b',
            'error': '#fb7185',
        }
        for entry in self.status_lines:
            items.append(
                '<div style="padding:8px 10px;border:1px solid #1e293b;border-radius:12px;background:#020617;color:#e2e8f0;">'
                '<span style="color:' + tone_map.get(entry['kind'], '#38bdf8') + ';font-weight:700;">●</span> '
                + html.escape(entry['text'])
                + '</div>'
            )
        self.log_html.value = '<div style="display:grid;gap:8px;">' + ''.join(items) + '</div>'

    def refresh_status(self):
        cpu_info = detect_cpu_info()
        browser_binary = find_browser_binary() or 'Not found'
        active_window = get_active_window_title() or 'No active X11 window detected yet'
        download_files = list_download_files(self.paths, limit=200)
        profile_state = 'Warm profile' if profile_has_previous_session(self.paths['profile_dir']) else 'Fresh profile'
        last_error_html = html.escape(self.last_error) if self.last_error else 'None'

        cards = [
            ('Display', DISPLAY_VALUE),
            ('Screen size', str(SCREEN_W) + ' × ' + str(SCREEN_H)),
            ('CPU', html.escape(str(cpu_info['cpu_count'])) + ' cores'),
            ('Memory', html.escape(str(cpu_info['memory_gb'])) + ' GB'),
            ('Browser', html.escape(os.path.basename(browser_binary))),
            ('Downloads', str(len(download_files)) + ' files'),
            ('Profile', profile_state),
            ('Last capture', html.escape(self.last_capture_at or 'Not captured yet')),
            ('Active window', html.escape(active_window)),
            ('State root', html.escape(self.paths['root'])),
            ('Persistent', 'Yes' if self.paths['persistent'] else 'No'),
            ('Last error', last_error_html),
        ]

        rows = []
        for title_text, value_text in cards:
            rows.append(
                '<div style="padding:12px;border:1px solid #1e293b;border-radius:16px;background:#020617;">'
                '<div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;">' + title_text + '</div>'
                '<div style="font-size:14px;color:#f8fafc;font-weight:700;margin-top:6px;line-height:1.5;">' + value_text + '</div>'
                '</div>'
            )
        self.status_html.value = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;">' + ''.join(rows) + '</div>'

    def save_state(self):
        save_json(self.paths['state_json'], {
            'last_url': self.url_input.value,
            'refresh_seconds': self.refresh_interval.value,
            'auto_refresh': bool(self.auto_refresh_toggle.value),
            'clipboard_text': self.clipboard_area.value,
            'paste_mode': self.terminal_paste_mode.value,
            'last_command': self.command_input.value,
            'last_download_url': self.download_url_input.value,
            'last_download_name': self.download_name_input.value,
            'last_run_path': self.run_path_input.value,
            'last_run_args': self.run_args_input.value,
            'bundle_owner': self.github_owner_input.value,
            'bundle_repo': self.github_repo_input.value,
            'bundle_branch': self.github_branch_input.value,
        })

    def build_placeholder_screen(self, message_text):
        if PILImage is None or ImageDraw is None:
            return b''
        image = PILImage.new('RGB', (1280, 720), color=(15, 23, 42))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default() if ImageFont is not None else None
        draw.rectangle((40, 40, 1240, 680), outline=(56, 189, 248), width=3)
        draw.text((80, 90), 'Kaggle desktop screen unavailable', fill=(248, 250, 252), font=font)
        draw.text((80, 140), message_text[:300], fill=(203, 213, 225), font=font)
        draw.text((80, 210), 'Try: Start desktop -> Open browser -> Refresh screen', fill=(52, 211, 153), font=font)
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    def refresh_screen(self):
        with self.capture_lock:
            try:
                png_bytes = capture_screen_bytes(self.paths, max_width=1280)
                self.screen_widget.value = png_bytes
                self.last_capture_at = now_text()
                self._log('Screen refreshed.', kind='success')
            except Exception as exc:
                self.screen_widget.value = self.build_placeholder_screen(str(exc))
                self.last_capture_at = now_text() + ' (placeholder)'
                self._log('Screen refresh used placeholder: ' + str(exc), kind='warning')
        self.refresh_status()

    def start_auto_refresh_loop(self):
        if self.auto_refresh_thread and self.auto_refresh_thread.is_alive():
            return
        self.auto_refresh_stop.clear()

        def loop():
            while not self.auto_refresh_stop.wait(max(0.5, float(self.refresh_interval.value or 1.0))):
                try:
                    self.refresh_screen()
                except Exception:
                    pass

        self.auto_refresh_thread = threading.Thread(target=loop, daemon=True)
        self.auto_refresh_thread.start()
        self._log('Auto refresh enabled.', kind='info')

    def stop_auto_refresh_loop(self):
        self.auto_refresh_stop.set()
        self._log('Auto refresh paused.', kind='warning')

    def _on_auto_refresh_change(self, change):
        if change['new']:
            self.start_auto_refresh_loop()
        else:
            self.stop_auto_refresh_loop()
        self.save_state()

    def _on_refresh_interval_change(self, change):
        self._log('Refresh interval set to ' + str(change['new']) + 's.', kind='info')
        if self.auto_refresh_toggle.value:
            self.stop_auto_refresh_loop()
            self.start_auto_refresh_loop()
        self.save_state()

    def start_desktop(self):
        result = ensure_desktop_session(self.paths)
        self._log(result['message'], kind='success')
        time.sleep(1.0)
        self.refresh_screen()

    def open_url(self, url_value):
        proc = launch_browser(self.paths, url_value)
        self._log('Opened URL in browser pid=' + str(proc.pid) + ': ' + url_value, kind='success')
        time.sleep(1.0)
        self.refresh_screen()
        return proc

    def open_browser(self):
        url_value = (self.url_input.value or '').strip() or URL_GOOGLE
        return self.open_url(url_value)

    def open_terminal(self):
        proc = launch_terminal(self.paths)
        if not proc:
            raise RuntimeError('xterm is not available')
        self._log('Opened terminal pid=' + str(proc.pid), kind='success')
        time.sleep(0.6)
        self.refresh_screen()
        return proc

    def open_downloads_folder(self):
        proc = launch_file_manager(self.paths, self.paths['downloads_dir'])
        if not proc:
            raise RuntimeError('No file manager is available')
        self._log('Opened downloads folder pid=' + str(proc.pid), kind='success')
        time.sleep(0.6)
        self.refresh_screen()
        return proc

    def release_all_buttons(self):
        for button_value in list(self.pressed_buttons):
            try:
                mouse_up(button_value)
            except Exception:
                pass
            self.pressed_buttons.discard(button_value)
        self._log('Released all tracked mouse buttons.', kind='info')

    def pointer_click(self, button_value, repeat_count):
        self.release_all_buttons()
        click(button_value, repeat=repeat_count, delay_ms=120)
        self._log('Sent mouse click button=' + str(button_value) + ' repeat=' + str(repeat_count), kind='success')
        time.sleep(0.15)
        self.refresh_screen()

    def event_xy(self, event):
        if 'dataX' in event and 'dataY' in event:
            return int(event['dataX']), int(event['dataY'])
        if 'arrayX' in event and 'arrayY' in event:
            return int(event['arrayX']), int(event['arrayY'])
        if event.get('changedTouches'):
            touch = event['changedTouches'][0]
            if 'dataX' in touch and 'dataY' in touch:
                return int(touch['dataX']), int(touch['dataY'])
        width = float(event.get('boundingRectWidth') or 1)
        height = float(event.get('boundingRectHeight') or 1)
        left = float(event.get('boundingRectLeft') or 0)
        top = float(event.get('boundingRectTop') or 0)
        client_x = float(event.get('clientX') or left) - left
        client_y = float(event.get('clientY') or top) - top
        x_value = max(0, min(SCREEN_W - 1, int((client_x / max(width, 1.0)) * SCREEN_W)))
        y_value = max(0, min(SCREEN_H - 1, int((client_y / max(height, 1.0)) * SCREEN_H)))
        return x_value, y_value

    def event_button_to_x11(self, button_value):
        return {0: 1, 1: 2, 2: 3}.get(button_value, 1)

    def handle_pointer_event(self, event):
        event_type = event.get('type')
        if event_type in ('contextmenu', 'dragstart'):
            return

        x_value, y_value = self.event_xy(event)
        move_mouse(x_value, y_value)

        if event_type in ('mousedown', 'touchstart'):
            button_value = 1 if event_type == 'touchstart' else self.event_button_to_x11(event.get('button'))
            if button_value not in self.pressed_buttons:
                mouse_down(button_value)
                self.pressed_buttons.add(button_value)
            return

        if event_type in ('mouseup', 'touchend', 'touchcancel', 'mouseleave'):
            if event_type in ('touchend', 'touchcancel', 'mouseleave'):
                buttons_to_release = list(self.pressed_buttons)
            else:
                buttons_to_release = [self.event_button_to_x11(event.get('button'))]
            for button_value in buttons_to_release:
                if button_value in self.pressed_buttons:
                    mouse_up(button_value)
                    self.pressed_buttons.discard(button_value)
            return

        if event_type == 'wheel':
            delta_y = float(event.get('deltaY') or 0)
            steps = max(1, min(8, int(abs(delta_y) / 45.0) + 1))
            scroll_vertical(steps if delta_y > 0 else -steps)
            return

        if event_type in ('mousemove', 'touchmove'):
            return

    def read_remote_clipboard(self):
        self.clipboard_area.value = get_clipboard_text()
        self._log('Read remote clipboard into the text area.', kind='success')

    def write_remote_clipboard(self):
        set_clipboard_text(self.clipboard_area.value)
        self._log('Updated the remote clipboard from the text area.', kind='success')

    def paste_remote_text(self):
        terminal_mode = self.terminal_paste_mode.value == 'Terminal'
        smart_paste_text(self.clipboard_area.value, terminal_mode=terminal_mode)
        self._log('Sent paste to the active remote window (' + self.terminal_paste_mode.value + ').', kind='success')
        time.sleep(0.2)
        self.refresh_screen()

    def type_text_from_area(self):
        type_text(self.clipboard_area.value)
        self._log('Typed text directly into the active remote window.', kind='success')
        time.sleep(0.2)
        self.refresh_screen()

    def copy_to_browser_clipboard(self, text_value, success_message):
        js_payload = json.dumps(text_value or '')
        display(Javascript(
            """
            (async () => {
              try {
                await navigator.clipboard.writeText(%s);
              } catch (error) {
                console.error(error);
              }
            })();
            """ % js_payload
        ))
        self._log(success_message, kind='success')

    def copy_remote_clipboard_to_browser(self):
        text_value = get_clipboard_text()
        self.copy_to_browser_clipboard(text_value, 'Remote clipboard copied to the browser clipboard.')

    def run_shell_command(self):
        command_text = (self.command_input.value or '').strip()
        if not command_text:
            raise RuntimeError('Enter a shell command first')
        result = run_shell(command_text, timeout=240, cwd=self.paths['root'])
        output_parts = [
            '$ ' + command_text,
            '',
            result.get('stdout', '').rstrip(),
        ]
        if result.get('stderr'):
            output_parts.extend(['', '[stderr]', result.get('stderr', '').rstrip()])
        output_parts.extend(['', '[exit code ' + str(result.get('returncode')) + ']'])
        self.command_output.value = '\n'.join(part for part in output_parts if part is not None).strip() + '\n'
        if result.get('returncode') == 0:
            self._log('Shell command finished successfully.', kind='success')
        else:
            self._log('Shell command finished with exit code ' + str(result.get('returncode')) + '.', kind='warning')
        self.refresh_downloads_view()
        self.refresh_status()

    def download_now(self):
        url_value = (self.download_url_input.value or '').strip()
        if not url_value:
            raise RuntimeError('Enter a download URL first')
        output_path = download_file(url_value, self.paths, self.download_name_input.value)
        self.run_path_input.value = output_path
        self._log('Downloaded file to ' + output_path, kind='success')
        self.refresh_downloads_view()

    def refresh_downloads_view(self):
        zip_path = zip_downloads(self.paths)
        files = list_download_files(self.paths, limit=200)
        with self.downloads_output:
            clear_output(wait=True)
            display(HTML(list_download_files_html(self.paths, limit=100)))
            if files:
                display(HTML('<div style="height:8px"></div>'))
                display(HTML('<div style="font-weight:700;color:#f8fafc;margin-bottom:6px;">Notebook download links</div>'))
                display(FileLinks(self.paths['downloads_dir'], recursive=True))
                display(HTML('<div style="height:8px"></div>'))
                display(FileLink(zip_path, result_html_prefix='Download all as zip: '))
            else:
                display(HTML('<div style="font-size:13px;color:#94a3b8;margin-top:8px;">No downloaded files yet.</div>'))
        self._log('Downloads view refreshed.', kind='info')

    def zip_downloads_action(self):
        zip_path = zip_downloads(self.paths)
        self.run_path_input.value = zip_path
        self._log('Created zip bundle: ' + zip_path, kind='success')
        self.refresh_downloads_view()

    def run_selected_file(self):
        path_value = (self.run_path_input.value or '').strip()
        if not path_value:
            raise RuntimeError('Enter a file path first')
        proc = run_downloaded_file(path_value, self.paths, self.run_args_input.value)
        pid_value = getattr(proc, 'pid', None)
        message = 'Opened or launched ' + path_value
        if pid_value:
            message += ' pid=' + str(pid_value)
        self._log(message, kind='success')
        time.sleep(0.8)
        self.refresh_screen()

    def extract_selected_archive(self):
        path_value = (self.run_path_input.value or '').strip()
        if not path_value:
            raise RuntimeError('Enter an archive path first')
        extract_dir = extract_archive(path_value, self.paths)
        self.run_path_input.value = extract_dir
        self._log('Archive extracted to ' + extract_dir, kind='success')
        self.refresh_downloads_view()
        launch_file_manager(self.paths, extract_dir)

    def bundle_files_to_push(self):
        files_map = {}
        for file_name in [DEFAULT_MAIN_PATH, DEFAULT_SUPPORT_PATH, DEFAULT_README_PATH, 'kaggle_launcher.py', 'browser_controller_full.py']:
            path_value = None
            if self.bundle_paths and file_name in self.bundle_paths:
                path_value = self.bundle_paths[file_name]
            elif os.path.exists(file_name):
                path_value = file_name
            elif os.path.exists(os.path.join(self.paths['bundle_dir'], file_name)):
                path_value = os.path.join(self.paths['bundle_dir'], file_name)
            if path_value and os.path.exists(path_value):
                files_map[file_name] = file_read_text(path_value, '')
        return files_map

    def push_bundle_to_github(self):
        token_value = (self.github_token_input.value or '').strip()
        owner_value = (self.github_owner_input.value or '').strip()
        repo_value = (self.github_repo_input.value or '').strip()
        branch_value = (self.github_branch_input.value or '').strip() or 'main'
        if not token_value:
            raise RuntimeError('Paste a GitHub token first')
        if not owner_value or not repo_value:
            raise RuntimeError('Owner and repo are required')

        github_validate_token(token_value)
        github_check_repo_access(token_value, owner_value, repo_value)
        files_map = self.bundle_files_to_push()
        if not files_map:
            raise RuntimeError('No local bundle files were found to upload')
        github_upsert_many(token_value, owner_value, repo_value, branch_value, files_map, message_prefix='Kaggle bundle update')
        self.github_result_html.value = html_message_box(
            'success',
            'GitHub sync complete',
            'Uploaded <b>' + str(len(files_map)) + '</b> files to <b>' + html.escape(owner_value + '/' + repo_value) + '</b> on branch <b>' + html.escape(branch_value) + '</b>.',
        )
        self._log('Pushed local bundle files to GitHub.', kind='success')


app = KaggleDesktopController()
