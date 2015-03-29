#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Copyright (C) 2009-2010 Fluendo, S.L. (www.fluendo.com).
# Copyright (C) 2009-2010 Marc-Andre Lureau <marcandre.lureau@gmail.com>
# Copyright (C) 2010 Zaheer Abbas Merali  <zaheerabbas at merali dot org>
# Copyright (C) 2010 Andoni Morales Alastruey <ylatuya@gmail.com>
# Copyright (C) 2015 Andrey Torpunov <gtors.potato+hls@gmail.com>
#
# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE" in the source distribution for more information.

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------

# Stdlib
import sys
import asyncio
import optparse
import logging
from urllib.parse import urlsplit
from functools import reduce

# 3rdparty
from gi.repository import Gst, Gdk, Gtk, GObject

#------------------------------------------------------------------------------
# 3rdparty components initialization
#------------------------------------------------------------------------------

#>This import needed for properly work of `get_xid` method
from gi.repository import GdkX11
#>And this import needed for properly work of `set_window_handle` method
from gi.repository import GstVideo

GObject.threads_init()
Gdk.threads_init()
Gst.init(None)
Gtk.init()

loop = asyncio.get_event_loop()

#------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------

# File pattern for `multifilesrc`
FILE_NAME_PATTERN = 'video%05d.ts'
FILES_LOCATION = '/tmp/' + FILE_NAME_PATTERN

#------------------------------------------------------------------------------
# GstPlayer
#------------------------------------------------------------------------------

class GstPlayer:

    def __init__(self):
        self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        self.window.set_title("Video-Player")
        self.window.set_default_size(500, 400)
        self.window.connect('delete-event', lambda *_: loop.stop())
        self.drawing_area = Gtk.DrawingArea()
        self.window.add(self.drawing_area)
        self.window.show_all()
    
        self.player = Gst.Pipeline("player")
        self.multifilesrc = Gst.ElementFactory.make("multifilesrc", "source")
        self.multifilesrc.set_property('location', FILES_LOCATION)
        
        self.decodebin = Gst.ElementFactory.make("decodebin", "decodebin")
        self.decodebin.connect("pad-added", self.on_decoded_pad)
        self.player.add(self.multifilesrc, self.decodebin)
        Gst.Element.link(self.multifilesrc, self.decodebin)
            
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)
        bus.enable_sync_message_emission()
        bus.connect("sync-message::element", self.on_sync_message)
        
        self._playing = False
        self._sync_video = False
        self._sync_audio = False

    def play(self):
        self.player.set_state(Gst.State.PLAYING)
        self._playing = True

    def stop(self):
        self.player.set_state(Gst.State.NULL)
        self._playing = False

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.stop()
            logging.info('EOS')
        elif t == Gst.MessageType.ERROR:
            self.stop()
            err, debug = message.parse_error()
            logging.error(err)
            self.play()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.player:
                o, n, p = message.parse_state_changed()

    def on_sync_message(self, bus, message):
        logging.debug("GstMessage: %r" % (message,))
        if message.get_structure() is None:
            return
        message_name = message.get_structure().get_name()
        if message_name == "prepare-window-handle":
            vsink = message.src
            vsink.set_property("force-aspect-ratio", True)
            xid = self.drawing_area.get_property('window').get_xid()
            vsink.set_window_handle(xid)

    def on_decoded_pad(self, decodebin, pad):
        logging.debug('%r %r', pad, pad.__dict__)
       
        c = pad.get_current_caps().to_string()
        if "video" in c and not self._sync_video:
            videosink = Gst.ElementFactory.make("xvimagesink", "videosink")
            self.player.add(videosink)
            pad.link(videosink.get_static_pad('sink'))
            videosink.set_state(Gst.State.PLAYING)
            self._sync_video = True
        elif "audio" in c and not self._sync_audio:
            q2 = Gst.ElementFactory.make("queue", "aqueue")
            q2.props.max_size_buffers = 0
            q2.props.max_size_time = 0
            audioconv = Gst.ElementFactory.make("audioconvert", "audioconv")
            audioresample =  Gst.ElementFactory.make("audioresample", "ar")
            audiosink = Gst.ElementFactory.make("autoaudiosink", "audiosink")
            self.player.add(q2, audioconv, audioresample, audiosink)
            Gst.Element.link(q2, audioconv)
            Gst.Element.link(audioconv, audioresample)
            Gst.Element.link(audioresample, audiosink)
            for e in [q2, audioconv, audioresample, audiosink]:
                e.set_state(Gst.State.PLAYING)
            sink_pad = q2.get_static_pad("sink")
            pad.link(sink_pad)
            self._sync_audio = True
