# ═══════════════════════════════════════════════════════════════════════════════
# 🖥️  KAGGLE BROWSER CONTROLLER v2.0
# ═══════════════════════════════════════════════════════════════════════════════
# Chrome + Xvfb automation with live screenshots & click support
# Works on Kaggle (TPU/P100), Colab, Paperspace, etc.
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess
import os
import sys
import time
import threading
import re
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
try:
    import xvfbwrapper
    from PIL import Image
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "xvfbwrapper", "Pillow", "requests"])
    import xvfbwrapper
    from PIL import Image
    import requests

try:
    import ipywidgets as widgets
    from IPython.display import display, HTML, clear_output
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ipywidgets"])
    import ipywidgets as widgets
    from IPython.display import display, HTML, clear_output

# ═══════════════════════════════════════════════════════════════════════════════
# SETUP ENVIRONMENT
# ═══════════════════════════════════════════════════════════════════════════════
os.environ["DISPLAY"] = ":99"
os.environ["XDG_RUNTIME_DIR"] = "/tmp/xdg-runtime"
os.environ["XAUTHORITY"] = "/tmp/xauthority"
subprocess.run(["mkdir", "-p", "/tmp/xdg-runtime"], capture_output=True)
subprocess.run(["mkdir", "-p", "/tmp/chrome-downloads"], capture_output=True)
subprocess.run(["touch", "/tmp/xauthority"], capture_output=True)

FRAME_COUNT = 0
LAST_ACTION = "Ready"
SCREEN_W, SCREEN_H = 1280, 800
IMG_W, IMG_H = 1280, 800
SCREENSHOT_INTERVAL = 3
screenshot_lock = threading.Lock()
vdisplay = None
chrome_proc = None
screenshot_thread = None
stop_screenshot = threading.Event()

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def run(cmd, check=False):
    if isinstance(cmd, str):
        cmd = "env DISPLAY=:99 " + cmd
        shell = True
        sh_cmd = cmd
    else:
        cmd = ["env", "DISPLAY=:99"] + cmd
        shell = False
        sh_cmd = " ".join(cmd)
    r = subprocess.run(sh_cmd if shell else cmd, shell=shell, capture_output=True, text=True)
    if check and r.returncode != 0:
        print("WARN: " + r.stderr.strip()[:100])
    return r

def run_bg(cmd):
    if isinstance(cmd, str):
        cmd = "env DISPLAY=:99 " + cmd + " &"
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        cmd = ["env", "DISPLAY=:99"] + cmd
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def log_action(msg):
    global LAST_ACTION
    LAST_ACTION = msg
    print("[ACTION] " + msg)

def get_xdotool():
    return ["xvfb-run", "-a", "--server-num=99", "xdotool"]

# ═══════════════════════════════════════════════════════════════════════════════
# XDOTOOL WRAPPERS
# ═══════════════════════════════════════════════════════════════════════════════
def xd_mousemove(x, y):
    run(["xdotool", "mousemove", str(x), str(y)])

def xd_click(btn=1):
    run(["xdotool", "click", str(btn)])

def xd_key(key):
    run(["xdotool", "key", key])

def xd_type(text):
    for c in text:
        if c == " ":
            run(["xdotool", "type", "--", " "])
        elif c == "\n":
            run(["xdotool", "key", "Return"])
        else:
            run(["xdotool", "type", "--", c])

def xd_sleep_click(x, y, btn=1, delay=0.1):
    xd_mousemove(x, y)
    time.sleep(delay)
    xd_click(btn)

# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION
# ═══════════════════════════════════════════════════════════════════════════════
def nav_go(url):
    log_action("Going to: " + url)
    run(["xdotool", "key", "ctrl+l"])
    time.sleep(0.2)
    run(["xdotool", "type", "--", url])
    time.sleep(0.1)
    run(["xdotool", "key", "Return"])

def nav_back():
    log_action("Navigate back")
    run(["xdotool", "key", "Alt+Left"])
    time.sleep(0.3)

