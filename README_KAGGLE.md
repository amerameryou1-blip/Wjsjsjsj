# Kaggle territorial.io launcher system

This repo layout is generated to replace the old notebook-magic-only raw file.

## Why the old version failed
The previous `Google` file used commands like `!apt-get update -y`.
That syntax works in notebook cells, but it is invalid Python when you run:

```python
exec(requests.get("https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/Google").text)
```

## 409 Secret detected fix
The token is **never** embedded in any file. The launcher reads it from
`os.getenv("GITHUB_TOKEN")` at runtime. Set this as a Kaggle Secret
(Add-ons → Secrets) with the name `GITHUB_TOKEN`.

## Files
- `Google` → pure Python launcher that writes helper files locally, installs runtime, opens territorial.io, saves output, and auto-updates GitHub
- `install_runtime.py` → installs Chromium/ChromeDriver and pip packages from Python
- `browser_runner.py` → opens https://territorial.io/ and saves a screenshot
- `github_push.py` → pushes local files to GitHub using the Contents API

## Kaggle usage
1. Enable Internet in your notebook settings.
2. Add a Kaggle Secret named `GITHUB_TOKEN` with your PAT value.
3. Run the bootstrap cell to download and execute the launcher.
4. The launcher opens territorial.io, saves output, and auto-pushes everything to GitHub.
