# ════════════════════════════════════════════════════════════════════════════════
# 🖥️  BROWSER CONTROLLER FOR KAGGLE - COMPLETE SOURCE
# ════════════════════════════════════════════════════════════════════════════════
# Xvfb + Chrome browser automation with live screenshots
# 
# Features:
#   🌐 Navigate websites with virtual display
#   📸 Live screenshots updated automatically  
#   🖱️  Click anywhere on screenshot to click in browser
#   📱 Touch support for mobile devices
#   💬 Chat input to type messages
#   ⌨️  Full keyboard support
#   🔍 Zoom in/out
#   📜 Scroll up/down
#   ❤️ Heartbeat to keep Kaggle session alive
#
# Requirements: Internet enabled in Kaggle settings
# ════════════════════════════════════════════════════════════════════════════════

import subprocess
import threading
import time
import os
import sys
import base64
import io
import re
import IPython
from IPython.display import display, HTML, clear_output

# ════════════════════════════════════════════════════════════════════════════════
# CHECK IMPORTS
# ════════════════════════════════════════════════════════════════════════════════

try:
    import xvfbwrapper
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "xvfbwrapper"], capture_output=True)
    import xvfbwrapper

try:
    from PIL import Image
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], capture_output=True)
    from PIL import Image

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], capture_output=True)
    import requests

try:
    import ipywidgets as widgets
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "ipywidgets"], capture_output=True)
    import ipywidgets as widgets

# ════════════════════════════════════════════════════════════════════════════════
# SETUP ENVIRONMENT
# ════════════════════════════════════════════════════════════════════════════════

os.environ["DISPLAY"] = ":99"
os.environ["XAUTHORITY"] = "/tmp/xauth"
os.makedirs("/tmp/xdg-runtime", exist_ok=True)
os.environ["XDG_RUNTIME_DIR"] = "/tmp/xdg-runtime"

# Create X authority
subprocess.run(["bash", "-c", "xauth generate :99 . trusted timeout 3600 2>/dev/null || true"], capture_output=True)

# ════════════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ════════════════════════════════════════════════════════════════════════════════

frame_count = 0
screenshot_interval = 3
screenshot_thread = None
stop_screenshot = threading.Event()
heartbeat_thread = None
stop_heartbeat = threading.Event()
vdisplay = None
browser_process = None
image_widget = None
status_widget = None
url_widget = None
type_widget = None
chat_widget = None

# Screen dimensions
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800

