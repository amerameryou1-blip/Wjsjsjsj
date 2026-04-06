# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║          KAGGLE BROWSER CONTROLLER - Touch & Chat Enabled                   ║
# ║  Chrome + Xvfb + xdotool | TPU/P100 Optimized | 30GB RAM Ready              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
# IMPORTANT: Enable Internet in Notebook Options → Settings → Internet (ON)
# Make sure your phone number is verified on Kaggle for internet access
#
# FIRST TIME SETUP - Run this once to install dependencies:
# !pip install xvfbwrapper Pillow requests
# !apt-get update && apt-get install -y xdotool scrot chromium-browser 2>/dev/null || true
#

import subprocess
import threading
import time
import os
import sys
import re
import base64
import json
from pathlib import Path

try:
    import xvfbwrapper
    from PIL import Image
    from io import BytesIO
except ImportError:
    print("⚠️ Installing required packages...")
    subprocess.run([sys.executable, "-m", "pip", "install", "xvfbwrapper", "Pillow", "-q"])
    import xvfbwrapper
    from PIL import Image
    from io import BytesIO

try:
    import ipywidgets as widgets
    from IPython.display import display, HTML, JavaScript, clear_output
except ImportError:
    print("⚠️ Ipywidgets not available, using basic output")
    widgets = None

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DISPLAY_NUM = ":99"
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
SCREEN_DEPTH = 24
CHROME_DEBUG_PORT = 9222
SCREENSHOT_PATH = "/tmp/frame.png"
DOWNLOAD_PATH = "/tmp/chrome-downloads"

# XDG Runtime dir fix for Chrome/Qt on Kaggle
os.makedirs("/tmp/xdg-runtime", mode=0o700, exist_ok=True)
os.environ["XDG_RUNTIME_DIR"] = "/tmp/xdg-runtime"
os.environ["DISPLAY"] = DISPLAY_NUM
os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"

# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════════════

state = {
    "frame_count": 0,
    "screenshot_interval": 3,
    "screenshot_thread": None,
    "stop_screenshot": threading.Event(),
    "heartbeat_thread": None,
    "stop_heartbeat": threading.Event(),
    "chrome_process": None,
    "xvfb_process": None,
    "command_history": [],
    "image_widget": None,
    "status_widget": None,
    "url_widget": None,
    "chat_widget": None,
    "log_widget": None,
    "is_mobile": False,
}

