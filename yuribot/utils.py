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


def download_link(url: str) -> str:
    os.makedirs(name='temp', exist_ok=True)
    ydl_opts = {
        'progress_hooks': [progress_hook],
        'overwrites': True,
        'paths': {
            'home': 'temp'
        }
    }
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            size = info.get('filesize_approx')
            if type(size) != int:
                raise TypeError(f'yt-dlp: Invalid file size received, try submitting the video again')
            if size > 512 * (2**20):
                raise IOError(f'yt-dlp: Video too big: {round(size / 2**20, 2)} MiB (Max 512 MiB)')
            ydl.download(url)
            if url in filename.keys():
                return filename[url]
            else:
                raise ValueError('yt-dlp: No videos found')
    except Exception as e:
        raise ValueError(e)