# ════════════════════════════════════════════════════════════════════════════════
# XDOTOOL HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def xdotool(args):
    cmd = ["xvfb-run", "-a", "--server-num=99", "xdotool"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

def xdotool_nowait(args):
    cmd = ["xvfb-run", "-a", "--server-num=99", "xdotool"] + args
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def log_action(msg):
    if status_widget:
        status_widget.value = msg

# ════════════════════════════════════════════════════════════════════════════════
# INSTALL CHROME
# ════════════════════════════════════════════════════════════════════════════════

def install_chrome():
    print("🔍 Checking for Chrome/Chromium...")
    
    # Check if already installed
    result = subprocess.run(["bash", "-c", "which google-chrome || which chromium-browser || which chromium"], capture_output=True, text=True)
    if result.stdout.strip():
        print("✅ Chrome/Chromium found: " + result.stdout.strip())
        return result.stdout.strip()
    
    # Try Chrome first
    try:
        print("📦 Installing Chrome...")
        subprocess.run([
            "bash", "-c",
            "wget -q -O /tmp/chrome.deb https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_current_amd64.deb && "
            "dpkg -i /tmp/chrome.deb || apt-get install -f -y"
        ], env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"}, timeout=180, capture_output=True)
        
        result = subprocess.run(["bash", "-c", "which google-chrome"], capture_output=True, text=True)
        if result.stdout.strip():
            print("✅ Chrome installed successfully")
            return result.stdout.strip()
    except Exception as e:
        print("⚠️ Chrome install attempt failed: " + str(e))
    
    # Fallback to Chromium
    try:
        print("📦 Installing Chromium as fallback...")
        subprocess.run([
            "bash", "-c",
            "apt-get update && apt-get install -y chromium chromium-browser 2>/dev/null"
        ], env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"}, timeout=180, capture_output=True)
        
        for cmd in ["chromium", "chromium-browser", "google-chrome"]:
            result = subprocess.run(["bash", "-c", "which " + cmd], capture_output=True, text=True)
            if result.stdout.strip():
                print("✅ Chromium installed: " + result.stdout.strip())
                return result.stdout.strip()
    except Exception as e:
        print("⚠️ Chromium install failed: " + str(e))
    
    print("❌ No browser found, will try anyway")
    return None

# ════════════════════════════════════════════════════════════════════════════════
# INSTALL DEPENDENCIES
# ════════════════════════════════════════════════════════════════════════════════

def install_dependencies():
    print("🔧 Installing system dependencies...")
    
    packages = [
        "xvfb",
        "xdotool", 
        "scrot",
        "imagemagick",
        "wget",
        "gnupg2",
        "libatk1.0-0",
        "libatk-bridge2.0-0",
        "libatspi2.0-0",
        "libvulkan1",
        "libxcomposite1",
        "libxdamage1",
        "libxrandr2",
        "libasound2",
        "libpangocairo-1.0-0",
        "libpango-1.0-0",
        "libgtk-3-0"
    ]
    
    for pkg in packages:
        try:
            subprocess.run(
                ["bash", "-c", "apt-get install -y " + pkg + " 2>/dev/null"],
                env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
                timeout=60,
                capture_output=True
            )
        except:
            pass
    
    print("✅ Dependencies installed")

# ════════════════════════════════════════════════════════════════════════════════
# BROWSER CONTROL FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def start_browser(url="https://www.google.com"):
    global vdisplay, browser_process
    
    print("🎮 Starting virtual display :99...")
    
    # Stop any existing
    stop_browser()
    time.sleep(1)
    
    # Kill any existing Xvfb
    subprocess.run(["bash", "-c", "pkill -9 Xvfb 2>/dev/null || true"], capture_output=True)
    time.sleep(0.5)
    
    # Start Xvfb
    try:
        vdisplay = xvfbwrapper.Xvfb(width=SCREEN_WIDTH, height=SCREEN_HEIGHT, depth=24, display=99)
        vdisplay.start()
        print("✅ Xvfb started on :99")
    except Exception as e:
        print("⚠️ Xvfb start error: " + str(e))
        # Try manual start
        subprocess.run(["bash", "-c", "Xvfb :99 -screen 0 1280x800x24 &"], capture_output=True)
        time.sleep(2)
    
    # Install Chrome if needed
    chrome_path = install_chrome()
    
    # Create download directory
    subprocess.run(["bash", "-c", "mkdir -p /tmp/chrome-downloads"], capture_output=True)
    
    print("🌐 Starting Chrome...")
    
    chrome_options = [
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--window-size=1280,800",
        "--start-maximized",
        "--disable-infobars",
        "--disable-extensions",
        "--no-first-run",
        "--disable-session-crashed-bubble",
        "--disable-crash-reporter",
        "--disable-oopr-debug-crash-dump",
        "--user-data-dir=/tmp/chrome-profile",
        "--download-default-directory=/tmp/chrome-downloads",
        "--autoplay-policy=no-user-gesture-required"
    ]
    
    if chrome_path:
        cmd = [chrome_path] + chrome_options + [url]
    else:
        # Try common paths
        for path in ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]:
            if os.path.exists(path):
                cmd = [path] + chrome_options + [url]
                break
        else:
            cmd = ["google-chrome"] + chrome_options + [url]
    
    try:
        browser_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "DISPLAY": ":99"}
        )
        print("✅ Chrome started (PID: " + str(browser_process.pid) + ")")
        time.sleep(3)
    except Exception as e:
        print("❌ Chrome start failed: " + str(e))
    
    return True

