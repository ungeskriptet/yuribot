import os
import shlex
import subprocess
from yt_dlp import YoutubeDL

filename = {}

def convert_gif() -> str:
    command = f'ffmpeg -y -i temp/video.mp4 -vf "scale=-1:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" temp/animation.gif'
    ffmpeg_cmd = subprocess.run(
        shlex.split(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=False
    )

    return 'temp/animation.gif'

def progress_hook(hook) -> None:
    if hook['status'] == 'finished':
        url = hook['info_dict']['original_url']
        file = hook['info_dict']['_filename']
        filename[url] = file

def download_link(url: str, path: str) -> str:
    ydl_opts = {
        'progress_hooks': [progress_hook],
        'overwrites': True,
        'paths': {
            'home': path
        }
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download(url)
            if url in filename.keys():
                return filename[url]
    except Exception as e:
        raise ValueError(e)