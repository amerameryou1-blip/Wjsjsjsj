import os
import io
import re
import json
import time
import base64
import shutil
import signal
import socket
import atexit
import threading
import subprocess
from pathlib import Path

# =========================
# USER CONFIG
# =========================
NGROK_AUTHTOKEN = "3AIkODWCDloeF626Is1rLhPJYVT_aZRViWM7vAnGGQ55UD1v"
PORT = 8000
SCREEN_W = 1280
SCREEN_H = 800
START_URL = "https://www.google.com"
STATE_DIR = "/kaggle/working/browser_remote_state"
PROFILE_DIR = os.path.join(STATE_DIR, "chrome-profile")
DOWNLOAD_DIR = os.path.join(STATE_DIR, "downloads")
LAST_FRAME = os.path.join(STATE_DIR, "last_frame.jpg")
PUBLIC_INFO = os.path.join(STATE_DIR, "public_url.json")

# =========================
# BOOTSTRAP
# =========================
def sh(cmd, check=False, capture=True, env=None):
    if isinstance(cmd, list):
        result = subprocess.run(cmd, check=check, capture_output=capture, text=True, env=env)
    else:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True, env=env)
    return result


def pip_install(*packages):
    cmd = ["python", "-m", "pip", "install", "-q"] + list(packages)
    sh(cmd, check=False)


def ensure_system():
    os.environ.setdefault("DEBIAN_FRONTEND", "noninteractive")
    os.environ["DISPLAY"] = ":99"
    os.environ.setdefault("XDG_RUNTIME_DIR", "/tmp/xdg-runtime")
    Path("/tmp/xdg-runtime").mkdir(parents=True, exist_ok=True)
    Path(STATE_DIR).mkdir(parents=True, exist_ok=True)
    Path(PROFILE_DIR).mkdir(parents=True, exist_ok=True)
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    apt_packages = [
        "xvfb", "xdotool", "scrot", "imagemagick", "curl", "wget", "ca-certificates",
        "libatk1.0-0", "libatk-bridge2.0-0", "libatspi2.0-0", "libvulkan1", "libnss3",
        "libxcomposite1", "libxdamage1", "libxrandr2", "libasound2", "libpangocairo-1.0-0",
        "libpango-1.0-0", "libgtk-3-0"
    ]
    sh("apt-get update -qq", check=False)
    sh("apt-get install -y -qq " + " ".join(apt_packages), check=False)

    chrome_ok = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if not chrome_ok:
        sh("wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb", check=False)
        sh("apt-get install -y /tmp/google-chrome.deb", check=False)
        sh("apt-get install -f -y", check=False)

    pip_install("fastapi", "uvicorn", "pyngrok", "pillow", "requests")


def chrome_bin():
    for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
        p = shutil.which(name)
        if p:
            return p
    return "google-chrome"


ensure_system()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image, ImageDraw
from pyngrok import ngrok
import uvicorn

# =========================
# RUNTIME STATE
# =========================
frame_lock = threading.Lock()
latest_frame_bytes = b""
latest_frame_meta = {"ts": 0, "cursor": {"x": SCREEN_W // 2, "y": SCREEN_H // 2}, "action": "booting"}
stop_event = threading.Event()
xvfb_proc = None
chrome_proc = None
cursor_x = SCREEN_W // 2
cursor_y = SCREEN_H // 2
stream_quality = 85
stream_width = 1100
stream_height = 688
public_url = None


# =========================
# HELPERS
# =========================
def run_display(cmd):
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    return sh(cmd, check=False, capture=True, env=env)


def xdotool(*args):
    return run_display(["xdotool"] + list(args))


def set_cursor(x, y):
    global cursor_x, cursor_y
    cursor_x = max(0, min(SCREEN_W - 1, int(x)))
    cursor_y = max(0, min(SCREEN_H - 1, int(y)))
    xdotool("mousemove", str(cursor_x), str(cursor_y))


def draw_cursor_overlay(image, x, y):
    draw = ImageDraw.Draw(image)
    color = (0, 255, 120)
    r = 11
    draw.line((x - 20, y, x + 20, y), fill=color, width=2)
    draw.line((x, y - 20, x, y + 20), fill=color, width=2)
    draw.ellipse((x - r, y - r, x + r, y + r), outline=(255, 70, 70), width=3)
    draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255))


def capture_frame():
    tmp = "/tmp/remote_frame.png"
    run_display(f"scrot {tmp} -o")
    if not os.path.exists(tmp):
        return None
    try:
        img = Image.open(tmp).convert("RGB")
        draw_cursor_overlay(img, cursor_x, cursor_y)
        img.thumbnail((stream_width, stream_height))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=stream_quality, optimize=True)
        data = buf.getvalue()
        with open(LAST_FRAME, "wb") as f:
            f.write(data)
        return data
    except Exception:
        return None


def frame_loop():
    global latest_frame_bytes, latest_frame_meta
    while not stop_event.is_set():
        data = capture_frame()
        if data:
            with frame_lock:
                latest_frame_bytes = data
                latest_frame_meta = {
                    "ts": int(time.time() * 1000),
                    "cursor": {"x": cursor_x, "y": cursor_y},
                    "action": latest_frame_meta.get("action", "updated")
                }
        time.sleep(0.6)


