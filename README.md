# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 JUPYTER BROWSER CONTROLLER - KAGGLE EDITION
# ═══════════════════════════════════════════════════════════════════════════════
# Features: Xvfb + Chrome browser automation with screenshot, clicks, keyboard
# Kaggle Compatible: TPU v4, P100, CPU Only
# ═══════════════════════════════════════════════════════════════════════════════

import subprocess
import threading
import time
import os
import re
import urllib.request
import base64
from io import BytesIO
from IPython.display import display, HTML, clear_output
import ipywidgets as widgets

# ═══════════════════════════════════════════════════════════════════════════════
# KAGGLE SETUP & CHECKS
# ═══════════════════════════════════════════════════════════════════════════════

print("🚀 Initializing Browser Controller...")

# Check if we're on Kaggle
ON_KAGGLE = os.path.exists('/kaggle/working')

if ON_KAGGLE:
    print("📍 Detected: Kaggle Environment")
    # Create XDG runtime directory for Chrome
    os.makedirs('/tmp/xdg-runtime', mode=0o777, exist_ok=True)
    os.environ['XDG_RUNTIME_DIR'] = '/tmp/xdg-runtime'
    # Create downloads directory
    os.makedirs('/tmp/chrome-downloads', exist_ok=True)
    DOWNLOAD_PATH = '/tmp/chrome-downloads'
else:
    DOWNLOAD_PATH = os.path.expanduser('~/Downloads')
    print("📍 Detected: Local Environment")

# Display info
print(f"   • Download path: {DOWNLOAD_PATH}")
print(f"   • XDG_RUNTIME_DIR: {os.environ.get('XDG_RUNTIME_DIR', 'not set')}")

# ═══════════════════════════════════════════════════════════════════════════════
# XVB & CHROME PROCESS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

xvfb_process = None
chrome_process = None
screenshot_thread = None
heartbeat_thread = None
running = True
frame_count = 0
screenshot_interval = 3  # seconds

DISPLAY_NUM = ":99"
SCREEN_SIZE = "1280x800x24"

def get_display_env():
    """Get environment with correct DISPLAY for xdotool"""
    env = os.environ.copy()
    env['DISPLAY'] = DISPLAY_NUM
    env['XAUTHORITY'] = '/tmp/.xa99'  # Dummy auth for xdotool
    return env

def check_xvfb_running():
    """Check if Xvfb is already running on display :99"""
    try:
        result = subprocess.run(
            ['ps', 'aux'], capture_output=True, text=True
        )
        return f'Xvfb {DISPLAY_NUM}' in result.stdout
    except:
        return False

