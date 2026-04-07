from pathlib import Path
import shutil
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

TARGET_URL = "https://territorial.io/"


def find_chrome_binary():
    for candidate in [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ]:
        if Path(candidate).exists():
            return candidate
    return None


def find_chromedriver():
    candidates = [
        "/usr/bin/chromedriver",
        shutil.which("chromedriver"),
        shutil.which("chromium-chromedriver"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def build_options(headless_flag=None):
    binary = find_chrome_binary()
    if binary is None:
        raise FileNotFoundError("Could not find Chromium/Chrome on this runtime.")

    options = Options()
    options.binary_location = binary
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")
    if headless_flag:
        options.add_argument(headless_flag)
    return options


def build_driver(headless=True):
    driver_path = find_chromedriver()
    if driver_path is None:
        raise FileNotFoundError("Could not find chromedriver on this runtime.")

    service = Service(driver_path)

    if not headless:
        return webdriver.Chrome(service=service, options=build_options())

    last_error = None
    for flag in ["--headless=new", "--headless"]:
        try:
            return webdriver.Chrome(service=service, options=build_options(flag))
        except Exception as exc:
            last_error = exc
    raise last_error


def run(url=TARGET_URL, wait_seconds=6, screenshot_name="territorial_io.png", headless=True):
    driver = build_driver(headless=headless)
    try:
        driver.get(url)
        time.sleep(wait_seconds)
        output_dir = Path("/kaggle/working")
        if not output_dir.exists():
            output_dir = Path.cwd()
        screenshot_path = output_dir / screenshot_name
        driver.save_screenshot(str(screenshot_path))

        result = {
            "url": url,
            "title": driver.title,
            "screenshot": str(screenshot_path),
        }
        print("Opened:", result["url"])
        print("Title:", result["title"])
        print("Screenshot:", result["screenshot"])
        return result
    finally:
        driver.quit()


if __name__ == "__main__":
    run()