def stop_browser():
    global vdisplay, browser_process
    if browser_process:
        try:
            browser_process.terminate()
            time.sleep(0.5)
            browser_process.kill()
        except:
            pass
        browser_process = None
    if vdisplay:
        try:
            vdisplay.stop()
        except:
            pass
        vdisplay = None

def navigate_to(url):
    log_action("🌐 Navigating to: " + url)
    xdotool_nowait(["key", "--window=root", "ctrl+l"])
    time.sleep(0.3)
    xdotool(["type", "--window=root", url])
    time.sleep(0.2)
    xdotool(["key", "--window=root", "Return"])
    log_action("✅ Navigated to: " + url)

def go_back():
    log_action("◀ Going back")
    xdotool(["key", "--window=root", "Alt+Left"])
    time.sleep(0.5)

def go_forward():
    log_action("▶ Going forward")
    xdotool(["key", "--window=root", "Alt+Right"])
    time.sleep(0.5)

def reload_page():
    log_action("🔄 Reloading page")
    xdotool(["key", "--window=root", "F5"])
    time.sleep(1)

def go_home():
    log_action("🏠 Going home")
    xdotool(["key", "--window=root", "Alt+Home"])
    time.sleep(1)

def press_enter():
    log_action("↵ Pressing Enter")
    xdotool(["key", "--window=root", "Return"])
    time.sleep(0.2)

def press_escape():
    log_action("❌ Pressing Escape")
    xdotool(["key", "--window=root", "Escape"])
    time.sleep(0.2)

def press_tab():
    log_action("⇥ Pressing Tab")
    xdotool(["key", "--window=root", "Tab"])
    time.sleep(0.2)

def press_arrow_up():
    log_action("▲ Arrow Up")
    xdotool(["key", "--window=root", "Up"])
    time.sleep(0.1)

def press_arrow_down():
    log_action("▼ Arrow Down")
    xdotool(["key", "--window=root", "Down"])
    time.sleep(0.1)

def press_page_up():
    log_action("PgUp Pressed")
    xdotool(["key", "--window=root", "Prior"])
    time.sleep(0.2)

def press_page_down():
    log_action("PgDn Pressed")
    xdotool(["key", "--window=root", "Next"])
    time.sleep(0.2)

def type_text(text):
    if text:
        log_action("⌨️ Typing: " + text[:30] + ("..." if len(text) > 30 else ""))
        xdotool(["type", "--window=root", text])
        time.sleep(0.1)

def copy_selection():
    log_action("⎘ Copying (Ctrl+C)")
    xdotool(["key", "--window=root", "ctrl+c"])
    time.sleep(0.3)

def paste_text():
    log_action("📋 Pasting (Ctrl+V)")
    xdotool(["key", "--window=root", "ctrl+v"])
    time.sleep(0.3)

def select_all():
    log_action("✨ Selecting All (Ctrl+A)")
    xdotool(["key", "--window=root", "ctrl+a"])
    time.sleep(0.3)

def right_click():
    log_action("🖱️ Right Click")
    xdotool(["click", "3"])
    time.sleep(0.3)

def scroll_up():
    log_action("📜 Scrolling Up")
    xdotool(["click", "--window=root", "4"])
    time.sleep(0.2)

def scroll_down():
    log_action("📜 Scrolling Down")
    xdotool(["click", "--window=root", "5"])
    time.sleep(0.2)

def zoom_in():
    log_action("🔍 Zooming In")
    xdotool(["key", "--window=root", "ctrl+plus"])
    time.sleep(0.3)

def zoom_out():
    log_action("🔍 Zooming Out")
    xdotool(["key", "--window=root", "ctrl+minus"])
    time.sleep(0.3)

def reset_zoom():
    log_action("🔄 Resetting Zoom")
    xdotool(["key", "--window=root", "ctrl+0"])
    time.sleep(0.3)

