import os
import requests

LOCAL_LAUNCHER = 'kaggle_launcher.py'
REMOTE_LAUNCHER = 'https://raw.githubusercontent.com/amerameryou1-blip/Wjsjsjsj/main/kaggle_launcher.py'


def main():
    if os.path.exists(LOCAL_LAUNCHER):
        code = open(LOCAL_LAUNCHER, 'r', encoding='utf-8').read()
        exec(compile(code, LOCAL_LAUNCHER, 'exec'), {'__name__': '__main__'})
        return

    response = requests.get(REMOTE_LAUNCHER, timeout=90)
    response.raise_for_status()
    exec(compile(response.text, REMOTE_LAUNCHER, 'exec'), {'__name__': '__main__'})


if __name__ == '__main__':
    main()