def start_xvfb():
    """Start Xvfb virtual display"""
    global xvfb_process
    
    if check_xvfb_running():
        print("✓ Xvfb already running on", DISPLAY_NUM)
        return True
    
    print(f"🎬 Starting Xvfb on {DISPLAY_NUM}...")
    try:
        xvfb_process = subprocess.Popen(
            ['Xvfb', DISPLAY_NUM, '-screen', '0', SCREEN_SIZE, '-ac', '+extension', 'GLX', '+render'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        
        # Create dummy X authority
        subprocess.run(['touch', '/tmp/.xa99'], check=False)
        
        print(f"✓ Xvfb started (PID: {xvfb_process.pid})")
        return True
    except FileNotFoundError:
        print("❌ Xvfb not found. Installing...")
        subprocess.run(['apt-get', 'update'], check=False)
        subprocess.run(['apt-get', 'install', '-y', 'xvfb'], check=False)
        return start_xvfb()
    except Exception as e:
        print(f"❌ Xvfb failed: {e}")
        return False

def start_chrome():
    """Start Chrome browser"""
    global chrome_process
    
    print("🌐 Starting Chrome...")
    chrome_args = [
        'google-chrome',
        '--no-sandbox',
        '--disable-gpu',
        '--disable-dev-shm-usage',
        '--disable-setuid-sandbox',
        '--disable-session-crashed-bubble',
        '--disable-infobars',
        '--no-first-run',
        '--start-maximized',
        f'--window-size=1280,800',
        '--new-window',
        '--homepage=about:blank',
        f'--download-default-directory={DOWNLOAD_PATH}',
        '--kiosk',
        'https://www.google.com'
    ]
    
    try:
        chrome_process = subprocess.Popen(
            chrome_args,
            env=get_display_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"✓ Chrome started (PID: {chrome_process.pid})")
        time.sleep(2)
        return True
    except FileNotFoundError:
        print("❌ Chrome not found. Installing...")
        if ON_KAGGLE:
            # Install Chrome on Kaggle
            subprocess.run(['wget', '-q', '-O', '/tmp/chrome.deb',
                          'https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb'],
                         check=False)
            subprocess.run(['dpkg', '--install', '/tmp/chrome.deb'], check=False)
            subprocess.run(['apt-get', '-f', 'install', '-y'], check=False)
        else:
            subprocess.run(['apt-get', 'install', '-y', 'google-chrome'], check=False)
        return start_chrome()
    except Exception as e:
        print(f"❌ Chrome failed: {e}")
        return False

def xdotool_type(text):
    """Type text using xdotool"""
    subprocess.run(
        ['xdotool', 'type', '--clearmodifiers', text],
        env=get_display_env(),
        check=False
    )

def xdotool_key(key):
    """Press a key using xdotool"""
    subprocess.run(
        ['xdotool', 'key', key],
        env=get_display_env(),
        check=False
    )

def xdotool_click(button=1):
    """Click mouse button (1=left, 2=middle, 3=right, 4=scroll up, 5=scroll down)"""
    subprocess.run(
        ['xdotool', 'click', str(button)],
        env=get_display_env(),
        check=False
    )

def xdotool_mousemove(x, y):
    """Move mouse to coordinates"""
    subprocess.run(
        ['xdotool', 'mousemove', str(int(x)), str(int(y))],
        env=get_display_env(),
        check=False
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SCREENSHOT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def take_screenshot():
    """Take screenshot using scrot, gnome-screenshot, or ImageMagick"""
    temp_file = '/tmp/frame.png'
    
    # Try different screenshot tools in order of preference
    tools = [
        ['scrot', temp_file, '-o'],  # scrot
        ['gnome-screenshot', '-f', temp_file],  # gnome-screenshot
        ['import', '-window', 'root', temp_file],  # ImageMagick
        ['xfce4-screenshooter', '-f', '-s', temp_file],  # XFCE
        [' flameshot', 'full', '-p', temp_file],  # Flameshot
    ]
    
    for tool in tools:
        try:
            result = subprocess.run(
                tool, env=get_display_env(),
                capture_output=True, timeout=5
            )
            if os.path.exists(temp_file):
                return temp_file
        except:
            continue
    
    # Fallback: Use xwd + convert
    try:
        subprocess.run(
            ['xwd', '-root', '-screen', '-display', DISPLAY_NUM, '-out', '/tmp/frame.xwd'],
            env=get_display_env(), check=False
        )
        subprocess.run(
            ['convert', '/tmp/frame.xwd', temp_file],
            check=False
        )
        if os.path.exists(temp_file):
            return temp_file
    except:
        pass
    
    return None

def update_screenshot():
    """Update the screenshot display"""
    global frame_count
    
    screenshot_file = take_screenshot()
    if screenshot_file and os.path.exists(screenshot_file):
        try:
            with open(screenshot_file, 'rb') as f:
                img.value = f.read()
            frame_count += 1
            status.value = "Frame #" + str(frame_count) + " - Screenshot updated"
        except Exception as e:
            status.value = "Frame #" + str(frame_count) + " - Screenshot error: " + str(e)
    else:
        status.value = "Frame #" + str(frame_count) + " - Failed to capture screenshot"

def screenshot_worker():
    """Background thread for periodic screenshots"""
    while running:
        update_screenshot()
        time.sleep(screenshot_interval)

# ═══════════════════════════════════════════════════════════════════════════════
# KERNEL COMMUNICATION (JAVAScript Injection)
# ═══════════════════════════════════════════════════════════════════════════════

def setup_javascript_injection():
    """Setup JavaScript handlers for click/touch events"""
    # Get the output area for communication
    from IPython import get_ipython
    ipython = get_ipython()
    
    if ipython is None:
        print("⚠️  Not in IPython environment, JS injection skipped")
        return
    
    # JavaScript code to inject
    js_code = """
    
    (function() {
        // Wait for elements to be ready
        function init() {
            var img = document.querySelector('.browser-screenshot');
            if (!img) {
                setTimeout(init, 500);
                return;
            }
            
            // Style the image
            img.style.cursor = 'crosshair';
            img.style.border = '3px solid #00ff88';
            img.style.borderRadius = '8px';
            
            // Coordinate scaling
            function getScaledCoords(e) {
                var rect = img.getBoundingClientRect();
                var clientX = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
                var clientY = e.clientY || (e.touches && e.touches[0] ? e.touches[0].clientY : 0);
                
                var scaleX = 1280 / rect.width;
                var scaleY = 800 / rect.height;
                
                var x = Math.round((clientX - rect.left) * scaleX);
                var y = Math.round((clientY - rect.top) * scaleY);
                
                return x + ',' + y;
            }
            
            // Left click
            img.addEventListener('click', function(e) {
                e.preventDefault();
                var coords = getScaledCoords(e);
                console.log('Click at:', coords);
                
                // Visual feedback
                var overlay = document.createElement('div');
                overlay.style.cssText = 'position:absolute;pointer-events:none;left:' + 
                    (e.clientX - 10) + 'px;top:' + (e.clientY - 10) + 
                    'px;width:20px;height:20px;border:2px solid #00ff88;' +
                    'border-radius:50%;animation:clickRipple 0.5s forwards;';
                document.body.appendChild(overlay);
                setTimeout(() => overlay.remove(), 500);
                
                // Execute in kernel
                if (typeof _ag_click === 'function') {
                    _ag_click(coords);
                } else {
                    // Fallback: direct xdotool
                    var coords = getScaledCoords(e);
                    var parts = coords.split(',');
                    IPython.notebook.kernel.execute(
                        'import subprocess, os; ' +
                        'subprocess.run(["xdotool", "mousemove", "' + parts[0] + '", "' + parts[1] + '"], env={"DISPLAY": ":99"}); ' +
                        'subprocess.run(["xdotool", "click", "1"], env={"DISPLAY": ":99"});'
                    );
                }
            });
            
            // Prevent context menu (right click)
            img.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                var coords = getScaledCoords(e);
                console.log('Right click at:', coords);
                
                if (typeof _ag_rclick === 'function') {
                    _ag_rclick(coords);
                }
            });
            
            // Touch support
            var touchTimer = null;
            img.addEventListener('touchstart', function(e) {
                e.preventDefault();
                touchTimer = setTimeout(function() {
                    var coords = getScaledCoords(e);
                    if (typeof _ag_rclick === 'function') {
                        _ag_rclick(coords);
                    }
                }, 500);
            });
            
            img.addEventListener('touchend', function(e) {
                e.preventDefault();
                if (touchTimer) {
                    clearTimeout(touchTimer);
                    touchTimer = null;
                }
                var coords = getScaledCoords(e);
                if (typeof _ag_click === 'function') {
                    _ag_click(coords);
                }
            });
            
            img.addEventListener('touchcancel', function() {
                if (touchTimer) {
                    clearTimeout(touchTimer);
                    touchTimer = null;
                }
            });
            
            console.log('✅ Browser controller JS injected');
        }
        
        // CSS animation
        var style = document.createElement('style');
        style.textContent = '@keyframes clickRipple { to { opacity: 0; transform: scale(2); } }';
        document.head.appendChild(style);
        
        init();
    })();
    
    """
    
    display(HTML(js_code))

def _ag_click(coords):
    """Handle click from JavaScript - move mouse and click"""
    try:
        x, y = map(int, coords.split(','))
        xdotool_mousemove(x, y)
        time.sleep(0.05)
        xdotool_click(1)
        status.value = "Frame #" + str(frame_count) + " - Left click at (" + str(x) + ", " + str(y) + ")"
    except Exception as e:
        status.value = "Frame #" + str(frame_count) + " - Click error: " + str(e)

def _ag_rclick(coords):
    """Handle right click from JavaScript"""
    try:
        x, y = map(int, coords.split(','))
        xdotool_mousemove(x, y)
        time.sleep(0.05)
        xdotool_click(3)
        status.value = "Frame #" + str(frame_count) + " - Right click at (" + str(x) + ", " + str(y) + ")"
    except Exception as e:
        status.value = "Frame #" + str(frame_count) + " - Right click error: " + str(e)

# ═══════════════════════════════════════════════════════════════════════════════
# BUTTON HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

def on_go_clicked(b):
    """Navigate to URL in URL input"""
    url = url_input.value
    if not url.startswith(('http://', 'https://', 'file://')):
        url = 'https://' + url
    
    # Ctrl+L to focus address bar, type URL, Enter
    xdotool_key('ctrl+l')
    time.sleep(0.3)
    xdotool_type(url)
    time.sleep(0.2)
    xdotool_key('Return')
    status.value = "Frame #" + str(frame_count) + " - Navigating to " + url

def on_back_clicked(b):
    """Go back in browser history"""
    xdotool_key('Alt+Left')
    status.value = "Frame #" + str(frame_count) + " - Back"

def on_forward_clicked(b):
    """Go forward in browser history"""
    xdotool_key('Alt+Right')
    status.value = "Frame #" + str(frame_count) + " - Forward"

def on_reload_clicked(b):
    """Reload current page"""
    xdotool_key('F5')
    status.value = "Frame #" + str(frame_count) + " - Reloading..."

def on_home_clicked(b):
    """Go to home page"""
    xdotool_key('Alt+Home')
    status.value = "Frame #" + str(frame_count) + " - Home"

def on_enter_clicked(b):
    """Press Enter key"""
    xdotool_key('Return')
    status.value = "Frame #" + str(frame_count) + " - Enter"

def on_escape_clicked(b):
    """Press Escape key"""
    xdotool_key('Escape')
    status.value = "Frame #" + str(frame_count) + " - Escape"

def on_tab_clicked(b):
    """Press Tab key"""
    xdotool_key('Tab')
    status.value = "Frame #" + str(frame_count) + " - Tab"

def on_arrow_up_clicked(b):
    """Press Arrow Up key"""
    xdotool_key('Up')
    status.value = "Frame #" + str(frame_count) + " - Up"

def on_arrow_down_clicked(b):
    """Press Arrow Down key"""
    xdotool_key('Down')
    status.value = "Frame #" + str(frame_count) + " - Down"

def on_pageup_clicked(b):
    """Press Page Up key"""
    xdotool_key('Prior')
    status.value = "Frame #" + str(frame_count) + " - PgUp"

def on_pagedown_clicked(b):
    """Press Page Down key"""
    xdotool_key('Next')
    status.value = "Frame #" + str(frame_count) + " - PgDn"

def on_copy_clicked(b):
    """Copy (Ctrl+C)"""
    xdotool_key('ctrl+c')
    status.value = "Frame #" + str(frame_count) + " - Copy (Ctrl+C)"

def on_paste_clicked(b):
    """Paste (Ctrl+V)"""
    xdotool_key('ctrl+v')
    status.value = "Frame #" + str(frame_count) + " - Paste (Ctrl+V)"

def on_selectall_clicked(b):
    """Select All (Ctrl+A)"""
    xdotool_key('ctrl+a')
    status.value = "Frame #" + str(frame_count) + " - Select All (Ctrl+A)"

def on_rightclick_clicked(b):
    """Right click at current mouse position"""
    xdotool_click(3)
    status.value = "Frame #" + str(frame_count) + " - Right click"

def on_scroll_up_clicked(b):
    """Scroll up (mouse wheel)"""
    xdotool_click(4)
    status.value = "Frame #" + str(frame_count) + " - Scroll Up"

def on_scroll_down_clicked(b):
    """Scroll down (mouse wheel)"""
    xdotool_click(5)
    status.value = "Frame #" + str(frame_count) + " - Scroll Down"

def on_zoom_in_clicked(b):
    """Zoom in (Ctrl++)"""
    xdotool_key('ctrl+plus')
    status.value = "Frame #" + str(frame_count) + " - Zoom In"

def on_zoom_out_clicked(b):
    """Zoom out (Ctrl+-)"""
    xdotool_key('ctrl+minus')
    status.value = "Frame #" + str(frame_count) + " - Zoom Out"

def on_fast_screenshot(b):
    """Fast screenshots (1 second)"""
    global screenshot_interval
    screenshot_interval = 1
    status.value = "Frame #" + str(frame_count) + " - Fast mode (1s)"

def on_slow_screenshot(b):
    """Slow screenshots (5 seconds)"""
    global screenshot_interval
    screenshot_interval = 5
    status.value = "Frame #" + str(frame_count) + " - Slow mode (5s)"

def on_type_clicked(b):
    """Type text from type input"""
    text = type_input.value
    if text:
        xdotool_type(text)
        display_text = text[:30] + "..." if len(text) > 30 else text
        status.value = "Frame #" + str(frame_count) + " - Typing: " + display_text
        type_input.value = ""

def on_chat_send(b):
    """Send chat message"""
    text = chat_input.value
    if text:
        xdotool_type(text)
        chat_input.value = ""
        display_text = text[:30] + "..." if len(text) > 30 else text
        status.value = "Frame #" + str(frame_count) + " - Sent: " + display_text

# ═══════════════════════════════════════════════════════════════════════════════
# CREATE WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

print("🎨 Creating widgets...")

# Screenshot image
img = widgets.Image(
    format='png',
    width='100%',
    layout=widgets.Layout(border='3px solid #00ff88', border_radius='8px')
)

# Status label
status = widgets.Label(
    value='Initializing...',
    layout=widgets.Layout(padding='10px', background_color='#1a1a2e')
)

# URL input
url_input = widgets.Text(
    value='https://www.google.com',
    placeholder='Enter URL...',
    layout=widgets.Layout(flex='1'),
    description=''
)

# Type input
type_input = widgets.Text(
    value='',
    placeholder='Type text here...',
    layout=widgets.Layout(flex='1'),
    description=''
)

# Chat input
chat_input = widgets.Textarea(
    value='',
    placeholder='💬 Chat message (Ctrl+Enter to send)...',
    layout=widgets.Layout(width='100%', height='60px'),
    description=''
)

# Navigation buttons (Row 1)
btn_go = widgets.Button(description=' 🌐 Go', button_style='success')
btn_back = widgets.Button(description=' ◀ Back')
btn_forward = widgets.Button(description=' ▶ Fwd')
btn_reload = widgets.Button(description=' 🔄 Reload')
btn_home = widgets.Button(description=' 🏠 Home')

# Keyboard buttons (Row 2)
btn_enter = widgets.Button(description=' ↵ Enter', button_style='info')
btn_escape = widgets.Button(description=' Esc')
btn_tab = widgets.Button(description=' ⇥ Tab')
btn_up = widgets.Button(description=' ▲ Up')
btn_down = widgets.Button(description=' ▼ Down')
btn_pageup = widgets.Button(description=' PgUp')
btn_pagedown = widgets.Button(description=' PgDn')

# Tools buttons (Row 3)
btn_copy = widgets.Button(description=' ⎘ Copy')
btn_paste = widgets.Button(description=' ⌘ Paste')
btn_selectall = widgets.Button(description=' Sel All')
btn_rightclick = widgets.Button(description=' 🖱️ RClick')
btn_scroll_up = widgets.Button(description=' ▲ Scroll')
btn_scroll_down = widgets.Button(description=' ▼ Scroll')
btn_zoom_in = widgets.Button(description=' 🔍+ Zoom')
btn_zoom_out = widgets.Button(description=' 🔍- Zoom')
btn_fast = widgets.Button(description=' 📸 Fast 1s', button_style='warning')
btn_slow = widgets.Button(description=' 📸 Slow 5s', button_style='warning')
btn_type = widgets.Button(description=' 📝 Type', button_style='primary')
btn_chat = widgets.Button(description=' 💬 Send', button_style='success')

# Assign click handlers
btn_go.on_click(on_go_clicked)
btn_back.on_click(on_back_clicked)
btn_forward.on_click(on_forward_clicked)
btn_reload.on_click(on_reload_clicked)
btn_home.on_click(on_home_clicked)
btn_enter.on_click(on_enter_clicked)
btn_escape.on_click(on_escape_clicked)
btn_tab.on_click(on_tab_clicked)
btn_up.on_click(on_arrow_up_clicked)
btn_down.on_click(on_arrow_down_clicked)
btn_pageup.on_click(on_pageup_clicked)
btn_pagedown.on_click(on_pagedown_clicked)
btn_copy.on_click(on_copy_clicked)
btn_paste.on_click(on_paste_clicked)
btn_selectall.on_click(on_selectall_clicked)
btn_rightclick.on_click(on_rightclick_clicked)
btn_scroll_up.on_click(on_scroll_up_clicked)
btn_scroll_down.on_click(on_scroll_down_clicked)
btn_zoom_in.on_click(on_zoom_in_clicked)
btn_zoom_out.on_click(on_zoom_out_clicked)
btn_fast.on_click(on_fast_screenshot)
btn_slow.on_click(on_slow_screenshot)
btn_type.on_click(on_type_clicked)
btn_chat.on_click(on_chat_send)

# Layout
row1 = widgets.HBox([btn_go, btn_back, btn_forward, btn_reload, btn_home])
row2 = widgets.HBox([btn_enter, btn_escape, btn_tab, btn_up, btn_down, btn_pageup, btn_pagedown])
row3 = widgets.HBox([btn_copy, btn_paste, btn_selectall, btn_rightclick, btn_scroll_up, btn_scroll_down, btn_zoom_in, btn_zoom_out])
row4 = widgets.HBox([btn_fast, btn_slow])

type_row = widgets.HBox([type_input, btn_type])
chat_row = widgets.HBox([chat_input, btn_chat])

# ═══════════════════════════════════════════════════════════════════════════════
# START EVERYTHING
# ═══════════════════════════════════════════════════════════════════════════════

def start_browser():
    """Start the browser and all services"""
    global screenshot_thread, heartbeat_thread
    
    # Start Xvfb
    if not start_xvfb():
        print("❌ Failed to start Xvfb")
        return False
    
    # Start Chrome
    if not start_chrome():
        print("❌ Failed to start Chrome")
        return False
    
    # Start screenshot thread
    running = True
    screenshot_thread = threading.Thread(target=screenshot_worker, daemon=True)
    screenshot_thread.start()
    print("✓ Screenshot thread started")
    
    # Setup JavaScript injection
    setup_javascript_injection()
    
    # Start heartbeat (prevents Kaggle timeout)
    if ON_KAGGLE:
        def heartbeat():
            """Send periodic output to prevent Kaggle timeout"""
            while running:
                print("❤️ Keep-alive ping...", flush=True)
                time.sleep(25)  # Kaggle timeout is usually 30-60 seconds
        
        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()
        print("✓ Heartbeat thread started")
    
    return True

def cleanup():
    """Cleanup processes"""
    global running
    running = False
    
    if chrome_process:
        chrome_process.terminate()
        print("✓ Chrome terminated")
    
    if xvfb_process:
        xvfb_process.terminate()
        print("✓ Xvfb terminated")

# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY UI
# ═══════════════════════════════════════════════════════════════════════════════

print("\\n" + "="*60)
print("🌐 BROWSER CONTROLLER FOR KAGGLE")
print("="*60)

if start_browser():
    print("\\n✅ Everything started successfully!")
    print("\\n" + "="*60)
    print("📋 WIDGETS")
    print("="*60)
    
    # Display all widgets
    display(widgets.VBox([
        widgets.HTML('🌐 Browser Controller'),
        widgets.HTML('Click the image to click in browser | Touch supported'),
        img,
        status,
        widgets.HTML('🌐 Navigation:'),
        row1,
        widgets.HTML('⌨️  Keyboard:'),
        row2,
        widgets.HTML('🛠️  Tools:'),
        row3,
        row4,
        widgets.HTML('📝 Type Text:'),
        type_row,
        widgets.HTML('💬 Chat:'),
        chat_row,
        widgets.HTML(''),
        widgets.HTML('Kaggle Browser Controller v1.0 | Click image to interact')
    ]))
    
    print("\\n✨ UI displayed above!")
    print("💡 Tips:")
    print("   • Click image = Left click in browser")
    print("   • Right-click image = Context menu")
    print("   • Mobile: Tap to click, hold for right-click")
else:
    print("\\n❌ Startup failed. Check the output above.")

# Register cleanup
import atexit
atexit.register(cleanup)
