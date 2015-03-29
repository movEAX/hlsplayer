# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Copyright (C) 2009-2010 Fluendo, S.L. (www.fluendo.com).
# Copyright (C) 2009-2010 Marc-Andre Lureau <marcandre.lureau@gmail.com>

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE" in the source distribution for more information.

#------------------------------------------------------------------------------
# Imports 
#------------------------------------------------------------------------------

# Stdlib
import logging
import os, os.path
import tempfile
import asyncio
from datetime import datetime
from urllib.parse import urlparse

# 3rdparty
import m3u8
import requests
from m3u8.model import M3U8

#------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------

BITRATE_CRITERIA = 1000
RELOAD_TIMEOUT = 7

#------------------------------------------------------------------------------
# Fetcher implementation
#------------------------------------------------------------------------------

count = 0

@asyncio.coroutine
def on_playlist_downloaded(pl: M3U8):
    if pl.playlists:
        logging.info('Loaded variant.m3u8')
        url = pl.playlists[0].absolute_uri
        asyncio.async(reload_playlist(url))
    elif pl.files:
        logging.info('Loaded playlist.m3u8 with files count: %d', len(pl.files))
        utc_timestamp = str(datetime.utcnow().timestamp())
        url_tpl = '{base}/playlist.m3u8?utcstart={utc}'
        url = url_tpl.format(
            base=pl.base_uri,
            utc=utc_timestamp)
        asyncio.async(reload_playlist(url, timeout=RELOAD_TIMEOUT))
        [asyncio.async(download_and_save(url)) for url in pl.files]
    else:
        logging.error('Playlist is empty: \n%r', pl.dumps())
        raise

@asyncio.coroutine
def reload_playlist(uri, *, timeout=None):
    logging.info('Reload playlist %r with timeout %r', uri, timeout)
    if timeout:
        yield from asyncio.sleep(timeout)
    pl = m3u8.load(uri)
    asyncio.async(on_playlist_downloaded(pl))


@asyncio.coroutine
def download_and_save(uri):
    global count
    logging.info('Donwload ts file %r', uri)
    response = requests.get(uri)
    if response.status_code == 200:
        filename = uri.rsplit('/', 1)[1]
        with open('/tmp/video{:05d}.ts'.format(count), 'wb') as fh:
            fh.write(response.content)
        count += 1

def start(url):
    asyncio.async(reload_playlist(url))