# ════════════════════════════════════════════════════════════════════════════════
# SCREENSHOT FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def capture_screenshot():
    global frame_count
    
    # Try scrot first
    result = subprocess.run(
        ["bash", "-c", "DISPLAY=:99 scrot /tmp/frame.png -o 2>/dev/null"],
        capture_output=True
    )
    
    if os.path.exists("/tmp/frame.png") and os.path.getsize("/tmp/frame.png") > 0:
        try:
            with open("/tmp/frame.png", "rb") as f:
                img_data = f.read()
            frame_count = frame_count + 1
            return img_data, True
        except:
            pass
    
    # Try gnome-screenshot fallback
    result = subprocess.run(
        ["bash", "-c", "DISPLAY=:99 gnome-screenshot -f /tmp/frame.png 2>/dev/null"],
        capture_output=True
    )
    
    if os.path.exists("/tmp/frame.png") and os.path.getsize("/tmp/frame.png") > 0:
        try:
            with open("/tmp/frame.png", "rb") as f:
                img_data = f.read()
            frame_count = frame_count + 1
            return img_data, True
        except:
            pass
    
    # Try ImageMagick import fallback
    result = subprocess.run(
        ["bash", "-c", "DISPLAY=:99 import -window root /tmp/frame.png 2>/dev/null"],
        capture_output=True
    )
    
    if os.path.exists("/tmp/frame.png") and os.path.getsize("/tmp/frame.png") > 0:
        try:
            with open("/tmp/frame.png", "rb") as f:
                img_data = f.read()
            frame_count = frame_count + 1
            return img_data, True
        except:
            pass
    
    # Create placeholder image
    try:
        from PIL import Image
        img = Image.new("RGB", (640, 400), color=(30, 30, 30))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        frame_count = frame_count + 1
        return buf.getvalue(), True
    except:
        return None, False

# ════════════════════════════════════════════════════════════════════════════════
# SCREENSHOT THREAD
# ════════════════════════════════════════════════════════════════════════════════

def screenshot_loop():
    global screenshot_thread, stop_screenshot, image_widget, status_widget
    
    while not stop_screenshot.is_set():
        try:
            img_data, success = capture_screenshot()
            
            if success and img_data and image_widget:
                image_widget.value = img_data
                
                if status_widget:
                    status_widget.value = "Frame #" + str(frame_count) + " - Screenshot updated"
        except Exception as e:
            if status_widget:
                status_widget.value = "Screenshot error: " + str(e)
        
        stop_screenshot.wait(screenshot_interval)
    
    print("🛑 Screenshot thread stopped")

def start_screenshot_thread(interval=3):
    global screenshot_thread, stop_screenshot, screenshot_interval
    
    screenshot_interval = interval
    
    if screenshot_thread and screenshot_thread.is_alive():
        stop_screenshot.set()
        screenshot_thread.join(timeout=2)
    
    stop_screenshot = threading.Event()
    screenshot_thread = threading.Thread(target=screenshot_loop, daemon=True)
    screenshot_thread.start()
    print("📸 Screenshot thread started (interval: " + str(interval) + "s)")

def stop_screenshot_thread():
    global stop_screenshot
    if stop_screenshot:
        stop_screenshot.set()
    print("🛑 Screenshot thread stopping...")

# ════════════════════════════════════════════════════════════════════════════════
# HEARTBEAT THREAD - KEEP KAGGLE SESSION ALIVE
# ════════════════════════════════════════════════════════════════════════════════

def heartbeat_loop():
    global stop_heartbeat
    
    print("❤️ Heartbeat thread started")
    while not stop_heartbeat.is_set():
        try:
            # Simple network request to keep session alive
            import urllib.request
            try:
                urllib.request.urlopen("https://www.google.com", timeout=5)
            except:
                pass
        except:
            pass
        
        stop_heartbeat.wait(25)
    
    print("❤️ Heartbeat thread stopped")

def start_heartbeat():
    global heartbeat_thread, stop_heartbeat
    
    if heartbeat_thread and heartbeat_thread.is_alive():
        return
    
    stop_heartbeat = threading.Event()
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()

def stop_heartbeat_thread():
    global stop_heartbeat
    if stop_heartbeat:
        stop_heartbeat.set()
    print("❤️ Heartbeat thread stopping...")

