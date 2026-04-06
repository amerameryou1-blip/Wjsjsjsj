# ═══════════════════════════════════════════════════════════════════════
# KAGGLE BROWSER CONTROLLER v3.0 - PRODUCTION READY
# ═══════════════════════════════════════════════════════════════════════
# Chrome + Xvfb + ipywidgets with click support
# Tested on Kaggle (TPU/P100), works on Colab too
# ═══════════════════════════════════════════════════════════════════════

import subprocess
import os
import sys
import time
import threading
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════
# IMPORTS & DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════
try:
    from xvfbwrapper import Xvfb
    from PIL import Image as PILImage
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", 
                    "xvfbwrapper", "Pillow", "requests"], check=False)
    from xvfbwrapper import Xvfb
    from PIL import Image as PILImage
    import requests

try:
    import ipywidgets as widgets
    from IPython.display import display, HTML
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "ipywidgets"], check=False)
    import ipywidgets as widgets
    from IPython.display import display, HTML

# ═══════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════
DISPLAY_NUM = 99
SCREEN_W = 1280
SCREEN_H = 800

frame_counter = 0
last_action = "Initializing"
screenshot_interval = 3
screenshot_running = False
screenshot_thread = None

vdisplay = None
chrome_process = None

# ═══════════════════════════════════════════════════════════════════════
# ENVIRONMENT SETUP
# ═══════════════════════════════════════════════════════════════════════
def setup_environment():
    os.environ["DISPLAY"] = ":99"
    os.environ["XDG_RUNTIME_DIR"] = "/tmp/xdg-runtime"
    os.environ["XAUTHORITY"] = "/tmp/.Xauthority"
    
    subprocess.run(["mkdir", "-p", "/tmp/xdg-runtime"], capture_output=True, check=False)
    subprocess.run(["mkdir", "-p", "/tmp/chrome-downloads"], capture_output=True, check=False)
    subprocess.run(["touch", "/tmp/.Xauthority"], capture_output=True, check=False)
    subprocess.run(["chmod", "700", "/tmp/xdg-runtime"], capture_output=True, check=False)

