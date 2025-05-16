from logging import basicConfig, INFO
from sys import stdout
from yuribot.main import main

def entry():
    basicConfig(level=INFO, stream=stdout)
    main()

if __name__ == '__main__':
    entry()
