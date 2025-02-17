import shlex
import subprocess


def convert_gif() -> str:
    command = f'ffmpeg -y -i temp/video.mp4 -vf "scale=-1:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" temp/animation.gif'
    ffmpeg_cmd = subprocess.run(
        shlex.split(command),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=False
    )

    return 'temp/animation.gif'