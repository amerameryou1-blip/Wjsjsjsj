# Zorin-Style Kaggle Desktop Pack

This repository has been fully rewritten for the Kaggle notebook environment.

## What this project is now
It **does not try to boot a full Zorin OS ISO inside Kaggle**.
Instead, it recreates the **Windows-like Zorin experience** on top of the Ubuntu-based Kaggle runtime by installing and configuring a lightweight **XFCE desktop** with a **bottom taskbar**, **Whisker Menu**, persistent browser profile, persistent downloads, and notebook-side remote control tools.

That is the practical version that fits Kaggle:
- install desktop packages into the current notebook runtime
- save desktop state, downloads, profile, wallpaper, and config in **`/kaggle/working/zorin_kaggle_desktop`**
- restore the layout and files on the next run
- keep controlling it from the notebook

## Research-backed decisions used in the rewrite
The rewrite was based on documentation and reference pages, not pure guessing.

1. **Kaggle persistence**
   - The persistent working area is `/kaggle/working`, so this project saves state there.

2. **Zorin OS direction**
   - Zorin OS is Ubuntu-based and has been built around **GNOME** and **Xfce** variants.
   - That makes an **Xfce-based Windows-like recreation** a realistic Kaggle target.

3. **Windows-like app menu**
   - Xfce’s **Whisker Menu** is documented as a searchable applications launcher.
   - That gives us a Start-menu-like experience.

4. **Fixing long-press / context-menu issues**
   - `ipyevents` documents `prevent_default_action=True` for suppressing default right-click context menus.
   - That is used on the live screenshot surface.

5. **Fixing drag / hold behavior**
   - `xdotool` documents `mousedown` and `mouseup` separately.
   - The rewritten controller uses those instead of only fast click events.

6. **Fixing the scrot filename bug pattern**
   - `scrot` supports explicit output files and overwrite mode.
   - The rewrite reuses one capture file instead of generating endless numbered screenshots.

## Files
- `kaggle_launcher.py` — main bootstrap entry point for Kaggle
- `browser_controller_support.py` — install, state, desktop, capture, input, download, and GitHub helpers
- `browser_controller_main.py` — Jupyter/Kaggle UI for controlling the desktop
- `browser_controller_full.py` — convenience wrapper entry point

## Main features
- full rewrite for Kaggle
- installs a **Zorin-style XFCE desktop stack**
- saves state in **`/kaggle/working/zorin_kaggle_desktop`**
- creates a **Windows-like bottom panel**
- uses a **Whisker Menu** launcher flow
- writes theme + desktop layout files into persistent Kaggle storage
- creates a persistent **browser profile**
- creates a persistent **downloads** folder
- supports **download → extract → run/open** workflows
- supports **AppImage**, shell scripts, folders, archives, and normal files
- supports **remote clipboard read/write**
- supports **paste fallback** and **type text fallback**
- supports **separate mouse-down/mouse-up** for drag and hold
- suppresses notebook/browser context menus on the live screen
- includes a **shell runner** with copyable output
- includes optional **GitHub push** for the rewritten files

## What gets saved in Kaggle
Everything important is kept under:

`/kaggle/working/zorin_kaggle_desktop`

Important subfolders:
- `home/` — persistent desktop home directory
- `downloads/` — downloaded files and apps
- `browser-profile/` — persistent browser state
- `captures/` — reusable screenshot output file
- `logs/` — runtime logs
- `wallpapers/` — generated wallpaper assets
- `bundle-cache/` — fetched Python bundle cache

## Why this is the right Kaggle shape
Kaggle notebook sessions are temporary, so package installs may need to be re-run when a fresh runtime starts.

However, the **desktop configuration and files** are saved into `/kaggle/working`, so the rewritten launcher restores the environment shape quickly on later runs.

That gives you the best practical result in Kaggle:
- temporary runtime packages
- persistent user state and downloaded content

## Launch from Kaggle
Fastest path:

```python
import requests
exec(requests.get('https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/kaggle_launcher.py').text)
```

Or after uploading the files manually:

```python
exec(open('kaggle_launcher.py', 'r', encoding='utf-8').read())
```

## What the notebook UI gives you
### Session tools
- Install / Repair
- Start desktop
- Apply Zorin layout
- Open browser
- Open terminal
- Open files
- Refresh screen

### Input tools
- live screenshot surface
- better mobile touch handling
- drag / hold support
- scroll support
- release stuck mouse buttons

### Clipboard tools
- read remote clipboard
- write remote clipboard
- paste text using terminal-style shortcuts
- type text directly as keys
- copy shell output back to the browser clipboard

### Download tools
- download by URL
- save file with a chosen name
- extract archives
- run/open downloaded files
- zip all downloads
- notebook download links

### GitHub tools
- paste a token
- push the rewritten bundle files back to your repo

## Practical limitation
This project recreates a **Zorin-style desktop experience**, not the full official Zorin distribution image.

In Kaggle, that is the realistic and reproducible path.

## Repository URLs
- Repo: https://github.com/amerameryou1-blip/Wjsjsjsj
- Launcher raw: https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/kaggle_launcher.py
- Main raw: https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/browser_controller_main.py
- Support raw: https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/browser_controller_support.py
- Full raw: https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/browser_controller_full.py
