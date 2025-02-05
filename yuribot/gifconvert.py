import shlex
import subprocess


def convert_gif() -> str:
    command = f'ffmpeg -y -i temp/video.mp4 -filter_complex scale=320:-1 -f gif temp/animation.gif'
    ffmpeg_cmd = subprocess.run(
        shlex.split(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=False
    )

    return 'temp/animation.gif'