def launch_xvfb():
    global xvfb_proc
    xvfb_proc = subprocess.Popen(
        ["Xvfb", ":99", "-screen", "0", f"{SCREEN_W}x{SCREEN_H}x24", "-ac"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)


def launch_chrome():
    global chrome_proc
    cmd = [
        chrome_bin(),
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-setuid-sandbox",
        "--window-size=1280,800",
        f"--user-data-dir={PROFILE_DIR}",
        f"--download-default-directory={DOWNLOAD_DIR}",
        "--disable-first-run-ui",
        "--no-first-run",
        "--no-default-browser-check",
        START_URL,
    ]
    env = os.environ.copy()
    env["DISPLAY"] = ":99"
    chrome_proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    set_cursor(cursor_x, cursor_y)


def open_url(url):
    xdotool("key", "ctrl+l")
    time.sleep(0.15)
    xdotool("type", "--delay", "1", url)
    time.sleep(0.1)
    xdotool("key", "Return")
    latest_frame_meta["action"] = "open_url"


def type_text(text):
    if not text:
        return
    xdotool("type", "--delay", "1", text)
    latest_frame_meta["action"] = "type_text"


def key_press(key):
    xdotool("key", key)
    latest_frame_meta["action"] = "key:" + key


def click_at(x, y, button=1):
    set_cursor(x, y)
    time.sleep(0.05)
    xdotool("click", str(button))
    latest_frame_meta["action"] = "click"


def move_cursor(dx, dy):
    set_cursor(cursor_x + dx, cursor_y + dy)
    latest_frame_meta["action"] = "move_cursor"


def list_downloads():
    items = []
    for p in sorted(Path(DOWNLOAD_DIR).glob("*")):
        if p.is_file():
            items.append({"name": p.name, "size": p.stat().st_size})
    return items


def write_public_info(url):
    payload = {
        "public_url": url,
        "api": {
            "frame": url.rstrip("/") + "/api/frame",
            "meta": url.rstrip("/") + "/api/meta",
            "click": url.rstrip("/") + "/api/click",
            "move": url.rstrip("/") + "/api/move",
            "key": url.rstrip("/") + "/api/key",
            "type": url.rstrip("/") + "/api/type",
            "open": url.rstrip("/") + "/api/open",
        },
    }
    with open(PUBLIC_INFO, "w") as f:
        json.dump(payload, f, indent=2)


def cleanup():
    stop_event.set()
    for proc in [chrome_proc, xvfb_proc]:
        try:
            if proc and proc.poll() is None:
                proc.terminate()
        except Exception:
            pass
    try:
        ngrok.kill()
    except Exception:
        pass


atexit.register(cleanup)


# =========================
# API
# =========================
class ClickBody(BaseModel):
    x: int
    y: int
    button: int = 1


class MoveBody(BaseModel):
    dx: int = 0
    dy: int = 0


class KeyBody(BaseModel):
    key: str


class TypeBody(BaseModel):
    text: str
    press_enter: bool = False


class OpenBody(BaseModel):
    url: str


app = FastAPI(title="Kaggle Remote Browser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def root():
    html = f"""
    <html>
      <head>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>Kaggle Remote Browser Backend</title>
        <style>
          body {{ font-family: Arial, sans-serif; background:#0b1020; color:#e9eefc; padding:24px; }}
          code, pre {{ background:#111936; color:#b8ffcf; padding:12px; border-radius:10px; display:block; overflow:auto; }}
          a {{ color:#7fd4ff; }}
        </style>
      </head>
      <body>
        <h1>Kaggle Remote Browser Backend</h1>
        <p>Backend is running.</p>
        <pre>{json.dumps({"public_url": public_url, "state_dir": STATE_DIR, "downloads": DOWNLOAD_DIR}, indent=2)}</pre>
        <p>Frame endpoint: <a href=\"/api/frame\">/api/frame</a></p>
        <p>Meta endpoint: <a href=\"/api/meta\">/api/meta</a></p>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/api/meta")
def api_meta():
    return {
        "ok": True,
        "screen": {"width": SCREEN_W, "height": SCREEN_H},
        "cursor": {"x": cursor_x, "y": cursor_y},
        "downloads": list_downloads(),
        "public_url": public_url,
        "state_dir": STATE_DIR,
        "profile_dir": PROFILE_DIR,
        "download_dir": DOWNLOAD_DIR,
        "last_action": latest_frame_meta.get("action", "idle"),
        "timestamp": latest_frame_meta.get("ts", 0),
    }


@app.get("/api/frame")
def api_frame():
    if os.path.exists(LAST_FRAME):
        return FileResponse(LAST_FRAME, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="No frame yet")


@app.post("/api/click")
def api_click(body: ClickBody):
    click_at(body.x, body.y, body.button)
    return {"ok": True, "cursor": {"x": cursor_x, "y": cursor_y}}


@app.post("/api/move")
def api_move(body: MoveBody):
    move_cursor(body.dx, body.dy)
    return {"ok": True, "cursor": {"x": cursor_x, "y": cursor_y}}


@app.post("/api/key")
def api_key(body: KeyBody):
    key_press(body.key)
    return {"ok": True}


@app.post("/api/type")
def api_type(body: TypeBody):
    type_text(body.text)
    if body.press_enter:
        key_press("Return")
    return {"ok": True}


@app.post("/api/open")
def api_open(body: OpenBody):
    open_url(body.url)
    return {"ok": True}


@app.get("/api/downloads")
def api_downloads():
    return {"ok": True, "items": list_downloads()}


# =========================
# START
# =========================
launch_xvfb()
launch_chrome()
threading.Thread(target=frame_loop, daemon=True).start()
ngrok.set_auth_token(NGROK_AUTHTOKEN)
tunnel = ngrok.connect(PORT, bind_tls=True)
public_url = tunnel.public_url
write_public_info(public_url)
print("Public URL:", public_url)
print("Saved info:", PUBLIC_INFO)
uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