# ════════════════════════════════════════════════════════════════════════════════
# CLICK HANDLERS
# ════════════════════════════════════════════════════════════════════════════════

def _ag_click(coords_str):
    global frame_count, status_widget
    
    try:
        parts = coords_str.split(",")
        img_x = int(float(parts[0]))
        img_y = int(float(parts[1]))
        
        # Get actual image display size
        if image_widget and hasattr(image_widget, "_layout"):
            display_width = image_widget.layout.width
            if display_width and "px" in str(display_width):
                display_width = int(str(display_width).replace("px", ""))
            else:
                display_width = SCREEN_WIDTH
        else:
            display_width = SCREEN_WIDTH
        
        # Scale to screen coordinates
        scale_x = SCREEN_WIDTH / display_width
        scale_y = SCREEN_HEIGHT / SCREEN_WIDTH
        
        screen_x = int(img_x * scale_x)
        screen_y = int(img_y * scale_y)
        
        # Clamp to screen bounds
        screen_x = max(0, min(screen_x, SCREEN_WIDTH - 1))
        screen_y = max(0, min(screen_y, SCREEN_HEIGHT - 1))
        
        log_action("🖱️ Left click at (" + str(screen_x) + ", " + str(screen_y) + ")")
        
        # Move mouse and click
        xdotool_nowait(["mousemove", "--display", ":99", str(screen_x), str(screen_y)])
        time.sleep(0.1)
        xdotool_nowait(["click", "--display", ":99", "1"])
        
        frame_count = frame_count + 1
        
    except Exception as e:
        log_action("❌ Click error: " + str(e))

def _ag_rclick(coords_str):
    global frame_count, status_widget
    
    try:
        parts = coords_str.split(",")
        img_x = int(float(parts[0]))
        img_y = int(float(parts[1]))
        
        scale_x = SCREEN_WIDTH / 640
        scale_y = SCREEN_HEIGHT / 400
        
        screen_x = int(img_x * scale_x)
        screen_y = int(img_y * scale_y)
        
        screen_x = max(0, min(screen_x, SCREEN_WIDTH - 1))
        screen_y = max(0, min(screen_y, SCREEN_HEIGHT - 1))
        
        log_action("🖱️ Right click at (" + str(screen_x) + ", " + str(screen_y) + ")")
        
        xdotool_nowait(["mousemove", "--display", ":99", str(screen_x), str(screen_y)])
        time.sleep(0.1)
        xdotool_nowait(["click", "--display", ":99", "3"])
        
        frame_count = frame_count + 1
        
    except Exception as e:
        log_action("❌ Right-click error: " + str(e))

# ════════════════════════════════════════════════════════════════════════════════
# BUTTON HANDLERS
# ════════════════════════════════════════════════════════════════════════════════

def on_go_clicked(b):
    url = url_widget.value.strip()
    if url:
        if not url.startswith("http"):
            url = "https://" + url
        navigate_to(url)
    else:
        log_action("⚠️ Enter a URL first")

def on_back_clicked(b):
    go_back()

def on_forward_clicked(b):
    go_forward()

def on_reload_clicked(b):
    reload_page()

def on_home_clicked(b):
    go_home()

def on_enter_clicked(b):
    press_enter()

def on_escape_clicked(b):
    press_escape()

def on_tab_clicked(b):
    press_tab()

def on_arrow_up_clicked(b):
    press_arrow_up()

def on_arrow_down_clicked(b):
    press_arrow_down()

def on_page_up_clicked(b):
    press_page_up()

def on_page_down_clicked(b):
    press_page_down()

def on_copy_clicked(b):
    copy_selection()

def on_paste_clicked(b):
    paste_text()

def on_select_all_clicked(b):
    select_all()

def on_right_click_btn(b):
    right_click()

def on_scroll_up_clicked(b):
    scroll_up()

def on_scroll_down_clicked(b):
    scroll_down()

def on_zoom_in_clicked(b):
    zoom_in()

def on_zoom_out_clicked(b):
    zoom_out()

