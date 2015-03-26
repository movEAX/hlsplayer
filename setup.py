import sys
from setuptools import setup, find_packages

try:
    import gi
    gi.require_version('1.0')
except:
    print("Install gst-python first, please")
    sys.exit(1)

setup(
    name="HLSPlayer",
    version="0.2",

    install_requires=['m3u8'],
    setup_requires=['nose>=1.0'],

    packages=find_packages(),
    entry_points={
        'console_scripts': [ 'hls-player = hls.player:main' ]
    },

    author="Marc-Andre Lureau",
    author_email="marcandre.lureau@gmail.com",
    description="HTTP Live Streaming player",
    license="GNU GPL",
    keywords="hls video streaming live",
)
