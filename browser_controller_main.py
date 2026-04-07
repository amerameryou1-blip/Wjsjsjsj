SUPPORT = globals().get('__browser_support__', globals())
if not SUPPORT:
    raise RuntimeError('Support module not loaded by launcher')

import os
import io
import html
import time
import json
import threading
import traceback

import ipywidgets as widgets
from IPython.display import HTML, Javascript, FileLinks, clear_output, display

try:
    from ipyevents import Event
except Exception:
    Event = None

DISPLAY_VALUE = SUPPORT['DISPLAY_VALUE']
SCREEN_W = SUPPORT['SCREEN_W']
SCREEN_H = SUPPORT['SCREEN_H']
STATE_DIR_NAME = SUPPORT['STATE_DIR_NAME']
URL_GOOGLE = SUPPORT['URL_GOOGLE']
URL_GITHUB = SUPPORT['URL_GITHUB']
URL_KAGGLE = SUPPORT['URL_KAGGLE']
URL_ZORIN = SUPPORT['URL_ZORIN']
URL_XFCE_DOCS = SUPPORT['URL_XFCE_DOCS']
DEFAULT_OWNER = SUPPORT['DEFAULT_OWNER']
DEFAULT_REPO = SUPPORT['DEFAULT_REPO']
DEFAULT_BRANCH = SUPPORT['DEFAULT_BRANCH']
DEFAULT_PREFIX = SUPPORT['DEFAULT_PREFIX']
DEFAULT_MAIN_PATH = SUPPORT['DEFAULT_MAIN_PATH']
DEFAULT_SUPPORT_PATH = SUPPORT['DEFAULT_SUPPORT_PATH']
DEFAULT_README_PATH = SUPPORT['DEFAULT_README_PATH']
RESEARCH_NOTES = SUPPORT['RESEARCH_NOTES']
ensure_state_dirs = SUPPORT['ensure_state_dirs']
load_json = SUPPORT['load_json']
save_json = SUPPORT['save_json']
append_log = SUPPORT['append_log']
file_read_text = SUPPORT['file_read_text']
run_shell = SUPPORT['run_shell']
run_list = SUPPORT['run_list']
human_size = SUPPORT['human_size']
now_text = SUPPORT['now_text']
html_message_box = SUPPORT['html_message_box']
detect_cpu_info = SUPPORT['detect_cpu_info']
install_or_repair_stack = SUPPORT['install_or_repair_stack']
ensure_xvfb_running = SUPPORT['ensure_xvfb_running']
ensure_desktop_session = SUPPORT['ensure_desktop_session']
apply_zorin_layout = SUPPORT['apply_zorin_layout']
find_browser_binary = SUPPORT['find_browser_binary']
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
list_download_files_html = SUPPORT['list_download_files_html']
download_file = SUPPORT['download_file']
extract_archive = SUPPORT['extract_archive']
run_downloaded_file = SUPPORT['run_downloaded_file']
zip_downloads = SUPPORT['zip_downloads']
github_validate_token = SUPPORT['github_validate_token']
github_check_repo_access = SUPPORT['github_check_repo_access']
github_upsert_many = SUPPORT['github_upsert_many']