def on_fast_screenshot(b):
    log_action("📸 Fast screenshot: 1s")
    start_screenshot_thread(1)

def on_slow_screenshot(b):
    log_action("📸 Slow screenshot: 5s")
    start_screenshot_thread(5)

def on_type_submit(sender):
    text = type_widget.value
    if text:
        type_text(text)
        type_widget.value = ""

def on_chat_send(sender):
    text = chat_widget.value
    if text:
        type_text(text)
        press_enter()
        chat_widget.value = ""

# ════════════════════════════════════════════════════════════════════════════════
# CREATE WIDGETS
# ════════════════════════════════════════════════════════════════════════════════

def create_widgets():
    global image_widget, status_widget, url_widget, type_widget, chat_widget
    
    # Image widget for screenshots
    image_widget = widgets.Image(
        format="png",
        width="100%",
        layout=widgets.Layout(border="3px solid #00ff88", border_radius="8px")
    )
    
    # Status label
    status_widget = widgets.Label(
        value="Initializing...",
        layout=widgets.Layout(padding="10px", background_color="#1a1a2e", width="100%")
    )
    
    # URL input
    url_widget = widgets.Text(
        value="https://www.google.com",
        placeholder="Enter URL...",
        layout=widgets.Layout(flex="1"),
        description=""
    )
    
    # Type input
    type_widget = widgets.Text(
        value="",
        placeholder="Type text and press Enter...",
        layout=widgets.Layout(flex="1"),
        description=""
    )
    
    # Chat input
    chat_widget = widgets.Textarea(
        value="",
        placeholder="Chat message (Ctrl+Enter to send)...",
        layout=widgets.Layout(width="100%", height="80px"),
        description=""
    )
    
    # Submit buttons for text inputs
    type_submit = widgets.Button(
        description="Send",
        button_style="primary",
        layout=widgets.Layout(padding="5px 15px")
    )
    type_submit.on_click(on_type_submit)
    type_widget.on_submit(on_type_submit)
    
    chat_submit = widgets.Button(
        description="💬 Send Chat",
        button_style="success",
        layout=widgets.Layout(padding="5px 15px")
    )
    chat_submit.on_click(on_chat_send)
    
    # ROW 1: Navigation buttons
    btn_go = widgets.Button(
        description="🌐 Go",
        button_style="success",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_go.on_click(on_go_clicked)
    
    btn_back = widgets.Button(
        description="◀ Back",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_back.on_click(on_back_clicked)
    
    btn_fwd = widgets.Button(
        description="▶ Fwd",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_fwd.on_click(on_forward_clicked)
    
    btn_reload = widgets.Button(
        description="🔄 Reload",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_reload.on_click(on_reload_clicked)
    
    btn_home = widgets.Button(
        description="🏠 Home",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_home.on_click(on_home_clicked)
    
    row1 = widgets.HBox([
        btn_go, btn_back, btn_fwd, btn_reload, btn_home
    ], layout=widgets.Layout(margin="5px 0"))
    
    # ROW 2: Key buttons
    btn_enter = widgets.Button(
        description="↵ Enter",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_enter.on_click(on_enter_clicked)
    
    btn_esc = widgets.Button(
        description="Esc",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_esc.on_click(on_escape_clicked)
    
    btn_tab = widgets.Button(
        description="⇥ Tab",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_tab.on_click(on_tab_clicked)
    
    btn_up = widgets.Button(
        description="▲",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_up.on_click(on_arrow_up_clicked)
    
    btn_down = widgets.Button(
        description="▼",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_down.on_click(on_arrow_down_clicked)
    
    btn_pgup = widgets.Button(
        description="PgUp",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_pgup.on_click(on_page_up_clicked)
    
    btn_pgdn = widgets.Button(
        description="PgDn",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_pgdn.on_click(on_page_down_clicked)
    
    row2 = widgets.HBox([
        btn_enter, btn_esc, btn_tab, btn_up, btn_down, btn_pgup, btn_pgdn
    ], layout=widgets.Layout(margin="5px 0"))
    
    # ROW 3: Tools buttons
    btn_copy = widgets.Button(
        description="⎘ Copy",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_copy.on_click(on_copy_clicked)
    
    btn_paste = widgets.Button(
        description="⌘ Paste",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_paste.on_click(on_paste_clicked)
    
    btn_selall = widgets.Button(
        description="Sel All",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_selall.on_click(on_select_all_clicked)
    
    btn_rclick = widgets.Button(
        description="🖱️ RClick",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_rclick.on_click(on_right_click_btn)
    
    btn_scrlup = widgets.Button(
        description="▲ Scroll",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_scrlup.on_click(on_scroll_up_clicked)
    
    btn_scrldn = widgets.Button(
        description="▼ Scroll",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_scrldn.on_click(on_scroll_down_clicked)
    
    btn_zoomin = widgets.Button(
        description="🔍+",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_zoomin.on_click(on_zoom_in_clicked)
    
    btn_zoomout = widgets.Button(
        description="🔍-",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_zoomout.on_click(on_zoom_out_clicked)
    
    row3 = widgets.HBox([
        btn_copy, btn_paste, btn_selall, btn_rclick, btn_scrlup, btn_scrldn, btn_zoomin, btn_zoomout
    ], layout=widgets.Layout(margin="5px 0"))
    
    # ROW 4: Screenshot speed
    btn_fast = widgets.Button(
        description="📸 Fast 1s",
        button_style="warning",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_fast.on_click(on_fast_screenshot)
    
    btn_slow = widgets.Button(
        description="📸 Slow 5s",
        button_style="info",
        layout=widgets.Layout(padding="8px 12px")
    )
    btn_slow.on_click(on_slow_screenshot)
    
    row4 = widgets.HBox([
        btn_fast, btn_slow
    ], layout=widgets.Layout(margin="5px 0"))
    
    # URL bar
    url_bar = widgets.HBox([
        widgets.HTML("URL:"),
        url_widget,
        type_submit
    ], layout=widgets.Layout(margin="5px 0"))
    
    # Type bar
    type_bar = widgets.HBox([
        widgets.HTML("Type:"),
        type_widget
    ], layout=widgets.Layout(margin="5px 0"))
    
    # Chat bar
    chat_bar = widgets.VBox([
        widgets.HTML("💬 Chat:"),
        chat_widget,
        chat_submit
    ], layout=widgets.Layout(margin="5px 0"))
    
    return widgets.VBox([
        status_widget,
        image_widget,
        url_bar,
        type_bar,
        row1,
        row2,
        row3,
        row4,
        chat_bar
    ])

# ════════════════════════════════════════════════════════════════════════════════
# JAVASCRIPT INJECTION FOR IMAGE INTERACTIVITY
# ════════════════════════════════════════════════════════════════════════════════

def get_javascript():
    js = """
    
    function setupImageInteraction() {
        var img = document.querySelector('img[data-checked="checked"]');
        if (!img) {
            setTimeout(setupImageInteraction, 500);
            return;
        }
        
        img.style.cursor = 'crosshair';
        img.style.border = '3px solid #00ff88';
        img.style.boxShadow = '0 0 20px rgba(0, 255, 136, 0.3)';
        
        // Desktop click
        img.onclick = function(e) {
            var rect = img.getBoundingClientRect();
            var x = Math.round((e.clientX - rect.left) * (img.naturalWidth / rect.width));
            var y = Math.round((e.clientY - rect.top) * (img.naturalHeight / rect.height));
            var kernel = IPython.notebook.kernel;
            kernel.execute('_ag_click("' + x + ',' + y + '")');
            showClickFeedback(e.clientX, e.clientY);
        };
        
        // Right click
        img.oncontextmenu = function(e) {
            e.preventDefault();
            var rect = img.getBoundingClientRect();
            var x = Math.round((e.clientX - rect.left) * (img.naturalWidth / rect.width));
            var y = Math.round((e.clientY - rect.top) * (img.naturalHeight / rect.height));
            var kernel = IPython.notebook.kernel;
            kernel.execute('_ag_rclick("' + x + ',' + y + '")');
        };
        
        // Touch support
        img.addEventListener('touchstart', function(e) {
            img._touchTimer = setTimeout(function() {
                var touch = e.touches[0];
                var rect = img.getBoundingClientRect();
                var x = Math.round((touch.clientX - rect.left) * (img.naturalWidth / rect.width));
                var y = Math.round((touch.clientY - rect.top) * (img.naturalHeight / rect.height));
                var kernel = IPython.notebook.kernel;
                kernel.execute('_ag_rclick("' + x + ',' + y + '")');
            }, 500);
        });
        
        img.addEventListener('touchend', function(e) {
            if (img._touchTimer) {
                clearTimeout(img._touchTimer);
                var touch = e.changedTouches[0];
                var rect = img.getBoundingClientRect();
                var x = Math.round((touch.clientX - rect.left) * (img.naturalWidth / rect.width));
                var y = Math.round((touch.clientY - rect.top) * (img.naturalHeight / rect.height));
                var kernel = IPython.notebook.kernel;
                kernel.execute('_ag_click("' + x + ',' + y + '")');
                showClickFeedback(touch.clientX, touch.clientY);
            }
        });
        
        img.addEventListener('touchmove', function(e) {
            if (img._touchTimer) {
                clearTimeout(img._touchTimer);
            }
        });
        
        console.log('✅ Image interaction enabled');
    }
    
    function showClickFeedback(x, y) {
        var dot = document.createElement('div');
        dot.style.cssText = 'position:fixed;left:' + (x-8) + 'px;top:' + (y-8) + 'px;width:16px;height:16px;background:#00ff88;border-radius:50%;pointer-events:none;z-index:9999;animation:clickPulse 0.5s ease-out forwards;';
        document.body.appendChild(dot);
        setTimeout(function() { dot.remove(); }, 500);
    }
    
    function addClickAnimation() {
        var style = document.createElement('style');
        style.textContent = '@keyframes clickPulse { 0% { transform: scale(1); opacity: 1; } 100% { transform: scale(2); opacity: 0; } }';
        document.head.appendChild(style);
    }
    
    document.addEventListener('DOMContentLoaded', function() {
        addClickAnimation();
        setupImageInteraction();
    });
    
    """
    return js

# ════════════════════════════════════════════════════════════════════════════════
# MAIN LAUNCH FUNCTION
# ════════════════════════════════════════════════════════════════════════════════

def launch_browser_controller(start_url="https://www.google.com"):
    global image_widget, status_widget
    
    print("=" * 60)
    print("🖥️  BROWSER CONTROLLER FOR KAGGLE")
    print("=" * 60)
    
    # Install deps
    install_dependencies()
    
    # Start browser
    print("🚀 Launching browser controller...")
    start_browser(start_url)
    
    # Create widgets
    print("🎨 Creating widgets...")
    ui = create_widgets()
    
    # Display
    print("📺 Displaying UI...")
    display(ui)
    
    # Inject JavaScript
    display(HTML(get_javascript()))
    
    # Start threads
    print("📡 Starting threads...")
    start_screenshot_thread(3)
    start_heartbeat()
    
    # Initial screenshot
    time.sleep(2)
    img_data, success = capture_screenshot()
    if success and img_data and image_widget:
        image_widget.value = img_data
    
    log_action("✅ Browser controller ready! Frame #" + str(frame_count))
    print("=" * 60)
    print("✅ READY! Click on the image to click in the browser.")
    print("=" * 60)
    
    return ui

# ════════════════════════════════════════════════════════════════════════════════
# CLEANUP FUNCTION
# ════════════════════════════════════════════════════════════════════════════════

def cleanup():
    print("🧹 Cleaning up...")
    stop_screenshot_thread()
    stop_heartbeat_thread()
    stop_browser()
    print("✅ Cleanup complete")

# ════════════════════════════════════════════════════════════════════════════════
# AUTO-LAUNCH
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    launch_browser_controller("https://www.google.com")