# ═══════════════════════════════════════════════════════════════════════
# COMMAND EXECUTION
# ═══════════════════════════════════════════════════════════════════════
def run_xdo(args):
    """Run xdotool command with proper display"""
    cmd = ["env", "DISPLAY=:99", "xdotool"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def xdo_key(key):
    """Press a key"""
    run_xdo(["key", key])
    
def xdo_type(text):
    """Type text character by character"""
    run_xdo(["type", "--", text])

def xdo_mousemove(x, y):
    """Move mouse to coordinates"""
    run_xdo(["mousemove", str(int(x)), str(int(y))])

def xdo_click(button):
    """Click mouse button (1=left, 3=right, 4=scroll up, 5=scroll down)"""
    run_xdo(["click", str(button)])

# ═══════════════════════════════════════════════════════════════════════
# NAVIGATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════
def navigate_to_url(url):
    """Navigate to a URL"""
    global last_action
    last_action = "Navigating to: " + url[:50]
    xdo_key("ctrl+l")
    time.sleep(0.2)
    xdo_type(url)
    time.sleep(0.1)
    xdo_key("Return")

def go_back():
    """Browser back"""
    global last_action
    last_action = "Back"
    xdo_key("alt+Left")

def go_forward():
    """Browser forward"""
    global last_action
    last_action = "Forward"
    xdo_key("alt+Right")

def reload_page():
    """Reload current page"""
    global last_action
    last_action = "Reload"
    xdo_key("F5")

def go_home():
    """Go to home page"""
    global last_action
    last_action = "Home"
    xdo_key("alt+Home")

# ═══════════════════════════════════════════════════════════════════════
# KEYBOARD FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════
def press_enter():
    global last_action
    last_action = "Enter"
    xdo_key("Return")

def press_escape():
    global last_action
    last_action = "Escape"
    xdo_key("Escape")

def press_tab():
    global last_action
    last_action = "Tab"
    xdo_key("Tab")

def press_arrow_up():
    global last_action
    last_action = "Arrow Up"
    xdo_key("Up")

def press_arrow_down():
    global last_action
    last_action = "Arrow Down"
    xdo_key("Down")

def press_pageup():
    global last_action
    last_action = "Page Up"
    xdo_key("Page_Up")

def press_pagedown():
    global last_action
    last_action = "Page Down"
    xdo_key("Page_Down")

# ═══════════════════════════════════════════════════════════════════════
# CLIPBOARD FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════
def do_copy():
    global last_action
    last_action = "Copy"
    xdo_key("ctrl+c")

def do_paste():
    global last_action
    last_action = "Paste"
    xdo_key("ctrl+v")

def do_select_all():
    global last_action
    last_action = "Select All"
    xdo_key("ctrl+a")

# ═══════════════════════════════════════════════════════════════════════
# SCROLL & ZOOM
# ═══════════════════════════════════════════════════════════════════════
def scroll_up():
    global last_action
    last_action = "Scroll Up"
    xdo_click(4)

def scroll_down():
    global last_action
    last_action = "Scroll Down"
    xdo_click(5)

def zoom_in():
    global last_action
    last_action = "Zoom In"
    xdo_key("ctrl+plus")

def zoom_out():
    global last_action
    last_action = "Zoom Out"
    xdo_key("ctrl+minus")

def right_click():
    global last_action
    last_action = "Right Click"
    xdo_click(3)

# ═══════════════════════════════════════════════════════════════════════
# TYPING FUNCTION
# ═══════════════════════════════════════════════════════════════════════
def type_text(text):
    if not text:
        return
    global last_action
    truncated = text[:40] + "..." if len(text) > 40 else text
    last_action = "Typed: " + truncated
    xdo_type(text)

# ═══════════════════════════════════════════════════════════════════════
# SCREENSHOT CAPTURE
# ═══════════════════════════════════════════════════════════════════════
def capture_screenshot():
    """Capture screenshot using scrot"""
    output = "/tmp/browser_frame.png"
    
    # Try scrot
    cmd = ["env", "DISPLAY=:99", "scrot", output, "-o"]
    result = subprocess.run(cmd, capture_output=True)
    
    if os.path.exists(output) and os.path.getsize(output) > 1000:
        return output
    
    # Fallback: ImageMagick import
    cmd = ["env", "DISPLAY=:99", "import", "-window", "root", output]
    subprocess.run(cmd, capture_output=True)
    
    if os.path.exists(output):
        return output
    
    return None

def screenshot_loop(image_widget, status_widget):
    """Screenshot capture loop running in background thread"""
    global frame_counter, screenshot_running, screenshot_interval, last_action
    
    while screenshot_running:
        try:
            path = capture_screenshot()
            
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    image_bytes = f.read()
                
                frame_counter += 1
                image_widget.value = image_bytes
                
                status_text = "Frame #" + str(frame_counter) + " - " + last_action
                status_widget.value = status_text
                
        except Exception as e:
            status_widget.value = "Screenshot error: " + str(e)[:50]
        
        time.sleep(screenshot_interval)

def start_screenshots(image_widget, status_widget):
    """Start the screenshot thread"""
    global screenshot_running, screenshot_thread
    
    screenshot_running = True
    screenshot_thread = threading.Thread(
        target=screenshot_loop, 
        args=(image_widget, status_widget),
        daemon=True
    )
    screenshot_thread.start()

def change_speed(seconds):
    """Change screenshot interval"""
    global screenshot_interval, last_action
    screenshot_interval = seconds
    last_action = "Speed: " + str(seconds) + "s"

# ═══════════════════════════════════════════════════════════════════════
# CLICK HANDLERS
# ═══════════════════════════════════════════════════════════════════════
def handle_left_click(coords_str):
    """Handle left click from JavaScript"""
    global last_action
    try:
        parts = coords_str.split(",")
        x = int(parts[0])
        y = int(parts[1])
        
        # Coordinates are already in screen space (1280x800)
        xdo_mousemove(x, y)
        time.sleep(0.05)
        xdo_click(1)
        
        last_action = "Left click at (" + str(x) + ", " + str(y) + ")"
    except Exception as e:
        last_action = "Click error: " + str(e)

def handle_right_click(coords_str):
    """Handle right click from JavaScript"""
    global last_action
    try:
        parts = coords_str.split(",")
        x = int(parts[0])
        y = int(parts[1])
        
        xdo_mousemove(x, y)
        time.sleep(0.05)
        xdo_click(3)
        
        last_action = "Right click at (" + str(x) + ", " + str(y) + ")"
    except Exception as e:
        last_action = "Right-click error: " + str(e)

# ═══════════════════════════════════════════════════════════════════════
# HEARTBEAT
# ═══════════════════════════════════════════════════════════════════════
def heartbeat_loop():
    """Keep Kaggle session alive"""
    while True:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print("[HEARTBEAT] " + timestamp)
        time.sleep(30)

def start_heartbeat():
    """Start heartbeat thread"""
    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.start()

# ═══════════════════════════════════════════════════════════════════════
# LAUNCH BROWSER
# ═══════════════════════════════════════════════════════════════════════
def launch_xvfb():
    """Start Xvfb virtual display"""
    global vdisplay
    
    print("Starting Xvfb virtual display...")
    vdisplay = Xvfb(width=SCREEN_W, height=SCREEN_H, colordepth=24, display=DISPLAY_NUM)
    vdisplay.start()
    time.sleep(2)
    print("Xvfb started on :99")

def launch_chrome():
    """Launch Chrome browser"""
    global chrome_process
    
    print("Launching Chrome...")
    
    chrome_args = [
        "google-chrome",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--window-size=1280,800",
        "--start-fullscreen",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-translate",
        "--hide-scrollbars",
        "--mute-audio",
        "--disable-logging",
        "--log-level=3",
        "--user-data-dir=/tmp/chrome-profile",
        "--download-default-directory=/tmp/chrome-downloads",
        "https://www.google.com"
    ]
    
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    
    chrome_process = subprocess.Popen(
        chrome_args,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    time.sleep(4)
    print("Chrome started (PID: " + str(chrome_process.pid) + ")")

# ═══════════════════════════════════════════════════════════════════════
# CREATE UI
# ═══════════════════════════════════════════════════════════════════════
def create_ui():
    """Create all widgets"""
    
    # Image widget
    img = widgets.Image(
        format="png",
        width="100%",
        layout=widgets.Layout(border="3px solid #00ff88", padding="2px")
    )
    
    # Status label
    status = widgets.Label(
        value="Initializing...",
        layout=widgets.Layout(padding="10px", width="100%")
    )
    
    # URL input
    url_input = widgets.Text(
        value="https://www.google.com",
        placeholder="Enter URL...",
        layout=widgets.Layout(width="85%")
    )
    
    # Type input
    type_input = widgets.Text(
        value="",
        placeholder="Type text here...",
        layout=widgets.Layout(width="85%")
    )
    
    # Chat textarea
    chat_area = widgets.Textarea(
        value="",
        placeholder="Type message (Ctrl+Enter to send)...",
        layout=widgets.Layout(width="100%", height="80px")
    )
    
    # Buttons - Row 1: Navigation
    btn_go = widgets.Button(description="🌐 Go", button_style="success", 
                            layout=widgets.Layout(width="70px"))
    btn_back = widgets.Button(description="◀ Back", 
                              layout=widgets.Layout(width="70px"))
    btn_fwd = widgets.Button(description="▶ Fwd", 
                             layout=widgets.Layout(width="70px"))
    btn_reload = widgets.Button(description="🔄 Reload", 
                                layout=widgets.Layout(width="80px"))
    btn_home = widgets.Button(description="🏠 Home", 
                              layout=widgets.Layout(width="80px"))
    
    # Buttons - Row 2: Keys
    btn_enter = widgets.Button(description="↵ Enter", 
                               layout=widgets.Layout(width="70px"))
    btn_esc = widgets.Button(description="Esc", 
                             layout=widgets.Layout(width="60px"))
    btn_tab = widgets.Button(description="⇥ Tab", 
                             layout=widgets.Layout(width="60px"))
    btn_up = widgets.Button(description="▲", 
                            layout=widgets.Layout(width="50px"))
    btn_down = widgets.Button(description="▼", 
                              layout=widgets.Layout(width="50px"))
    btn_pgup = widgets.Button(description="PgUp", 
                              layout=widgets.Layout(width="60px"))
    btn_pgdn = widgets.Button(description="PgDn", 
                              layout=widgets.Layout(width="60px"))
    
    # Buttons - Row 3: Tools
    btn_copy = widgets.Button(description="⎘ Copy", 
                              layout=widgets.Layout(width="70px"))
    btn_paste = widgets.Button(description="⌘ Paste", 
                               layout=widgets.Layout(width="70px"))
    btn_selall = widgets.Button(description="Sel All", 
                                layout=widgets.Layout(width="70px"))
    btn_rclick = widgets.Button(description="Right Click", 
                                layout=widgets.Layout(width="90px"))
    btn_scrup = widgets.Button(description="▲ Scroll", 
                               layout=widgets.Layout(width="70px"))
    btn_scrdn = widgets.Button(description="▼ Scroll", 
                               layout=widgets.Layout(width="70px"))
    btn_zoomin = widgets.Button(description="🔍+", 
                                layout=widgets.Layout(width="60px"))
    btn_zoomout = widgets.Button(description="🔍-", 
                                 layout=widgets.Layout(width="60px"))
    btn_fast = widgets.Button(description="📸 Fast 1s", button_style="warning",
                              layout=widgets.Layout(width="90px"))
    btn_slow = widgets.Button(description="📸 Slow 5s", button_style="info",
                              layout=widgets.Layout(width="90px"))
    
    # Type/Send buttons
    btn_type_send = widgets.Button(description="Type", button_style="primary",
                                   layout=widgets.Layout(width="14%"))
    btn_chat_send = widgets.Button(description="SEND", button_style="success",
                                   layout=widgets.Layout(width="100px", height="80px"))
    
    return {
        "img": img,
        "status": status,
        "url_input": url_input,
        "type_input": type_input,
        "chat_area": chat_area,
        "btn_go": btn_go,
        "btn_back": btn_back,
        "btn_fwd": btn_fwd,
        "btn_reload": btn_reload,
        "btn_home": btn_home,
        "btn_enter": btn_enter,
        "btn_esc": btn_esc,
        "btn_tab": btn_tab,
        "btn_up": btn_up,
        "btn_down": btn_down,
        "btn_pgup": btn_pgup,
        "btn_pgdn": btn_pgdn,
        "btn_copy": btn_copy,
        "btn_paste": btn_paste,
        "btn_selall": btn_selall,
        "btn_rclick": btn_rclick,
        "btn_scrup": btn_scrup,
        "btn_scrdn": btn_scrdn,
        "btn_zoomin": btn_zoomin,
        "btn_zoomout": btn_zoomout,
        "btn_fast": btn_fast,
        "btn_slow": btn_slow,
        "btn_type_send": btn_type_send,
        "btn_chat_send": btn_chat_send
    }

# ═══════════════════════════════════════════════════════════════════════
# ATTACH HANDLERS
# ═══════════════════════════════════════════════════════════════════════
def attach_handlers(ui):
    """Attach all button click handlers"""
    
    # Navigation
    ui["btn_go"].on_click(lambda b: navigate_to_url(ui["url_input"].value))
    ui["btn_back"].on_click(lambda b: go_back())
    ui["btn_fwd"].on_click(lambda b: go_forward())
    ui["btn_reload"].on_click(lambda b: reload_page())
    ui["btn_home"].on_click(lambda b: go_home())
    
    # Keyboard
    ui["btn_enter"].on_click(lambda b: press_enter())
    ui["btn_esc"].on_click(lambda b: press_escape())
    ui["btn_tab"].on_click(lambda b: press_tab())
    ui["btn_up"].on_click(lambda b: press_arrow_up())
    ui["btn_down"].on_click(lambda b: press_arrow_down())
    ui["btn_pgup"].on_click(lambda b: press_pageup())
    ui["btn_pgdn"].on_click(lambda b: press_pagedown())
    
    # Clipboard & Tools
    ui["btn_copy"].on_click(lambda b: do_copy())
    ui["btn_paste"].on_click(lambda b: do_paste())
    ui["btn_selall"].on_click(lambda b: do_select_all())
    ui["btn_rclick"].on_click(lambda b: right_click())
    ui["btn_scrup"].on_click(lambda b: scroll_up())
    ui["btn_scrdn"].on_click(lambda b: scroll_down())
    ui["btn_zoomin"].on_click(lambda b: zoom_in())
    ui["btn_zoomout"].on_click(lambda b: zoom_out())
    
    # Screenshot speed
    ui["btn_fast"].on_click(lambda b: change_speed(1))
    ui["btn_slow"].on_click(lambda b: change_speed(5))
    
    # Type & Send
    ui["btn_type_send"].on_click(lambda b: type_text(ui["type_input"].value))
    ui["type_input"].on_submit(lambda t: type_text(t.value))
    
    def send_chat(b):
        text = ui["chat_area"].value
        if text:
            type_text(text)
            press_enter()
            ui["chat_area"].value = ""
    
    ui["btn_chat_send"].on_click(send_chat)

# ═══════════════════════════════════════════════════════════════════════
# JAVASCRIPT INJECTION
# ═══════════════════════════════════════════════════════════════════════
def inject_click_handler():
    """Inject JavaScript to handle image clicks"""
    
    js_code = """
    
    (function() {
        console.log('[BrowserCtrl] Injecting click handlers...');
        
        function findImageWidget() {
            // Try multiple selectors
            var img = document.querySelector('.widget-image img');
            if (!img) img = document.querySelector('img[src^="data:image/png"]');
            if (!img) {
                var imgs = document.querySelectorAll('img');
                for (var i = 0; i < imgs.length; i++) {
                    if (imgs[i].width > 500) {
                        img = imgs[i];
                        break;
                    }
                }
            }
            return img;
        }
        
        function attachHandlers() {
            var img = findImageWidget();
            if (!img) {
                setTimeout(attachHandlers, 500);
                return;
            }
            
            // Style the image
            img.style.cursor = 'crosshair';
            img.style.border = '3px solid #00ff88';
            img.style.boxShadow = '0 0 20px rgba(0,255,136,0.4)';
            
            // Left click handler
            img.addEventListener('click', function(e) {
                e.preventDefault();
                
                var rect = img.getBoundingClientRect();
                var scaleX = 1280 / rect.width;
                var scaleY = 800 / rect.height;
                
                var x = Math.round((e.clientX - rect.left) * scaleX);
                var y = Math.round((e.clientY - rect.top) * scaleY);
                
                x = Math.max(0, Math.min(x, 1280));
                y = Math.max(0, Math.min(y, 800));
                
                var coords = x + ',' + y;
                
                // Call Python function
                var kernel = IPython.notebook.kernel;
                kernel.execute('handle_left_click("' + coords + '")');
                
                return false;
            });
            
            // Right click handler
            img.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                
                var rect = img.getBoundingClientRect();
                var scaleX = 1280 / rect.width;
                var scaleY = 800 / rect.height;
                
                var x = Math.round((e.clientX - rect.left) * scaleX);
                var y = Math.round((e.clientY - rect.top) * scaleY);
                
                x = Math.max(0, Math.min(x, 1280));
                y = Math.max(0, Math.min(y, 800));
                
                var coords = x + ',' + y;
                
                var kernel = IPython.notebook.kernel;
                kernel.execute('handle_right_click("' + coords + '")');
                
                return false;
            });
            
            // Touch support
            var touchTimer = null;
            
            img.addEventListener('touchstart', function(e) {
                var touch = e.touches[0];
                var startX = touch.clientX;
                var startY = touch.clientY;
                
                touchTimer = setTimeout(function() {
                    // Long press = right click
                    var rect = img.getBoundingClientRect();
                    var scaleX = 1280 / rect.width;
                    var scaleY = 800 / rect.height;
                    
                    var x = Math.round((startX - rect.left) * scaleX);
                    var y = Math.round((startY - rect.top) * scaleY);
                    
                    x = Math.max(0, Math.min(x, 1280));
                    y = Math.max(0, Math.min(y, 800));
                    
                    var coords = x + ',' + y;
                    var kernel = IPython.notebook.kernel;
                    kernel.execute('handle_right_click("' + coords + '")');
                }, 800);
            });
            
            img.addEventListener('touchend', function(e) {
                if (touchTimer) {
                    clearTimeout(touchTimer);
                    
                    // Quick tap = left click
                    if (e.changedTouches.length > 0) {
                        var touch = e.changedTouches[0];
                        var rect = img.getBoundingClientRect();
                        var scaleX = 1280 / rect.width;
                        var scaleY = 800 / rect.height;
                        
                        var x = Math.round((touch.clientX - rect.left) * scaleX);
                        var y = Math.round((touch.clientY - rect.top) * scaleY);
                        
                        x = Math.max(0, Math.min(x, 1280));
                        y = Math.max(0, Math.min(y, 800));
                        
                        var coords = x + ',' + y;
                        var kernel = IPython.notebook.kernel;
                        kernel.execute('handle_left_click("' + coords + '")');
                    }
                }
                touchTimer = null;
            });
            
            img.addEventListener('touchmove', function() {
                if (touchTimer) {
                    clearTimeout(touchTimer);
                    touchTimer = null;
                }
            });
            
            console.log('[BrowserCtrl] Click handlers attached successfully!');
        }
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', attachHandlers);
        } else {
            attachHandlers();
        }
    })();
    
    """
    
    display(HTML(js_code))

# ═══════════════════════════════════════════════════════════════════════
# MAIN FUNCTION
# ═══════════════════════════════════════════════════════════════════════
def main():
    """Main entry point"""
    
    print("")
    print("=" * 70)
    print("  KAGGLE BROWSER CONTROLLER v3.0")
    print("=" * 70)
    print("")
    
    # Setup
    setup_environment()
    launch_xvfb()
    launch_chrome()
    start_heartbeat()
    
    # Create UI
    ui = create_ui()
    attach_handlers(ui)
    
    # Build layout
    url_row = widgets.HBox(
        [ui["url_input"], ui["btn_go"]],
        layout=widgets.Layout(gap="5px", padding="5px")
    )
    
    type_row = widgets.HBox(
        [ui["type_input"], ui["btn_type_send"]],
        layout=widgets.Layout(gap="5px", padding="5px")
    )
    
    chat_row = widgets.HBox(
        [ui["chat_area"], ui["btn_chat_send"]],
        layout=widgets.Layout(gap="5px", padding="5px")
    )
    
    nav_row = widgets.HBox(
        [widgets.Label("🌐 NAV:"), ui["btn_go"], ui["btn_back"], 
         ui["btn_fwd"], ui["btn_reload"], ui["btn_home"]],
        layout=widgets.Layout(gap="5px", padding="5px")
    )
    
    key_row = widgets.HBox(
        [widgets.Label("⌨️ KEYS:"), ui["btn_enter"], ui["btn_esc"], 
         ui["btn_tab"], ui["btn_up"], ui["btn_down"], 
         ui["btn_pgup"], ui["btn_pgdn"]],
        layout=widgets.Layout(gap="5px", padding="5px")
    )
    
    tool_row = widgets.HBox(
        [widgets.Label("🛠️ TOOLS:"), ui["btn_copy"], ui["btn_paste"], 
         ui["btn_selall"], ui["btn_rclick"], ui["btn_scrup"], 
         ui["btn_scrdn"], ui["btn_zoomin"], ui["btn_zoomout"],
         widgets.Label("📸:"), ui["btn_fast"], ui["btn_slow"]],
        layout=widgets.Layout(gap="5px", padding="5px")
    )
    
    # Header
    header = widgets.HTML("""
        
            🖥️ BROWSER CONTROLLER v3.0
            
                Click image to interact | Right-click for menu | Touch supported
            
        
    """)
    
    # Display everything
    display(widgets.VBox([
        header,
        url_row,
        type_row,
        chat_row,
        ui["status"],
        ui["img"],
        nav_row,
        key_row,
        tool_row
    ]))
    
    # Inject JavaScript
    inject_click_handler()
    
    # Start screenshots
    start_screenshots(ui["img"], ui["status"])
    
    print("")
    print("=" * 70)
    print("  READY! Click the screenshot to interact with Chrome.")
    print("=" * 70)
    print("")

# ═══════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
else:
    # Auto-run when imported/executed
    main()