# ═══════════════════════════════════════════════════════════════════════════════
# SHELL COMMAND HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def run_cmd(cmd, timeout=10, check=True):
    """Run shell command with DISPLAY env set, return stdout"""
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY_NUM
    env["XDG_RUNTIME_DIR"] = "/tmp/xdg-runtime"
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, 
            text=True, timeout=timeout, env=env
        )
        if check and result.returncode != 0:
            print(f"⚠️ Command failed: {cmd[:60]}...")
            print(f"   Error: {result.stderr[:200]}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"⏱️ Command timeout: {cmd[:60]}")
        return ""
    except Exception as e:
        print(f"❌ Command error: {e}")
        return ""

# ═══════════════════════════════════════════════════════════════════════════════
# CHROME & Xvfb MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def check_chrome():
    """Find available Chrome/Chromium binary"""
    for path in ["/usr/bin/chromium-browser", "/usr/bin/chromium", 
             "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]:
        if os.path.exists(path):
            return path
    return "chromium-browser"

def start_xvfb():
    """Start Xvfb virtual display"""
    print(f"🔧 Starting Xvfb on {DISPLAY_NUM}...")
    
    # Kill any existing Xvfb on this display
    run_cmd(f"pkill -f 'Xvfb {DISPLAY_NUM}' 2>/dev/null", check=False)
    time.sleep(0.5)
    
    try:
        # Start Xvfb with accel extensions
        proc = subprocess.Popen([
            "Xvfb", DISPLAY_NUM,
            "-screen", "0", f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}x{SCREEN_DEPTH}",
            "-ac", "+extension", "GLX", "+extension", "RANDR", "+render", "-noreset"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state["xvfb_process"] = proc
        time.sleep(1)
        
        # Verify Xvfb is running
        if proc.poll() is None:
            run_cmd(f"xdotool --display {DISPLAY_NUM} getNumLock 2>/dev/null", check=False)
            print("✅ Xvfb started successfully")
            return True
        else:
            print("❌ Xvfb failed to start")
            return False
    except Exception as e:
        print(f"❌ Xvfb error: {e}")
        return False

def start_chrome():
    """Start Chrome browser with remote debugging"""
    print("🌐 Starting Chrome...")
    
    chrome_path = check_chrome()
    print(f"   Using: {chrome_path}")
    
    # Kill existing Chrome
    run_cmd("pkill -f 'chrome' 2>/dev/null", check=False)
    run_cmd("pkill -f 'chromium' 2>/dev/null", check=False)
    time.sleep(0.5)
    
    # Create download directory
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    
    # Chrome flags optimized for Kaggle/cloud
    chrome_args = [
        chrome_path,
        f"--display={DISPLAY_NUM}",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--no-zygote",
        "--safebrowsing-disable-auto-update",
        "--ignore-certificate-errors",
        "--ignore-ssl-errors",
        "--ignore-certificate-errors-spki-list",
        "--user-data-dir=/tmp/chrome-data",
        f"--download-default-directory={DOWNLOAD_PATH}",
        "--download-prompt-behavior=0",
        "--kiosk-printing-enabled=false",
        f"--window-size={SCREEN_WIDTH},{SCREEN_HEIGHT}",
        "--app=https://www.google.com",
    ]
    
    try:
        proc = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        state["chrome_process"] = proc
        time.sleep(3)
        
        if proc.poll() is None:
            print("✅ Chrome started successfully")
            return True
        else:
            print("❌ Chrome exited immediately")
            return False
    except Exception as e:
        print(f"❌ Chrome error: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def capture_screenshot():
    """Capture screenshot using scrot, gnome-screenshot, or ImageMagick"""
    # Try scrot first (fastest)
    result = run_cmd(f"scrot {SCREENSHOT_PATH} -o 2>/dev/null", check=False)
    if os.path.exists(SCREENSHOT_PATH) and os.path.getsize(SCREENSHOT_PATH) > 1000:
        return SCREENSHOT_PATH
    
    # Fallback to gnome-screenshot
    result = run_cmd(f"gnome-screenshot -f {SCREENSHOT_PATH} 2>/dev/null", check=False)
    if os.path.exists(SCREENSHOT_PATH) and os.path.getsize(SCREENSHOT_PATH) > 1000:
        return SCREENSHOT_PATH
    
    # Fallback to ImageMagick import
    result = run_cmd(f"import -window root {SCREENSHOT_PATH} 2>/dev/null", check=False)
    if os.path.exists(SCREENSHOT_PATH) and os.path.getsize(SCREENSHOT_PATH) > 1000:
        return SCREENSHOT_PATH
    
    # Fallback to Chrome DevTools Protocol screenshot
    return None

def screenshot_loop():
    """Background thread for continuous screenshots"""
    print(f"📷 Screenshot loop started (interval: {state['screenshot_interval']}s)")
    
    while not state["stop_screenshot"].is_set():
        try:
            screenshot_path = capture_screenshot()
            
            if screenshot_path and os.path.exists(screenshot_path):
                state["frame_count"] += 1
                
                # Read and encode image for widget
                with open(screenshot_path, "rb") as f:
                    img_data = f.read()
                
                # Update image widget if available
                if state["image_widget"] is not None:
                    state["image_widget"].value = img_data
                
                # Update status
                if state["status_widget"]:
                    action = state["command_history"][-1]["action"] if state["command_history"] else "Live feed"
                    state["status_widget"].value = f"Frame #{state['frame_count']} • {action}"
            else:
                print("⚠️ Screenshot capture failed")
                
        except Exception as e:
            print(f"⚠️ Screenshot error: {e}")
        
        state["stop_screenshot"].wait(state["screenshot_interval"])
    
    print("📷 Screenshot loop stopped")

def start_screenshot_thread(interval=3):
    """Start or restart screenshot thread"""
    state["screenshot_interval"] = interval
    state["stop_screenshot"].set()
    
    if state["screenshot_thread"]:
        state["screenshot_thread"].join(timeout=2)
    
    state["stop_screenshot"] = threading.Event()
    state["screenshot_thread"] = threading.Thread(target=screenshot_loop, daemon=True)
    state["screenshot_thread"].start()

# ═══════════════════════════════════════════════════════════════════════════════
# MOUSE & KEYBOARD CONTROL
# ═══════════════════════════════════════════════════════════════════════════════

def _ag_click(coords):
    """
    Handle click events from JavaScript.
    Coords is "x,y" string, scale from image to screen resolution.
    """
    try:
        # Parse coordinates from "x,y" string
        parts = coords.replace("(", "").replace(")", "").split(",")
        if len(parts) != 2:
            parts = coords.split("x")
        
        img_x = int(float(parts[0]))
        img_y = int(float(parts[1]))
        
        # Get actual displayed image size from widget (accounting for CSS scaling)
        img_width = SCREEN_WIDTH
        img_height = SCREEN_HEIGHT
        
        # Scale to screen coordinates
        scale_x = SCREEN_WIDTH / img_width
        scale_y = SCREEN_HEIGHT / img_height
        
        screen_x = int(img_x * scale_x)
        screen_y = int(img_y * scale_y)
        
        # Clamp to screen bounds
        screen_x = max(0, min(screen_x, SCREEN_WIDTH - 1))
        screen_y = max(0, min(screen_y, SCREEN_HEIGHT - 1))
        
        # Move mouse and click
        run_cmd(f"xdotool mousemove {screen_x} {screen_y}", check=False)
        time.sleep(0.05)
        run_cmd(f"xdotool click 1", check=False)
        
        log_action(f"🖱️ Click at ({screen_x}, {screen_y})")
        return True
    except Exception as e:
        print(f"❌ Click error: {e}")
        return False

def _ag_rclick(coords):
    """Handle right-click events from JavaScript"""
    try:
        parts = coords.replace("(", "").replace(")", "").split(",")
        if len(parts) != 2:
            parts = coords.split("x")
        
        screen_x = int(float(parts[0]))
        screen_y = int(float(parts[1]))
        
        run_cmd(f"xdotool mousemove {screen_x} {screen_y}", check=False)
        time.sleep(0.05)
        run_cmd(f"xdotool click 3", check=False)
        
        log_action(f"🖱️ Right-click at ({screen_x}, {screen_y})")
        return True
    except Exception as e:
        print(f"❌ Right-click error: {e}")
        return False

def _ag_type(text):
    """Type text using xdotool with special character support"""
    try:
        # Escape special shell characters
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
        run_cmd(f'xdotool type -- "{escaped}"', check=False)
        log_action(f"⌨️ Typed: {text[:50]}{'...' if len(text) > 50 else ''"})
        return True
    except Exception as e:
        print(f"❌ Type error: {e}")
        return False

def _ag_key(key):
    """Send a single key using xdotool"""
    try:
        run_cmd(f"xdotool key {key}", check=False)
        log_action(f"⌨️ Key: {key}")
        return True
    except Exception as e:
        print(f"❌ Key error: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# NAVIGATION ACTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def nav_go(url=None):
    """Navigate to URL: Ctrl+L, type URL, Enter"""
    if not url:
        url = state["url_widget"].value if state["url_widget"] else ""
    
    if not url:
        print("⚠️ No URL entered")
        return
    
    # Ensure URL has protocol
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    print(f"🌐 Navigating to: {url}")
    
    # Ctrl+L to focus address bar
    run_cmd("xdotool key Ctrl+l", check=False)
    time.sleep(0.2)
    
    # Select all and type new URL
    run_cmd("xdotool key Ctrl+a", check=False)
    time.sleep(0.1)
    _ag_type(url)
    time.sleep(0.1)
    
    # Press Enter
    run_cmd("xdotool key Return", check=False)
    
    log_action(f"🌐 Opened: {url}")
    update_status(f"🌐 Opened {url[:40]}...")

def nav_back(b=None):
    run_cmd("xdotool key Alt+Left", check=False)
    log_action("◀ Browser back")
    update_status("◀ Navigated back")

def nav_forward(b=None):
    run_cmd("xdotool key Alt+Right", check=False)
    log_action("▶ Browser forward")
    update_status("▶ Navigated forward")

def nav_reload(b=None):
    run_cmd("xdotool key F5", check=False)
    log_action("🔄 Page reloaded")
    update_status("🔄 Page reloaded")

def nav_home(b=None):
    run_cmd("xdotool key Alt+Home", check=False)
    log_action("🏠 Returned home")
    update_status("🏠 Returned home")

# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD SHORTCUTS
# ═══════════════════════════════════════════════════════════════════════════════

def key_enter(b=None):
    run_cmd("xdotool key Return", check=False)
    log_action("↵ Enter pressed")

def key_escape(b=None):
    run_cmd("xdotool key Escape", check=False)
    log_action("✖️ Escape pressed")

def key_tab(b=None):
    run_cmd("xdotool key Tab", check=False)
    log_action("⇥ Tab pressed")

def key_up(b=None):
    run_cmd("xdotool key Up", check=False)
    log_action("▲ Up arrow")

def key_down(b=None):
    run_cmd("xdotool key Down", check=False)
    log_action("▼ Down arrow")

def key_pgup(b=None):
    run_cmd("xdotool key Page_Up", check=False)
    log_action("↑ Page Up")

def key_pgdn(b=None):
    run_cmd("xdotool key Page_Down", check=False)
    log_action("↓ Page Down")

# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def tool_copy(b=None):
    run_cmd("xdotool key Ctrl+c", check=False)
    log_action("⎘ Copied to clipboard")
    update_status("⎘ Copied")

def tool_paste(b=None):
    run_cmd("xdotool key Ctrl+v", check=False)
    log_action("⌘ Pasted from clipboard")
    update_status("⌘ Pasted")

def tool_selectall(b=None):
    run_cmd("xdotool key Ctrl+a", check=False)
    log_action("✓ Select all")
    update_status("✓ Selected all")

def tool_rightclick(b=None):
    run_cmd("xdotool click 3", check=False)
    log_action("🖱️ Right-click")

def tool_scrollup(b=None):
    run_cmd("xdotool click 4", check=False)
    log_action("📜 Scrolled up")

def tool_scrolldown(b=None):
    run_cmd("xdotool click 5", check=False)
    log_action("📜 Scrolled down")

def tool_zoomin(b=None):
    run_cmd("xdotool key Ctrl+plus", check=False)
    log_action("🔍 Zoomed in")
    update_status("🔍 Zoomed in")

def tool_zoomout(b=None):
    run_cmd("xdotool key Ctrl+minus", check=False)
    log_action("🔍 Zoomed out")
    update_status("🔍 Zoomed out")

def tool_screenshot_fast(b=None):
    start_screenshot_thread(interval=1)
    log_action("📸 Fast screenshot (1s)")
    update_status("📸 Fast mode: 1s")

def tool_screenshot_normal(b=None):
    start_screenshot_thread(interval=3)
    log_action("📸 Normal screenshot (3s)")
    update_status("📸 Normal mode: 3s")

def tool_screenshot_slow(b=None):
    start_screenshot_thread(interval=5)
    log_action("📸 Slow screenshot (5s)")
    update_status("📸 Slow mode: 5s")

# ═══════════════════════════════════════════════════════════════════════════════
# CHAT / TEXT INPUT
# ═══════════════════════════════════════════════════════════════════════════════

def send_chat_message(b=None):
    """Send message from chat input field"""
    if state["chat_widget"]:
        msg = state["chat_widget"].value
        if msg.strip():
            _ag_type(msg)
            time.sleep(0.1)
            run_cmd("xdotool key Return", check=False)
            log_action(f"💬 Sent: {msg[:50]}")
            state["chat_widget"].value = ""

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def log_action(action):
    """Log action to history"""
    timestamp = time.strftime("%H:%M:%S")
    state["command_history"].append({"time": timestamp, "action": action})
    if len(state["command_history"]) > 50:
        state["command_history"] = state["command_history"][-50:]

def update_status(text):
    """Update status label"""
    if state["status_widget"]:
        state["status_widget"].value = f"Frame #{state['frame_count']} • {text}"

def heartbeat_loop():
    """Keep session alive by sending periodic pings"""
    print("❤️ Heartbeat started (30s interval)")
    while not state["stop_heartbeat"].is_set():
        time.sleep(30)
        if not state["stop_heartbeat"].is_set():
            # Simulate slight mouse movement to keep session alive
            run_cmd("xdotool mousemove 100 100 2>/dev/null", check=False)
            print(f"💓 Heartbeat {time.strftime('%H:%M:%S')}")
    print("❤️ Heartbeat stopped")

def start_heartbeat():
    state["stop_heartbeat"] = threading.Event()
    state["heartbeat_thread"] = threading.Thread(target=heartbeat_loop, daemon=True)
    state["heartbeat_thread"].start()

def cleanup():
    """Stop all processes on cleanup"""
    print("🧹 Cleaning up...")
    state["stop_screenshot"].set()
    state["stop_heartbeat"].set()
    
    if state["chrome_process"]:
        state["chrome_process"].terminate()
    if state["xvfb_process"]:
        state["xvfb_process"].terminate()
    
    run_cmd("pkill -f chromium 2>/dev/null", check=False)
    run_cmd("pkill -f chrome 2>/dev/null", check=False)
    run_cmd("pkill -f Xvfb 2>/dev/null", check=False)
    
    print("✅ Cleanup complete")

# ═══════════════════════════════════════════════════════════════════════════════
# WIDGET LAYOUT & JAVASCRIPT INJECTION
# ═══════════════════════════════════════════════════════════════════════════════

def create_widgets():
    """Create all ipywidgets and layout"""
    
    # Screenshot image widget
    placeholder_img = open("/tmp/frame.png", "rb").read() if os.path.exists("/tmp/frame.png") else b""
    img_widget = widgets.Image(
        value=placeholder_img,
        format='png',
        width='100%',
        layout=widgets.Layout("max-width"="1280px", "border"="2px solid #238636", "border-radius"="8px")
    )
    state["image_widget"] = img_widget
    
    # Status label
    status_widget = widgets.Label(
        value="Initializing...",
        layout=widgets.Layout("padding"="8px", "font-size"="14px", "background"="#21262d", "border-radius"="6px")
    )
    state["status_widget"] = status_widget
    
    # URL input
    url_widget = widgets.Text(
        value="https://www.google.com",
        placeholder="Enter URL...",
        layout=widgets.Layout("flex"="1", "padding"="10px", "font-size"="14px"),
        description=""
    )
    state["url_widget"] = url_widget
    
    # Chat/Type input
    chat_widget = widgets.Textarea(
        value="",
        placeholder="Type a message to send to the browser... (Ctrl+Enter to send)",
        layout=widgets.Layout("width"="100%", "height"="80px", "padding"="10px", "font-size"="14px"),
    )
    state["chat_widget"] = chat_widget
    
    # Button styling
    btn_style = {"button_color": "#21262d", "border": "1px solid #30363d", "margin": "2px"}
    
    # Navigation buttons
    btn_go = widgets.Button(description="🌐 Go", button_style="success", layout=widgets.Layout("padding"="8px 16px"))
    btn_back = widgets.Button(description="◀ Back", layout=widgets.Layout("padding"="8px 12px"))
    btn_fwd = widgets.Button(description="▶ Fwd", layout=widgets.Layout("padding"="8px 12px"))
    btn_reload = widgets.Button(description="🔄 Reload", layout=widgets.Layout("padding"="8px 12px"))
    btn_home = widgets.Button(description="🏠 Home", layout=widgets.Layout("padding"="8px 12px"))
    
    # Key buttons
    btn_enter = widgets.Button(description="↵ Enter", layout=widgets.Layout("padding"="8px 12px"))
    btn_esc = widgets.Button(description="Esc", layout=widgets.Layout("padding"="8px 12px"))
    btn_tab = widgets.Button(description="⇥ Tab", layout=widgets.Layout("padding"="8px 12px"))
    btn_up = widgets.Button(description="▲", layout=widgets.Layout("padding"="8px 12px"))
    btn_down = widgets.Button(description="▼", layout=widgets.Layout("padding"="8px 12px"))
    btn_pgup = widgets.Button(description="PgUp", layout=widgets.Layout("padding"="8px 12px"))
    btn_pgdn = widgets.Button(description="PgDn", layout=widgets.Layout("padding"="8px 12px"))
    
    # Tool buttons
    btn_copy = widgets.Button(description="⎘ Copy", layout=widgets.Layout("padding"="8px 12px"))
    btn_paste = widgets.Button(description="⌘ Paste", layout=widgets.Layout("padding"="8px 12px"))
    btn_selall = widgets.Button(description="Sel All", layout=widgets.Layout("padding"="8px 12px"))
    btn_rclick = widgets.Button(description="Right Click", layout=widgets.Layout("padding"="8px 12px"))
    btn_scrollup = widgets.Button(description="▲ Scroll", layout=widgets.Layout("padding"="8px 12px"))
    btn_scrolldown = widgets.Button(description="▼ Scroll", layout=widgets.Layout("padding"="8px 12px"))
    btn_zoomin = widgets.Button(description="🔍+", layout=widgets.Layout("padding"="8px 12px"))
    btn_zoomout = widgets.Button(description="🔍-", layout=widgets.Layout("padding"="8px 12px"))
    btn_fast = widgets.Button(description="📸 Fast 1s", button_style="warning", layout=widgets.Layout("padding"="8px 12px"))
    btn_slow = widgets.Button(description="📸 Slow 5s", button_style="info", layout=widgets.Layout("padding"="8px 12px"))
    
    # Send button
    btn_send = widgets.Button(description="💬 Send", button_style="success", layout=widgets.Layout("padding"="8px 16px"))
    
    # Wire up events
    btn_go.on_click(lambda b: nav_go())
    btn_back.on_click(nav_back)
    btn_fwd.on_click(nav_forward)
    btn_reload.on_click(nav_reload)
    btn_home.on_click(nav_home)
    btn_enter.on_click(key_enter)
    btn_esc.on_click(key_escape)
    btn_tab.on_click(key_tab)
    btn_up.on_click(key_up)
    btn_down.on_click(key_down)
    btn_pgup.on_click(key_pgup)
    btn_pgdn.on_click(key_pgdn)
    btn_copy.on_click(tool_copy)
    btn_paste.on_click(tool_paste)
    btn_selall.on_click(tool_selectall)
    btn_rclick.on_click(tool_rightclick)
    btn_scrollup.on_click(tool_scrollup)
    btn_scrolldown.on_click(tool_scrolldown)
    btn_zoomin.on_click(tool_zoomin)
    btn_zoomout.on_click(tool_zoomout)
    btn_fast.on_click(lambda b: (start_screenshot_thread(1), update_status("📸 Fast: 1s")))
    btn_slow.on_click(lambda b: (start_screenshot_thread(5), update_status("📸 Slow: 5s")))
    btn_send.on_click(send_chat_message)
    
    # Chat textarea Ctrl+Enter handler
    def on_chat_key(change):
        if change['type'] == 'keydown' and change['key'] == 'Enter' and change.get('ctrl'):
            send_chat_message()
    chat_widget.on_notify(on_chat_key)
    
    # Layout
    nav_row = widgets.HBox([btn_go, btn_back, btn_fwd, btn_reload, btn_home], layout=widgets.Layout("margin"="4px 0"))
    key_row = widgets.HBox([btn_enter, btn_esc, btn_tab, btn_up, btn_down, btn_pgup, btn_pgdn], layout=widgets.Layout("margin"="4px 0"))
    tool_row1 = widgets.HBox([btn_copy, btn_paste, btn_selall, btn_rclick, btn_scrollup, btn_scrolldown], layout=widgets.Layout("margin"="4px 0"))
    tool_row2 = widgets.HBox([btn_zoomin, btn_zoomout, btn_fast, btn_slow], layout=widgets.Layout("margin"="4px 0"))
    
    url_row = widgets.HBox([
        widgets.HTML("📱 URL:"),
        url_widget,
    ], layout=widgets.Layout("display"="flex", "align-items"="center"))
    
    chat_row = widgets.HBox([
        widgets.HTML("💬:"),
        chat_widget,
        btn_send
    ], layout=widgets.Layout("display"="flex", "align-items"="flex-start"))
    
    # Main layout
    main_box = widgets.VBox([
        status_widget,
        widgets.HTML("🖱️ Click/Touch the image to interact • Right-click for context menu"),
        img_widget,
        widgets.HTML(""),
        url_row,
        chat_row,
        widgets.HTML(""),
        widgets.HTML("🔧 Navigation"),
        nav_row,
        widgets.HTML("⌨️ Keys"),
        key_row,
        widgets.HTML("🛠️ Tools"),
        tool_row1,
        tool_row2,
    ], layout=widgets.Layout("padding"="15px", "background"="#0d1117", "border-radius"="12px"))
    
    return main_box

def inject_javascript():
    """Inject JavaScript for click/touch handling into the Image widget"""
    js_code = """
    <script>
    // Wait for widgets to be ready
    document.addEventListener('DOMContentLoaded', function() {
        // Find the image element (may be inside widget container)
        setTimeout(function() {
            var img = document.querySelector('.jupyter-widgets-output-area img, '
                                + '.widget-image, '
                                + 'img[src*="frame.png"], '
                                + 'img');
            
            if (img) {
                // Style for crosshair cursor and green border
                img.style.cursor = 'crosshair';
                img.style.border = '2px solid #238636';
                img.style.borderRadius = '8px';
                img.style.boxShadow = '0 4px 20px rgba(35, 134, 54, 0.3)';
                
                // Get actual display dimensions
                var displayWidth = img.naturalWidth || 1280;
                var displayHeight = img.naturalHeight || 800;
                
                console.log('Browser Controller: Image found', displayWidth, 'x', displayHeight);
                
                // MOBILE/TOUCH DETECTION
                var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
                
                // Left click handler
                img.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    var rect = img.getBoundingClientRect();
                    var scaleX = 1280 / rect.width;
                    var scaleY = 800 / rect.height;
                    
                    var imgX = Math.round((e.clientX - rect.left) * scaleX);
                    var imgY = Math.round((e.clientY - rect.top) * scaleY);
                    
                    console.log('Left click at:', imgX, imgY);
                    
                    // Call Python function via IPython kernel
                    if (window._ag_click) {
                        window._ag_click(imgX + ',' + imgY);
                    } else {
                        // Fallback: try IPython kernel
                        try {
                            IPython.notebook.kernel.execute('_ag_click("' + imgX + ',' + imgY + '")');
                        } catch(e) {
                            console.log('Kernel call failed:', e);
                        }
                    }
                    
                    // Visual feedback
                    showClickFeedback(e.clientX - rect.left, e.clientY - rect.top);
                });
                
                // Right click handler (context menu)
                img.addEventListener('contextmenu', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    var rect = img.getBoundingClientRect();
                    var scaleX = 1280 / rect.width;
                    var scaleY = 800 / rect.height;
                    
                    var imgX = Math.round((e.clientX - rect.left) * scaleX);
                    var imgY = Math.round((e.clientY - rect.top) * scaleY);
                    
                    console.log('Right click at:', imgX, imgY);
                    
                    if (window._ag_rclick) {
                        window._ag_rclick(imgX + ',' + imgY);
                    } else {
                        try {
                            IPython.notebook.kernel.execute('_ag_rclick("' + imgX + ',' + imgY + '")');
                        } catch(e) {
                            console.log('Kernel call failed:', e);
                        }
                    }
                });
                
                // TOUCH SUPPORT for mobile/tablet
                img.addEventListener('touchstart', function(e) {
                    e.preventDefault();
                    img.style.outline = '3px solid #58a6ff';
                    img.style.outlineOffset = '2px';
                }, {passive: false});
                
                img.addEventListener('touchend', function(e) {
                    e.preventDefault();
                    img.style.outline = 'none';
                    
                    var touch = e.changedTouches[0];
                    var rect = img.getBoundingClientRect();
                    var scaleX = 1280 / rect.width;
                    var scaleY = 800 / rect.height;
                    
                    var imgX = Math.round((touch.clientX - rect.left) * scaleX);
                    var imgY = Math.round((touch.clientY - rect.top) * scaleY);
                    
                    console.log('Touch at:', imgX, imgY);
                    
                    if (window._ag_click) {
                        window._ag_click(imgX + ',' + imgY);
                    } else {
                        try {
                            IPython.notebook.kernel.execute('_ag_click("' + imgX + ',' + imgY + '")');
                        } catch(e) {
                            console.log('Kernel call failed:', e);
                        }
                    }
                }, {passive: false});
                
                img.addEventListener('touchcancel', function(e) {
                    img.style.outline = 'none';
                });
                
                // Long press for right-click on mobile
                var longPressTimer;
                img.addEventListener('touchstart', function(e) {
                    longPressTimer = setTimeout(function() {
                        var touch = e.touches[0];
                        var rect = img.getBoundingClientRect();
                        var scaleX = 1280 / rect.width;
                        var scaleY = 800 / rect.height;
                        
                        var imgX = Math.round((touch.clientX - rect.left) * scaleX);
                        var imgY = Math.round((touch.clientY - rect.top) * scaleY);
                        
                        if (window._ag_rclick) {
                            window._ag_rclick(imgX + ',' + imgY);
                        } else {
                            try {
                                IPython.notebook.kernel.execute('_ag_rclick("' + imgX + ',' + imgY + '")');
                            } catch(e) {}
                        }
                        
                        img.style.outline = 'none';
                    }, 500);
                }, {passive: true});
                
                img.addEventListener('touchend', function(e) {
                    if (longPressTimer) clearTimeout(longPressTimer);
                });
                
                img.addEventListener('touchmove', function(e) {
                    if (longPressTimer) {
                        clearTimeout(longPressTimer);
                        longPressTimer = null;
                    }
                });
                
                // Visual click feedback
                function showClickFeedback(x, y) {
                    var feedback = document.createElement('div');
                    feedback.style.cssText = 
                        'position: absolute;' +
                        'left: ' + x + 'px;' +
                        'top: ' + y + 'px;' +
                        'width: 20px;' +
                        'height: 20px;' +
                        'background: rgba(88, 166, 255, 0.5);' +
                        'border: 2px solid #58a6ff;' +
                        'border-radius: 50%;' +
                        'pointer-events: none;' +
                        'transform: translate(-50%, -50%);' +
                        'animation: clickPulse 0.5s ease-out forwards;' +
                        'z-index: 1000;';
                    
                    var parent = img.parentElement;
                    parent.style.position = 'relative';
                    parent.appendChild(feedback);
                    
                    setTimeout(function() {
                        feedback.remove();
                    }, 500);
                }
                
                // Add animation style
                var style = document.createElement('style');
                style.textContent = 
                    '@keyframes clickPulse {' +
                    '  0% { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }' +
                    '  100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }' +
                    '}';
                document.head.appendChild(style);
                
                console.log('Browser Controller: JavaScript injected successfully');
                
            } else {
                console.log('Browser Controller: Waiting for image...');
                // Retry after a delay
                setTimeout(arguments.callee, 1000);
            }
        }, 1000);
    });
    </script>
    """
    return js_code

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_browser():
    """Main initialization function"""
    print("═" * 70))
    print("🌐 KAGGLE BROWSER CONTROLLER - Initializing...")
    print("═" * 70))
    
    # Setup environment
    os.makedirs("/tmp/xdg-runtime", mode=0o700, exist_ok=True)
    os.environ["XDG_RUNTIME_DIR"] = "/tmp/xdg-runtime"
    os.environ["DISPLAY"] = DISPLAY_NUM
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"
    
    # Start Xvfb
    if not start_xvfb():
        print("❌ Failed to start Xvfb. Aborting.")
        return
    
    # Start Chrome
    if not start_chrome():
        print("❌ Failed to start Chrome. Aborting.")
        cleanup()
        return
    
    # Create widgets
    print("🎨 Creating widgets...")
    main_widget = create_widgets()
    
    # Inject JavaScript
    print("📜 Injecting JavaScript for touch/click...")
    js_html = HTML(inject_javascript())
    
    # Start screenshot thread
    time.sleep(1)
    start_screenshot_thread(3)
    
    # Start heartbeat
    start_heartbeat()
    
    # Display everything
    clear_output(wait=True)
    display(js_html)
    display(main_widget)
    
    print("═" * 70))
    print("✅ Browser Controller Ready!")
    print("═" * 70))
    print("📋 Usage:")
    print("   • Click on the image to click in the browser")
    print("   • Right-click for context menu")
    print("   • Touch supported for mobile/tablet")
    print("   • Long-press for right-click on touch devices")
    print("   • Type in the chat box and press Send (or Ctrl+Enter)")
    print("═" * 70))
    
    # Register cleanup
    import atexit
    atexit.register(cleanup)
    
    return main_widget

# ═══════════════════════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════════════════════

# Run the initialization
init_browser()