class ZorinKaggleDesktopApp:
    def __init__(self):
        self.paths = ensure_state_dirs()
        self.state = load_json(self.paths['state_json'], {})
        self.capture_lock = threading.Lock()
        self.auto_refresh_stop = threading.Event()
        self.auto_refresh_thread = None
        self.pressed_buttons = set()
        self.last_pointer = {'x': SCREEN_W // 2, 'y': SCREEN_H // 2}
        self.touch_active = False
        self.bundle_paths = globals().get('__browser_bundle_paths__', {})
        self.last_shell_output = ''
        self.last_status = ''

        self._build_widgets()
        self._attach_events()
        self._render()
        self._startup()

    def _build_widgets(self):
        research_cards = []
        for note in RESEARCH_NOTES:
            research_cards.append(
                '<div style="padding:12px 14px;border:1px solid #1e293b;border-radius:16px;background:#020617;color:#cbd5e1;font-size:13px;line-height:1.6;">'
                + html.escape(note)
                + '</div>'
            )

        self.header_html = widgets.HTML(
            value=(
                '<div style="padding:18px 20px;border:1px solid #1e293b;border-radius:24px;background:linear-gradient(135deg,#020617,#0f172a 55%,#172554);color:#f8fafc;">'
                '<div style="font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:#38bdf8;">Kaggle desktop rewrite</div>'
                '<div style="font-size:30px;font-weight:800;margin-top:8px;">Zorin-style Windows-like Linux for Kaggle</div>'
                '<div style="font-size:14px;line-height:1.75;color:#cbd5e1;margin-top:10px;max-width:960px;">'
                'This is a full rewrite aimed at the Kaggle notebook environment. It recreates a Zorin-like Windows-style desktop using XFCE, '
                'keeps state under <b>/kaggle/working/' + html.escape(STATE_DIR_NAME) + '</b>, fixes long-press/context-menu problems on the live screen, '
                'and adds download, run, clipboard, shell, and GitHub update tools.'
                '</div>'
                '</div>'
            )
        )
        self.research_html = widgets.HTML(
            value='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;">' + ''.join(research_cards) + '</div>'
        )

        self.status_html = widgets.HTML(value=html_message_box('info', 'Ready', 'Building Zorin-style Kaggle desktop UI...'))
        self.screen_widget = widgets.Image(
            format='png',
            layout=widgets.Layout(width='100%', max_width='1280px', height='auto', border='1px solid #334155'),
        )
        self.pointer_help_html = widgets.HTML(
            value=(
                '<div style="font-size:13px;line-height:1.7;color:#cbd5e1;">'
                '<b>Input fixes:</b> the live surface suppresses browser context-menu behavior, uses separate mouse-down and mouse-up actions for drag/hold, '
                'supports touch hold on mobile, throttles move spam, and reuses one screenshot file to avoid the old scrot filename bug.'
                '</div>'
            )
        )

        self.install_button = widgets.Button(description='Install / Repair', icon='wrench')
        self.start_desktop_button = widgets.Button(description='Start desktop', icon='desktop')
        self.apply_layout_button = widgets.Button(description='Apply Zorin layout', icon='paint-brush')
        self.open_browser_button = widgets.Button(description='Open browser', icon='globe')
        self.open_terminal_button = widgets.Button(description='Open terminal', icon='terminal')
        self.open_files_button = widgets.Button(description='Open files', icon='folder-open')
        self.refresh_screen_button = widgets.Button(description='Refresh screen', icon='camera')
        self.release_mouse_button = widgets.Button(description='Release mouse', icon='hand-paper-o')

        self.url_input = widgets.Text(
            value=self.state.get('last_url', URL_GOOGLE),
            description='URL',
            layout=widgets.Layout(width='100%'),
        )
        self.auto_refresh_toggle = widgets.ToggleButton(
            value=self.state.get('auto_refresh', True),
            description='Auto refresh',
            icon='refresh',
            layout=widgets.Layout(width='150px'),
        )
        self.refresh_interval = widgets.Dropdown(
            options=[('0.8s', 0.8), ('1.0s', 1.0), ('1.5s', 1.5), ('2.0s', 2.0), ('3.0s', 3.0)],
            value=self.state.get('refresh_seconds', 1.0),
            description='Every',
            layout=widgets.Layout(width='180px'),
        )

        self.quick_google_button = widgets.Button(description='Google')
        self.quick_github_button = widgets.Button(description='GitHub')
        self.quick_kaggle_button = widgets.Button(description='Kaggle')
        self.quick_zorin_button = widgets.Button(description='Zorin')
        self.quick_docs_button = widgets.Button(description='XFCE Docs')

        self.mouse_click_button = widgets.Button(description='Left click')
        self.mouse_double_click_button = widgets.Button(description='Double click')
        self.mouse_right_button = widgets.Button(description='Right click')
        self.scroll_up_button = widgets.Button(description='Scroll up')
        self.scroll_down_button = widgets.Button(description='Scroll down')

        self.key_input = widgets.Text(value='ctrl+l', description='Key', layout=widgets.Layout(width='100%'))
        self.send_key_button = widgets.Button(description='Send key', icon='keyboard-o')
        self.clipboard_area = widgets.Textarea(
            value=self.state.get('clipboard_text', ''),
            placeholder='Clipboard / paste / typing text',
            layout=widgets.Layout(width='100%', height='150px'),
        )
        self.clipboard_read_button = widgets.Button(description='Read remote clipboard', icon='download')
        self.clipboard_set_button = widgets.Button(description='Set remote clipboard', icon='upload')
        self.clipboard_paste_button = widgets.Button(description='Paste text', icon='paste')
        self.clipboard_type_button = widgets.Button(description='Type text', icon='keyboard-o')
        self.copy_output_button = widgets.Button(description='Copy shell output', icon='clipboard')

        self.download_url_input = widgets.Text(
            value=self.state.get('download_url', ''),
            description='URL',
            layout=widgets.Layout(width='100%'),
        )
        self.download_name_input = widgets.Text(
            value=self.state.get('download_name', ''),
            description='Name',
            layout=widgets.Layout(width='100%'),
        )
        self.download_button = widgets.Button(description='Download', icon='cloud-download')
        self.download_refresh_button = widgets.Button(description='Refresh list', icon='refresh')
        self.download_run_button = widgets.Button(description='Run / Open', icon='play')
        self.download_extract_button = widgets.Button(description='Extract', icon='archive')
        self.download_zip_button = widgets.Button(description='Zip all', icon='file-archive-o')
        self.file_selector = widgets.Dropdown(options=[('No files yet', '')], description='File', layout=widgets.Layout(width='100%'))
        self.downloads_html = widgets.HTML()
        self.download_links_output = widgets.Output()

        self.shell_input = widgets.Textarea(
            value=self.state.get('shell_command', 'ls -la /kaggle/working'),
            placeholder='Type a shell command',
            layout=widgets.Layout(width='100%', height='120px'),
        )
        self.shell_run_button = widgets.Button(description='Run command', icon='play')
        self.shell_output = widgets.Textarea(
            value='',
            placeholder='Shell output will appear here',
            layout=widgets.Layout(width='100%', height='200px'),
        )

        self.github_token_input = widgets.Password(value='', description='Token', layout=widgets.Layout(width='100%'))
        self.github_owner_input = widgets.Text(value=DEFAULT_OWNER, description='Owner', layout=widgets.Layout(width='100%'))
        self.github_repo_input = widgets.Text(value=DEFAULT_REPO, description='Repo', layout=widgets.Layout(width='100%'))
        self.github_branch_input = widgets.Text(value=DEFAULT_BRANCH, description='Branch', layout=widgets.Layout(width='100%'))
        self.github_prefix_input = widgets.Text(value=DEFAULT_PREFIX, description='Prefix', layout=widgets.Layout(width='100%'))
        self.github_update_button = widgets.Button(description='Push rewritten files', icon='github')
        self.github_result_html = widgets.HTML(value='')

        self.diagnostics_html = widgets.HTML()
        self.log_html = widgets.HTML(value=html_message_box('info', 'Activity log', 'Waiting for actions...'))

        self.session_box = widgets.VBox([
            widgets.HBox([
                self.install_button,
                self.start_desktop_button,
                self.apply_layout_button,
                self.open_browser_button,
                self.open_terminal_button,
                self.open_files_button,
                self.refresh_screen_button,
                self.release_mouse_button,
            ], layout=widgets.Layout(flex_flow='row wrap', gap='8px')),
            self.url_input,
            widgets.HBox([self.auto_refresh_toggle, self.refresh_interval], layout=widgets.Layout(gap='10px')),
            widgets.HBox([
                self.quick_google_button,
                self.quick_github_button,
                self.quick_kaggle_button,
                self.quick_zorin_button,
                self.quick_docs_button,
            ], layout=widgets.Layout(flex_flow='row wrap', gap='8px')),
        ])

        self.mouse_box = widgets.VBox([
            widgets.HBox([
                self.mouse_click_button,
                self.mouse_double_click_button,
                self.mouse_right_button,
                self.scroll_up_button,
                self.scroll_down_button,
            ], layout=widgets.Layout(flex_flow='row wrap', gap='8px')),
        ])

        self.clipboard_box = widgets.VBox([
            self.key_input,
            widgets.HBox([self.send_key_button], layout=widgets.Layout(gap='8px')),
            self.clipboard_area,
            widgets.HBox([
                self.clipboard_read_button,
                self.clipboard_set_button,
                self.clipboard_paste_button,
                self.clipboard_type_button,
                self.copy_output_button,
            ], layout=widgets.Layout(flex_flow='row wrap', gap='8px')),
        ])

        self.shell_box = widgets.VBox([
            self.shell_input,
            widgets.HBox([self.shell_run_button], layout=widgets.Layout(gap='8px')),
            self.shell_output,
        ])

        self.downloads_box = widgets.VBox([
            self.download_url_input,
            self.download_name_input,
            widgets.HBox([
                self.download_button,
                self.download_refresh_button,
                self.download_run_button,
                self.download_extract_button,
                self.download_zip_button,
            ], layout=widgets.Layout(flex_flow='row wrap', gap='8px')),
            self.file_selector,
            self.downloads_html,
            self.download_links_output,
        ])

        self.github_box = widgets.VBox([
            self.github_token_input,
            self.github_owner_input,
            self.github_repo_input,
            self.github_branch_input,
            self.github_prefix_input,
            widgets.HBox([self.github_update_button], layout=widgets.Layout(gap='8px')),
            self.github_result_html,
        ])

        self.diagnostics_box = widgets.VBox([
            self.diagnostics_html,
            self.log_html,
        ])

        self.accordion = widgets.Accordion(children=[
            self.session_box,
            self.mouse_box,
            self.clipboard_box,
            self.shell_box,
            self.downloads_box,
            self.github_box,
            self.diagnostics_box,
        ])
        for index, title in enumerate(['Session', 'Mouse', 'Clipboard + Keys', 'Shell', 'Downloads', 'GitHub', 'Diagnostics']):
            self.accordion.set_title(index, title)
        self.accordion.selected_index = 0

    def _attach_events(self):
        self.install_button.on_click(self._on_install)
        self.start_desktop_button.on_click(self._on_start_desktop)
        self.apply_layout_button.on_click(self._on_apply_layout)
        self.open_browser_button.on_click(self._on_open_browser)
        self.open_terminal_button.on_click(self._on_open_terminal)
        self.open_files_button.on_click(self._on_open_files)
        self.refresh_screen_button.on_click(self._on_refresh_screen)
        self.release_mouse_button.on_click(self._on_release_mouse)
        self.quick_google_button.on_click(lambda _: self._open_url(URL_GOOGLE))
        self.quick_github_button.on_click(lambda _: self._open_url(URL_GITHUB))
        self.quick_kaggle_button.on_click(lambda _: self._open_url(URL_KAGGLE))
        self.quick_zorin_button.on_click(lambda _: self._open_url(URL_ZORIN))
        self.quick_docs_button.on_click(lambda _: self._open_url(URL_XFCE_DOCS))
        self.mouse_click_button.on_click(lambda _: self._manual_click(1, 1))
        self.mouse_double_click_button.on_click(lambda _: self._manual_click(1, 2))
        self.mouse_right_button.on_click(lambda _: self._manual_click(3, 1))
        self.scroll_up_button.on_click(lambda _: self._manual_scroll(-6))
        self.scroll_down_button.on_click(lambda _: self._manual_scroll(6))
        self.send_key_button.on_click(self._on_send_key)
        self.clipboard_read_button.on_click(self._on_read_clipboard)
        self.clipboard_set_button.on_click(self._on_set_clipboard)
        self.clipboard_paste_button.on_click(self._on_paste_text)
        self.clipboard_type_button.on_click(self._on_type_text)
        self.copy_output_button.on_click(self._on_copy_shell_output)
        self.download_button.on_click(self._on_download)
        self.download_refresh_button.on_click(lambda _: self._refresh_downloads())
        self.download_run_button.on_click(self._on_run_selected_file)
        self.download_extract_button.on_click(self._on_extract_selected_file)
        self.download_zip_button.on_click(self._on_zip_downloads)
        self.shell_run_button.on_click(self._on_run_shell)
        self.github_update_button.on_click(self._on_push_github)
        self.auto_refresh_toggle.observe(self._on_auto_refresh_change, names='value')
        self.refresh_interval.observe(self._on_interval_change, names='value')

        if Event is not None:
            self.pointer_events = Event(
                source=self.screen_widget,
                watched_events=['mousedown', 'mouseup', 'mousemove', 'wheel', 'contextmenu', 'dragstart', 'touchstart', 'touchmove', 'touchend'],
                prevent_default_action=True,
                wait=20,
                throttle_or_debounce='throttle',
            )
            self.pointer_events.on_dom_event(self._on_surface_event)

    def _render(self):
        clear_output(wait=True)
        style_html = widgets.HTML(
            value=(
                '<style>'
                '.ipyevents-watched:focus{outline:1px solid rgba(56,189,248,.55)!important;}'
                '.widget-textarea textarea{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}'
                '</style>'
            )
        )
        display(widgets.VBox([
            style_html,
            self.header_html,
            self.research_html,
            self.status_html,
            self.screen_widget,
            self.pointer_help_html,
            self.accordion,
        ], layout=widgets.Layout(gap='14px')))

    def _startup(self):
        self._refresh_downloads()
        self._refresh_diagnostics()
        self._refresh_screen(silent=True)
        if self.auto_refresh_toggle.value:
            self._start_auto_refresh()
        self._set_status('success', 'Ready', 'Zorin-style Kaggle desktop UI loaded. State root: ' + self.paths['root'])

    def _save_state(self):
        self.state['last_url'] = self.url_input.value
        self.state['auto_refresh'] = bool(self.auto_refresh_toggle.value)
        self.state['refresh_seconds'] = float(self.refresh_interval.value)
        self.state['clipboard_text'] = self.clipboard_area.value
        self.state['download_url'] = self.download_url_input.value
        self.state['download_name'] = self.download_name_input.value
        self.state['shell_command'] = self.shell_input.value
        save_json(self.paths['state_json'], self.state)

    def _log(self, message_text):
        append_log('ui.log', message_text)
        self.log_html.value = html_message_box('info', 'Activity log', message_text)

    def _set_status(self, kind, title_text, body_text):
        self.last_status = body_text
        self.status_html.value = html_message_box(kind, title_text, body_text)
        self._log(title_text + ': ' + body_text)
        self._refresh_diagnostics()

    def _refresh_diagnostics(self):
        install_report = load_json(self.paths['install_report'], {})
        session_report = load_json(self.paths['session_report'], {})
        cpu = detect_cpu_info()
        browser = find_browser_binary() or 'not found'
        downloads = list_download_files()
        active_title = get_active_window_title() or '(no active window title yet)'

        facts = [
            ('State root', self.paths['root']),
            ('Persistent', 'Yes' if self.paths['persistent'] else 'No'),
            ('Display', DISPLAY_VALUE),
            ('Screen', str(SCREEN_W) + 'x' + str(SCREEN_H)),
            ('Browser', browser),
            ('Active window', active_title),
            ('Downloads count', str(len(downloads))),
            ('Install report', self.paths['install_report']),
            ('Session report', self.paths['session_report']),
            ('CPU', (cpu.get('cpu_model') or 'Unknown') + ' • ' + str(cpu.get('cpu_count') or 0) + ' cores • ' + str(cpu.get('memory_gb') or 0) + ' GB RAM'),
            ('Last install timestamp', install_report.get('timestamp', 'Not run yet')),
            ('Last session timestamp', session_report.get('timestamp', 'Not started yet')),
        ]
        card_items = []
        for label, value in facts:
            card_items.append(
                '<div style="padding:12px 14px;border:1px solid #1e293b;border-radius:14px;background:#020617;">'
                '<div style="font-size:12px;color:#38bdf8;text-transform:uppercase;letter-spacing:.08em;">' + html.escape(label) + '</div>'
                '<div style="font-size:13px;line-height:1.65;color:#e2e8f0;margin-top:4px;white-space:pre-wrap;">' + html.escape(str(value)) + '</div>'
                '</div>'
            )
        self.diagnostics_html.value = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;">' + ''.join(card_items) + '</div>'

    def _refresh_screen(self, silent=False):
        with self.capture_lock:
            image_bytes = capture_screen_bytes()
            self.screen_widget.value = image_bytes
        if not silent:
            self._set_status('success', 'Screen updated', 'Live desktop surface refreshed at ' + now_text())

    def _start_auto_refresh(self):
        self.auto_refresh_stop.clear()
        if self.auto_refresh_thread and self.auto_refresh_thread.is_alive():
            return

        def worker():
            while not self.auto_refresh_stop.is_set():
                time.sleep(float(self.refresh_interval.value))
                if self.auto_refresh_stop.is_set():
                    break
                try:
                    self._refresh_screen(silent=True)
                except Exception as exc:
                    append_log('ui.log', 'auto refresh error: ' + str(exc))

        self.auto_refresh_thread = threading.Thread(target=worker, daemon=True)
        self.auto_refresh_thread.start()

    def _stop_auto_refresh(self):
        self.auto_refresh_stop.set()

    def _on_auto_refresh_change(self, change):
        if change['new']:
            self._start_auto_refresh()
            self._set_status('info', 'Auto refresh enabled', 'Screen will refresh every ' + str(self.refresh_interval.value) + ' seconds.')
        else:
            self._stop_auto_refresh()
            self._set_status('warning', 'Auto refresh disabled', 'Automatic screen updates are paused.')
        self._save_state()

    def _on_interval_change(self, change):
        self._save_state()
        if self.auto_refresh_toggle.value:
            self._stop_auto_refresh()
            self._start_auto_refresh()

    def _open_url(self, url_value):
        self.url_input.value = url_value
        self._save_state()
        self._on_open_browser(None)

    def _manual_click(self, button_value, repeat):
        click(button_value, repeat=repeat)
        self._set_status('success', 'Mouse action', 'Sent click command for button ' + str(button_value) + '.')

    def _manual_scroll(self, amount_value):
        scroll_vertical(amount_value)
        self._set_status('success', 'Scroll sent', 'Sent vertical scroll command.')

    def _release_all_pressed(self):
        for button_value in sorted(self.pressed_buttons):
            mouse_up(button_value)
        self.pressed_buttons = set()
        self.touch_active = False

    def _event_button_to_x11(self, event):
        button_index = int(event.get('button', 0))
        mapping = {0: 1, 1: 2, 2: 3}
        return mapping.get(button_index, 1)

    def _coords_from_event(self, event):
        if 'dataX' in event and 'dataY' in event:
            x_value = int(event.get('dataX') or 0)
            y_value = int(event.get('dataY') or 0)
        else:
            relative_x = float(event.get('relativeX', 0) or 0)
            relative_y = float(event.get('relativeY', 0) or 0)
            width_value = float(event.get('boundingRectWidth', 1) or 1)
            height_value = float(event.get('boundingRectHeight', 1) or 1)
            x_value = int((relative_x / max(1.0, width_value)) * SCREEN_W)
            y_value = int((relative_y / max(1.0, height_value)) * SCREEN_H)
        x_value = max(0, min(SCREEN_W - 1, x_value))
        y_value = max(0, min(SCREEN_H - 1, y_value))
        self.last_pointer = {'x': x_value, 'y': y_value}
        return x_value, y_value

    def _touch_coords(self, event):
        touches = event.get('changedTouches') or event.get('touches') or []
        if not touches:
            return self.last_pointer['x'], self.last_pointer['y']
        touch = touches[0]
        if 'dataX' in touch and 'dataY' in touch:
            x_value = int(touch.get('dataX') or 0)
            y_value = int(touch.get('dataY') or 0)
        else:
            relative_x = float(touch.get('relativeX', 0) or 0)
            relative_y = float(touch.get('relativeY', 0) or 0)
            width_value = float(event.get('boundingRectWidth', 1) or 1)
            height_value = float(event.get('boundingRectHeight', 1) or 1)
            x_value = int((relative_x / max(1.0, width_value)) * SCREEN_W)
            y_value = int((relative_y / max(1.0, height_value)) * SCREEN_H)
        x_value = max(0, min(SCREEN_W - 1, x_value))
        y_value = max(0, min(SCREEN_H - 1, y_value))
        self.last_pointer = {'x': x_value, 'y': y_value}
        return x_value, y_value

    def _on_surface_event(self, event):
        try:
            event_type = event.get('type', '')
            if event_type == 'dragstart':
                return

            if event_type.startswith('touch'):
                x_value, y_value = self._touch_coords(event)
                move_mouse(x_value, y_value)
                if event_type == 'touchstart' and not self.touch_active:
                    mouse_down(1)
                    self.pressed_buttons.add(1)
                    self.touch_active = True
                elif event_type == 'touchend' and self.touch_active:
                    mouse_up(1)
                    self.pressed_buttons.discard(1)
                    self.touch_active = False
                return

            x_value, y_value = self._coords_from_event(event)
            move_mouse(x_value, y_value)

            if event_type == 'mousedown':
                button_value = self._event_button_to_x11(event)
                mouse_down(button_value)
                self.pressed_buttons.add(button_value)
            elif event_type == 'mouseup':
                button_value = self._event_button_to_x11(event)
                mouse_up(button_value)
                self.pressed_buttons.discard(button_value)
            elif event_type == 'wheel':
                delta_y = float(event.get('deltaY', 0) or 0)
                scroll_vertical(-4 if delta_y < 0 else 4)
            elif event_type == 'contextmenu':
                click(3)
        except Exception as exc:
            append_log('ui.log', 'surface event error: ' + str(exc))

    def _on_install(self, _):
        self._save_state()
        try:
            report = install_or_repair_stack(include_browser=True)
            browser_name = report.get('browser_found') or 'not found'
            self._set_status('success', 'Install / repair finished', 'Packages checked. Browser: ' + str(browser_name) + '. Report saved to ' + self.paths['install_report'])
        except Exception as exc:
            self._set_status('error', 'Install failed', str(exc))

    def _on_start_desktop(self, _):
        self._save_state()
        try:
            report = ensure_desktop_session()
            self._refresh_screen(silent=True)
            self._set_status('success', 'Desktop started', 'Desktop session ready on ' + report.get('display', DISPLAY_VALUE) + ' and saved under ' + self.paths['root'])
        except Exception as exc:
            self._set_status('error', 'Desktop start failed', str(exc))

    def _on_apply_layout(self, _):
        try:
            report = apply_zorin_layout()
            self._refresh_screen(silent=True)
            self._set_status('success', 'Zorin layout applied', 'Wallpaper, theme, panel, and desktop shortcuts refreshed. Wallpaper: ' + report.get('wallpaper_path', ''))
        except Exception as exc:
            self._set_status('error', 'Layout apply failed', str(exc))

    def _on_open_browser(self, _):
        self._save_state()
        try:
            result = launch_browser(self.url_input.value)
            self._set_status('success', 'Browser launched', 'Opened ' + result.get('url', self.url_input.value))
        except Exception as exc:
            self._set_status('error', 'Browser launch failed', str(exc))

    def _on_open_terminal(self, _):
        try:
            result = launch_terminal()
            self._set_status('success', 'Terminal launched', 'Started ' + result.get('terminal', 'terminal'))
        except Exception as exc:
            self._set_status('error', 'Terminal launch failed', str(exc))

    def _on_open_files(self, _):
        try:
            result = launch_file_manager(self.paths['downloads_dir'])
            self._set_status('success', 'File manager launched', 'Opened ' + result.get('target', self.paths['downloads_dir']))
        except Exception as exc:
            self._set_status('error', 'File manager launch failed', str(exc))

    def _on_refresh_screen(self, _):
        try:
            self._refresh_screen(silent=False)
        except Exception as exc:
            self._set_status('error', 'Refresh failed', str(exc))

    def _on_release_mouse(self, _):
        self._release_all_pressed()
        self._set_status('warning', 'Mouse released', 'Released any held mouse buttons.')

    def _on_send_key(self, _):
        result = send_key(self.key_input.value)
        if result.get('ok'):
            self._set_status('success', 'Key sent', 'Sent ' + self.key_input.value)
        else:
            self._set_status('error', 'Key send failed', result.get('stderr') or result.get('message') or 'Unknown error')

    def _on_read_clipboard(self, _):
        text_value = get_clipboard_text()
        self.clipboard_area.value = text_value
        self._save_state()
        self._set_status('success', 'Clipboard loaded', 'Remote clipboard text loaded into the text area.')

    def _on_set_clipboard(self, _):
        result = set_clipboard_text(self.clipboard_area.value)
        self._save_state()
        if result.get('ok'):
            self._set_status('success', 'Clipboard updated', 'Remote clipboard was updated.')
        else:
            self._set_status('error', 'Clipboard update failed', result.get('stderr') or result.get('message') or 'Unknown error')

    def _on_paste_text(self, _):
        result = smart_paste_text(self.clipboard_area.value)
        self._save_state()
        if result.get('ok'):
            self._set_status('success', 'Paste sent', 'Tried terminal-style paste shortcuts after writing the remote clipboard.')
        else:
            self._set_status('warning', 'Paste may have failed', 'Try Type text if the target app ignores paste shortcuts.')

    def _on_type_text(self, _):
        result = type_text(self.clipboard_area.value)
        self._save_state()
        if result.get('ok'):
            self._set_status('success', 'Typed text', 'Injected the text directly as keystrokes.')
        else:
            self._set_status('error', 'Typing failed', result.get('stderr') or result.get('message') or 'Unknown error')

    def _on_run_shell(self, _):
        self._save_state()
        command_text = self.shell_input.value.strip()
        if not command_text:
            self._set_status('warning', 'No command', 'Type a shell command first.')
            return
        result = run_shell(command_text, timeout=3600)
        output_parts = [
            '$ ' + command_text,
            '',
            result.get('stdout', ''),
        ]
        stderr_text = result.get('stderr', '').strip()
        if stderr_text:
            output_parts.extend(['', '[stderr]', stderr_text])
        output_parts.extend(['', '[exit code] ' + str(result.get('returncode', 1))])
        final_output = '\n'.join(part for part in output_parts if part is not None)
        self.shell_output.value = final_output
        self.last_shell_output = final_output
        if result.get('ok'):
            self._set_status('success', 'Command completed', 'Shell command finished successfully.')
        else:
            self._set_status('warning', 'Command finished with errors', 'Exit code ' + str(result.get('returncode', 1)) + '. You can still copy the output.')

    def _copy_text_to_browser_clipboard(self, text_value):
        safe_text = json.dumps(text_value)
        display(Javascript(
            '(async()=>{'
            'try{'
            'if(navigator.clipboard&&window.isSecureContext){await navigator.clipboard.writeText(' + safe_text + ');}'
            'else{const area=document.createElement("textarea");area.value=' + safe_text + ';document.body.appendChild(area);area.select();document.execCommand("copy");area.remove();}'
            '}catch(err){console.error(err);}'
            '})();'
        ))

    def _on_copy_shell_output(self, _):
        text_value = self.shell_output.value or self.last_shell_output or ''
        self._copy_text_to_browser_clipboard(text_value)
        self._set_status('success', 'Output copied', 'Tried to copy shell output into your browser clipboard.')

    def _refresh_downloads(self):
        files = list_download_files()
        options = [('No files yet', '')] if not files else [(item['name'] + ' (' + item['size_text'] + ')', item['name']) for item in files]
        self.file_selector.options = options
        if files:
            current_names = {value for _, value in options}
            current_value = self.file_selector.value if self.file_selector.value in current_names else files[0]['name']
            self.file_selector.value = current_value
        self.downloads_html.value = list_download_files_html()
        self.download_links_output.clear_output(wait=True)
        with self.download_links_output:
            display(FileLinks(self.paths['downloads_dir']))
        self._refresh_diagnostics()

    def _on_download(self, _):
        self._save_state()
        try:
            result = download_file(self.download_url_input.value, self.download_name_input.value)
            if result.get('ok'):
                self._refresh_downloads()
                self._set_status('success', 'Download finished', 'Saved ' + result.get('name', '') + ' into ' + self.paths['downloads_dir'])
            else:
                self._set_status('error', 'Download failed', result.get('message') or str(result.get('result') or 'Unknown error'))
        except Exception as exc:
            self._set_status('error', 'Download failed', str(exc))

    def _selected_file(self):
        return (self.file_selector.value or '').strip()

    def _on_run_selected_file(self, _):
        file_name = self._selected_file()
        if not file_name:
            self._set_status('warning', 'No file selected', 'Choose a file first.')
            return
        try:
            result = run_downloaded_file(file_name)
            self._refresh_downloads()
            self._set_status('success', 'Run / open requested', 'Handled ' + file_name + ' with mode ' + str(result.get('mode', 'auto')))
        except Exception as exc:
            self._set_status('error', 'Run / open failed', str(exc))

    def _on_extract_selected_file(self, _):
        file_name = self._selected_file()
        if not file_name:
            self._set_status('warning', 'No file selected', 'Choose an archive first.')
            return
        try:
            result = extract_archive(file_name)
            self._refresh_downloads()
            self._set_status('success', 'Archive extracted', 'Extracted into ' + result.get('target_dir', ''))
        except Exception as exc:
            self._set_status('error', 'Extract failed', str(exc))

    def _on_zip_downloads(self, _):
        try:
            zip_path = zip_downloads('zorin_kaggle_downloads.zip')
            self._refresh_downloads()
            self._set_status('success', 'Downloads zipped', 'Created ' + zip_path)
        except Exception as exc:
            self._set_status('error', 'Zip failed', str(exc))

    def _collect_push_files(self):
        file_map = {}
        ordered = [
            'README.md',
            'kaggle_launcher.py',
            'browser_controller_main.py',
            'browser_controller_support.py',
            'browser_controller_full.py',
        ]
        for file_name in ordered:
            source_path = self.bundle_paths.get(file_name, file_name)
            file_map[file_name] = file_read_text(source_path, file_read_text(file_name, ''))
        return file_map

    def _on_push_github(self, _):
        token_value = self.github_token_input.value.strip()
        owner_value = self.github_owner_input.value.strip() or DEFAULT_OWNER
        repo_value = self.github_repo_input.value.strip() or DEFAULT_REPO
        branch_value = self.github_branch_input.value.strip() or DEFAULT_BRANCH
        prefix_value = self.github_prefix_input.value.strip()
        if not token_value:
            self._set_status('warning', 'Missing token', 'Paste a GitHub token with contents write access.')
            return
        try:
            user_info = github_validate_token(token_value)
            repo_info = github_check_repo_access(token_value, owner_value, repo_value)
            results = github_upsert_many(token_value, owner_value, repo_value, branch_value, self._collect_push_files(), prefix=prefix_value)
            self.github_result_html.value = html_message_box(
                'success',
                'GitHub update completed',
                'User: {user}\nRepo: {repo}\nBranch: {branch}\nFiles updated: {count}'.format(
                    user=user_info.get('login', ''),
                    repo=repo_info.get('full_name', owner_value + '/' + repo_value),
                    branch=branch_value,
                    count=len(results),
                ),
            )
            self._set_status('success', 'GitHub push completed', 'Updated ' + str(len(results)) + ' files in ' + owner_value + '/' + repo_value)
        except Exception as exc:
            self.github_result_html.value = html_message_box('error', 'GitHub update failed', str(exc))
            self._set_status('error', 'GitHub push failed', str(exc))


try:
    ZorinKaggleDesktopApp()
except Exception as exc:
    display(HTML('<pre style="white-space:pre-wrap;color:#ef4444;">' + html.escape(traceback.format_exc()) + '</pre>'))
    raise