def nav_forward():
    log_action("Navigate forward")
    run(["xdotool", "key", "Alt+Right"])
    time.sleep(0.3)

def nav_reload():
    log_action("Reload page")
    run(["xdotool", "key", "F5"])
    time.sleep(0.5)

def nav_home():
    log_action("Go home")
    run(["xdotool", "key", "Alt+Home"])

# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD
# ═══════════════════════════════════════════════════════════════════════════════
def key_enter():
    log_action("Press Enter")
    xd_key("Return")

def key_escape():
    log_action("Press Escape")
    xd_key("Escape")

def key_tab():
    log_action("Press Tab")
    xd_key("Tab")

def key_up():
    log_action("Press Arrow Up")
    xd_key("Up")

def key_down():
    log_action("Press Arrow Down")
    xd_key("Down")

def key_pageup():
    log_action("Page Up")
    xd_key("Page_Up")

def key_pagedown():
    log_action("Page Down")
    xd_key("Page_Down")

# ═══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD & SELECTION
# ═══════════════════════════════════════════════════════════════════════════════
def clip_copy():
    log_action("Copy (Ctrl+C)")
    xd_key("ctrl+c")
    time.sleep(0.1)

def clip_paste():
    log_action("Paste (Ctrl+V)")
    xd_key("ctrl+v")
    time.sleep(0.1)

def clip_select_all():
    log_action("Select All (Ctrl+A)")
    xd_key("ctrl+a")

# ═══════════════════════════════════════════════════════════════════════════════
# SCROLL & ZOOM
# ═══════════════════════════════════════════════════════════════════════════════
def scroll_up():
    log_action("Scroll up")
    run(["xdotool", "click", "4"])

def scroll_down():
    log_action("Scroll down")
    run(["xdotool", "click", "5"])

def zoom_in():
    log_action("Zoom in (Ctrl++)")
    xd_key("ctrl+plus")

def zoom_out():
    log_action("Zoom out (Ctrl+-)")
    xd_key("ctrl+minus")

# ═══════════════════════════════════════════════════════════════════════════════
# RIGHT CLICK
# ═══════════════════════════════════════════════════════════════════════════════
def do_right_click():
    log_action("Right click")
    xd_click(3)

# ═══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT
# ═══════════════════════════════════════════════════════════════════════════════
def capture_screenshot():
    global FRAME_COUNT
    path = "/tmp/frame.png"
    
    # Try scrot first
    r = run("scrot " + path + " -o -a 0,0," + str(SCREEN_W) + "," + str(SCREEN_H))
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    
    # Try gnome-screenshot
    r = run("DISPLAY=:99 gnome-screenshot -f " + path + " -w")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    
    # Try import (ImageMagick)
    r = run("import -window root -display :99 " + path)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    
    # Fallback: use Python PIL with display capture
    try:
        import gtk
        gdk = gtk.gdk
        gdk.display_get_default()
        pixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, True, 8, SCREEN_W, SCREEN_H)
        pixbuf.get_from_drawable(gdk.get_default_root_window(), gdk.colormap_get_system(), 0, 0, 0, 0, SCREEN_W, SCREEN_H)
        pixbuf.save(path, "png")
    except:
        pass
    
    return path if os.path.exists(path) else None

def screenshot_worker(img_widget, status_widget):
    global FRAME_COUNT, SCREENSHOT_INTERVAL
    while not stop_screenshot.is_set():
        path = capture_screenshot()
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                FRAME_COUNT += 1
                with screenshot_lock:
                    img_widget.value = data
                status_widget.value = "Frame #" + str(FRAME_COUNT) + " - " + LAST_ACTION
            except Exception as e:
                status_widget.value = "Screenshot error: " + str(e)[:50]
        time.sleep(SCREENSHOT_INTERVAL)

