from logging import basicConfig, INFO
from sys import stdout
from yuribot.main import main

if __name__ == '__main__':
    basicConfig(level=INFO, stream=stdout)
    main()