def start_screenshot(img_widget, status_widget):
    global screenshot_thread, stop_screenshot
    stop_screenshot = threading.Event()
    screenshot_thread = threading.Thread(target=screenshot_worker, args=(img_widget, status_widget), daemon=True)
    screenshot_thread.start()

def stop_screenshot_thread():
    global stop_screenshot
    if stop_screenshot:
        stop_screenshot.set()
    if screenshot_thread:
        time.sleep(0.5)

def set_interval(secs):
    global SCREENSHOT_INTERVAL
    SCREENSHOT_INTERVAL = secs
    log_action("Screenshot interval: " + str(secs) + "s")

# ═══════════════════════════════════════════════════════════════════════════════
# CLICK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
def _ag_click(coords_str):
    try:
        parts = coords_str.split(",")
        img_x = int(parts[0])
        img_y = int(parts[1])
        scale_x = SCREEN_W / IMG_W
        scale_y = SCREEN_H / IMG_H
        scr_x = int(img_x * scale_x)
        scr_y = int(img_y * scale_y)
        xd_sleep_click(scr_x, scr_y, 1)
        log_action("Left click at (" + str(scr_x) + ", " + str(scr_y) + ")")
    except Exception as e:
        log_action("Click error: " + str(e))

def _ag_rclick(coords_str):
    try:
        parts = coords_str.split(",")
        img_x = int(parts[0])
        img_y = int(parts[1])
        scale_x = SCREEN_W / IMG_W
        scale_y = SCREEN_H / IMG_H
        scr_x = int(img_x * scale_x)
        scr_y = int(img_y * scale_y)
        xd_sleep_click(scr_x, scr_y, 3)
        log_action("Right click at (" + str(scr_x) + ", " + str(scr_y) + ")")
    except Exception as e:
        log_action("Right-click error: " + str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# HEARTBEAT (keeps Kaggle alive)
# ═══════════════════════════════════════════════════════════════════════════════
def start_heartbeat():
    def beat():
        while True:
            print("[HEARTBEAT] Session alive - " + datetime.now().strftime("%H:%M:%S"))
            time.sleep(25)
    t = threading.Thread(target=beat, daemon=True)
    t.start()

# ═══════════════════════════════════════════════════════════════════════════════
# TYPE TEXT
# ═══════════════════════════════════════════════════════════════════════════════
def type_text(text):
    if not text:
        return
    log_action("Typing: " + text[:30] + ("..." if len(text) > 30 else ""))
    xd_type(text)

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT SEND
# ═══════════════════════════════════════════════════════════════════════════════
def send_chat(chat_widget, status_widget):
    text = chat_widget.value.strip()
    if text:
        type_text(text)
        chat_widget.value = ""
        key_enter()
        status_widget.value = "Frame #" + str(FRAME_COUNT) + " - Sent: " + text[:30]

# ═══════════════════════════════════════════════════════════════════════════════
# CREATE WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════
def create_widgets():
    global IMG_W, IMG_H
    
    # Screenshot image
    img = widgets.Image(format="png", width="100%", layout=widgets.Layout(padding="2px"))
    
    # Status label
    status = widgets.Label(value="Initializing...", 
                          layout=widgets.Layout(padding="8px", font_size="14px"),
                          style={"background_color": "#1a1a2e", "color": "#00ff88"})
    
    # URL bar
    url_input = widgets.Text(value="https://www.google.com",
                             placeholder="Enter URL...",
                             layout=widgets.Layout(width="85%", padding="4px"),
                             style={"font_size": "14px"})
    
    # Type text input
    type_input = widgets.Text(value="",
                              placeholder="Type text and press Enter...",
                              layout=widgets.Layout(width="85%", padding="4px"),
                              style={"font_size": "14px"})
    
    # Chat textarea
    chat = widgets.Textarea(value="",
                           placeholder="Chat message (Ctrl+Enter to send)...",
                           layout=widgets.Layout(width="100%", height="60px", padding="4px"),
                           style={"font_size": "13px"})
    
    # Row 1: Navigation
    btn_go = widgets.Button(description="", tooltip="Go (Ctrl+L)", 
                           button_style="success", icon="globe",
                           layout=widgets.Layout(width="50px", height="40px"))
    btn_back = widgets.Button(description="", tooltip="Back (Alt+Left)", 
                             icon="arrow-left",
                             layout=widgets.Layout(width="50px", height="40px"))
    btn_fwd = widgets.Button(description="", tooltip="Forward (Alt+Right)", 
                            icon="arrow-right",
                            layout=widgets.Layout(width="50px", height="40px"))
    btn_reload = widgets.Button(description="", tooltip="Reload (F5)", 
                               icon="refresh",
                               layout=widgets.Layout(width="50px", height="40px"))
    btn_home = widgets.Button(description="", tooltip="Home (Alt+Home)", 
                             icon="home",
                             layout=widgets.Layout(width="50px", height="40px"))
    
    # Row 2: Keys
    btn_enter = widgets.Button(description="", tooltip="Enter", 
                              icon="level-down-alt rotate-90",
                              layout=widgets.Layout(width="40px", height="40px"))
    btn_esc = widgets.Button(description="Esc", tooltip="Escape",
                            layout=widgets.Layout(width="40px", height="40px"))
    btn_tab = widgets.Button(description="", tooltip="Tab", icon="arrows-alt-h",
                            layout=widgets.Layout(width="40px", height="40px"))
    btn_up = widgets.Button(description="", tooltip="Arrow Up", icon="arrow-up",
                           layout=widgets.Layout(width="40px", height="40px"))
    btn_down = widgets.Button(description="", tooltip="Arrow Down", icon="arrow-down",
                             layout=widgets.Layout(width="40px", height="40px"))
    btn_pgup = widgets.Button(description="", tooltip="Page Up", icon="angle-double-up",
                             layout=widgets.Layout(width="40px", height="40px"))
    btn_pgdn = widgets.Button(description="", tooltip="Page Down", icon="angle-double-down",
                             layout=widgets.Layout(width="40px", height="40px"))
    
    # Row 3: Tools
    btn_copy = widgets.Button(description="", tooltip="Copy (Ctrl+C)", icon="copy",
                              layout=widgets.Layout(width="40px", height="40px"))
    btn_paste = widgets.Button(description="", tooltip="Paste (Ctrl+V)", icon="paste",
                              layout=widgets.Layout(width="40px", height="40px"))
    btn_sela = widgets.Button(description="", tooltip="Select All (Ctrl+A)", icon="asterisk",
                              layout=widgets.Layout(width="40px", height="40px"))
    btn_rclick = widgets.Button(description="", tooltip="Right Click", icon="hand-pointer",
                               layout=widgets.Layout(width="40px", height="40px"))
    btn_scrl_up = widgets.Button(description="", tooltip="Scroll Up", icon="arrow-up",
                                 layout=widgets.Layout(width="40px", height="40px"))
    btn_scrl_dn = widgets.Button(description="", tooltip="Scroll Down", icon="arrow-down",
                                 layout=widgets.Layout(width="40px", height="40px"))
    btn_zoom_in = widgets.Button(description="", tooltip="Zoom In (Ctrl++)", icon="search-plus",
                                 layout=widgets.Layout(width="40px", height="40px"))
    btn_zoom_out = widgets.Button(description="", tooltip="Zoom Out (Ctrl+-)", icon="search-minus",
                                  layout=widgets.Layout(width="40px", height="40px"))
    btn_fast = widgets.Button(description="", tooltip="Fast 1s", icon="bolt",
                             button_style="warning",
                             layout=widgets.Layout(width="50px", height="40px"))
    btn_slow = widgets.Button(description="", tooltip="Slow 5s", icon="clock",
                              button_style="info",
                              layout=widgets.Layout(width="50px", height="40px"))
    
    # Type button
    btn_type_go = widgets.Button(description="Type", tooltip="Type and Enter",
                                 button_style="primary",
                                 layout=widgets.Layout(width="14%", height="40px"))
    
    # Chat send button
    btn_chat_send = widgets.Button(description="SEND", tooltip="Send (Ctrl+Enter)",
                                   button_style="primary",
                                   layout=widgets.Layout(width="100px", height="60px"))
    
    return {
        "img": img, "status": status, "url": url_input, "type": type_input,
        "chat": chat, "btn_go": btn_go, "btn_back": btn_back, "btn_fwd": btn_fwd,
        "btn_reload": btn_reload, "btn_home": btn_home, "btn_enter": btn_enter,
        "btn_esc": btn_esc, "btn_tab": btn_tab, "btn_up": btn_up, "btn_down": btn_down,
        "btn_pgup": btn_pgup, "btn_pgdn": btn_pgdn, "btn_copy": btn_copy,
        "btn_paste": btn_paste, "btn_sela": btn_sela, "btn_rclick": btn_rclick,
        "btn_scrl_up": btn_scrl_up, "btn_scrl_dn": btn_scrl_dn, "btn_zoom_in": btn_zoom_in,
        "btn_zoom_out": btn_zoom_out, "btn_fast": btn_fast, "btn_slow": btn_slow,
        "btn_type_go": btn_type_go, "btn_chat_send": btn_chat_send
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ATTACH HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
def attach_handlers(w, img, status):
    # Navigation
    w["btn_go"].on_click(lambda b: nav_go(w["url"].value))
    w["btn_back"].on_click(lambda b: nav_back())
    w["btn_fwd"].on_click(lambda b: nav_forward())
    w["btn_reload"].on_click(lambda b: nav_reload())
    w["btn_home"].on_click(lambda b: nav_home())
    
    # Keys
    w["btn_enter"].on_click(lambda b: key_enter())
    w["btn_esc"].on_click(lambda b: key_escape())
    w["btn_tab"].on_click(lambda b: key_tab())
    w["btn_up"].on_click(lambda b: key_up())
    w["btn_down"].on_click(lambda b: key_down())
    w["btn_pgup"].on_click(lambda b: key_pageup())
    w["btn_pgdn"].on_click(lambda b: key_pagedown())
    
    # Tools
    w["btn_copy"].on_click(lambda b: clip_copy())
    w["btn_paste"].on_click(lambda b: clip_paste())
    w["btn_sela"].on_click(lambda b: clip_select_all())
    w["btn_rclick"].on_click(lambda b: do_right_click())
    w["btn_scrl_up"].on_click(lambda b: scroll_up())
    w["btn_scrl_dn"].on_click(lambda b: scroll_down())
    w["btn_zoom_in"].on_click(lambda b: zoom_in())
    w["btn_zoom_out"].on_click(lambda b: zoom_out())
    w["btn_fast"].on_click(lambda b: set_interval(1))
    w["btn_slow"].on_click(lambda b: set_interval(5))
    
    # Type
    w["btn_type_go"].on_click(lambda b: type_text(w["type"].value))
    w["type"].on_submit(lambda b: type_text(w["type"].value))
    
    # Chat
    w["btn_chat_send"].on_click(lambda b: send_chat(w["chat"], status))
    def chat_send(e):
        if e.ctrl_key:
            send_chat(w["chat"], status)
    w["chat"].observe(lambda e: chat_send(e) if hasattr(e, "ctrl_key") else None)

# ═══════════════════════════════════════════════════════════════════════════════
# JAVASCRIPT INJECTION
# ═══════════════════════════════════════════════════════════════════════════════
def inject_javascript(img):
    js = """
    <script>
    (function() {
        var img = null;
        function findImg() {
            var el = document.querySelector('img[data-bc-original]');
            if (!el) el = document.querySelector('.widget-image');
            if (!el) el = document.querySelector('img');
            return el;
        }
        
        function getScale(el) {
            if (!el) return {w: 1280, h: 800};
            var w = el.naturalWidth || el.width || 1280;
            var h = el.naturalHeight || el.height || 800;
            return {w: w, h: h};
        }
        
        function handleClick(e) {
            e.preventDefault();
            var el = findImg();
            if (!el) return;
            var rect = el.getBoundingClientRect();
            var scale = getScale(el);
            var x = Math.round((e.clientX - rect.left) / rect.width * scale.w);
            var y = Math.round((e.clientY - rect.top) / rect.height * scale.h);
            x = Math.max(0, Math.min(x, 1280));
            y = Math.max(0, Math.min(y, 800));
            try { window._ag_click(x + ',' + y); } catch(e) {}
            return false;
        }
        
        function handleRightClick(e) {
            e.preventDefault();
            var el = findImg();
            if (!el) return;
            var rect = el.getBoundingClientRect();
            var scale = getScale(el);
            var x = Math.round((e.clientX - rect.left) / rect.width * scale.w);
            var y = Math.round((e.clientY - rect.top) / rect.height * scale.h);
            x = Math.max(0, Math.min(x, 1280));
            y = Math.max(0, Math.min(y, 800));
            try { window._ag_rclick(x + ',' + y); } catch(e) {}
            return false;
        }
        
        function handleTouch(e) {
            if (e.changedTouches.length === 0) return;
            var t = e.changedTouches[0];
            var el = findImg();
            if (!el) return;
            var rect = el.getBoundingClientRect();
            var scale = getScale(el);
            var x = Math.round((t.clientX - rect.left) / rect.width * scale.w);
            var y = Math.round((t.clientY - rect.top) / rect.height * scale.h);
            x = Math.max(0, Math.min(x, 1280));
            y = Math.max(0, Math.min(y, 800));
            try { window._ag_click(x + ',' + y); } catch(e) {}
        }
        
        function handleLongPress(e) {
            e.preventDefault();
            var el = findImg();
            if (!el) return;
            var rect = el.getBoundingClientRect();
            var scale = getScale(el);
            var x = Math.round((e.clientX - rect.left) / rect.width * scale.w);
            var y = Math.round((e.clientY - rect.top) / rect.height * scale.h);
            x = Math.max(0, Math.min(x, 1280));
            y = Math.max(0, Math.min(y, 800));
            try { window._ag_rclick(x + ',' + y); } catch(e) {}
            return false;
        }
        
        function init() {
            img = findImg();
            if (!img) { setTimeout(init, 500); return; }
            img.style.cursor = 'crosshair';
            img.style.border = '3px solid #00ff88';
            img.style.boxShadow = '0 0 20px rgba(0,255,136,0.3)';
            
            img.addEventListener('click', handleClick);
            img.addEventListener('contextmenu', handleRightClick);
            img.addEventListener('touchend', handleTouch);
            img.addEventListener('touchstart', function(e) {
                this._touchTimer = setTimeout(function() {
                    handleLongPress({clientX: e.touches[0].clientX, clientY: e.touches[0].clientY, preventDefault: function(){}});
                }, 500);
            });
            img.addEventListener('touchend', function() {
                if (this._touchTimer) clearTimeout(this._touchTimer);
            });
            img.addEventListener('touchmove', function() {
                if (this._touchTimer) clearTimeout(this._touchTimer);
            });
            
            console.log('[BrowserCtrl] JavaScript injected successfully');
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', init);
        } else {
            init();
        }
    })();
    </script>
    """
    display(HTML(js))

# ═══════════════════════════════════════════════════════════════════════════════
# LAUNCH BROWSER
# ═══════════════════════════════════════════════════════════════════════════════
def launch_browser():
    global vdisplay, chrome_proc
    
    log_action("Starting Xvfb...")
    vdisplay = xvfbwrapper.Xvfb(width=SCREEN_W, height=SCREEN_H, colordepth=24, display=99)
    vdisplay.start()
    time.sleep(1)
    
    log_action("Launching Chrome...")
    chrome_cmd = [
        "google-chrome",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--window-size=1280,800",
        "--start-fullscreen",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--disable-translate",
        "--no-first-run",
        "--hide-scrollbars",
        "--mute-audio",
        "--no-default-browser-check",
        "--disable-logging",
        "--log-level=3",
        "--user-data-dir=/tmp/chrome-data",
        "--download-default-dir=/tmp/chrome-downloads",
        "--kiosk",
        "https://www.google.com"
    ]
    
    try:
        chrome_proc = subprocess.Popen(
            ["env", "DISPLAY=:99"] + chrome_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)
        log_action("Chrome started (PID: " + str(chrome_proc.pid) + ")")
    except Exception as e:
        log_action("Chrome launch via Popen failed: " + str(e))
        run_bg(" ".join(chrome_cmd))
        time.sleep(3)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  KAGGLE BROWSER CONTROLLER v2.0")
    print("=" * 70)
    
    launch_browser()
    start_heartbeat()
    
    w = create_widgets()
    attach_handlers(w, w["img"], w["status"])
    
    # Layout
    row1 = widgets.HBox([
        widgets.HTML("<b style='color:#00ff88'>🌐 NAV</b>"), w["btn_go"], w["btn_back"],
        w["btn_fwd"], w["btn_reload"], w["btn_home"]
    ], layout=widgets.Layout(gap="4px", padding="4px"))
    
    row2 = widgets.HBox([
        widgets.HTML("<b style='color:#00ff88'>⌨️ KEY</b>"), w["btn_enter"], w["btn_esc"],
        w["btn_tab"], w["btn_up"], w["btn_down"], w["btn_pgup"], w["btn_pgdn"]
    ], layout=widgets.Layout(gap="4px", padding="4px"))
    
    row3 = widgets.HBox([
        widgets.HTML("<b style='color:#00ff88'>🛠️</b>"), w["btn_copy"], w["btn_paste"],
        w["btn_sela"], w["btn_rclick"], w["btn_scrl_up"], w["btn_scrl_dn"],
        w["btn_zoom_in"], w["btn_zoom_out"],
        widgets.HTML("<b style='color:#ffcc00'>📸</b>"), w["btn_fast"], w["btn_slow"]
    ], layout=widgets.Layout(gap="4px", padding="4px"))
    
    url_row = widgets.HBox([
        w["url"], w["btn_go"]
    ], layout=widgets.Layout(gap="4px", padding="4px"))
    
    type_row = widgets.HBox([
        w["type"], w["btn_type_go"]
    ], layout=widgets.Layout(gap="4px", padding="4px"))
    
    chat_row = widgets.HBox([
        w["chat"], w["btn_chat_send"]
    ], layout=widgets.Layout(gap="4px", padding="4px"))
    
    # Output for JavaScript
    js_out = widgets.Output()
    with js_out:
        inject_javascript(w["img"])
    
    # Display everything
    display(widgets.VBox([
        widgets.HTML("""
        <div style='background: linear-gradient(135deg, #1a1a2e, #16213e); 
                    padding: 15px; border-radius: 10px; margin-bottom: 10px;
                    border: 2px solid #00ff88; text-align: center;'>
            <h2 style='color: #00ff88; margin: 0;'>🖥️ KAGGLE BROWSER CONTROLLER v2.0</h2>
            <p style='color: #888; margin: 5px 0 0 0; font-size: 12px;'>
                Click image to click in browser | Right-click for context menu | Touch supported
            </p>
        </div>
        """),
        url_row,
        type_row,
        chat_row,
        w["status"],
        w["img"],
        row1, row2, row3,
        js_out
    ], layout=widgets.Layout(padding="10px")))
    
    # Start screenshot
    start_screenshot(w["img"], w["status"])
    
    print("=" * 70)
    print("  READY! Click the image to interact with Chrome.")
    print("  Use buttons or type text above.")
    print("=" * 70)

if __name__ == "__main__":
    main()
