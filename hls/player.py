#!/usr/bin/env python
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Copyright (C) 2009-2010 Fluendo, S.L. (www.fluendo.com).
# Copyright (C) 2009-2010 Marc-Andre Lureau <marcandre.lureau@gmail.com>
# Copyright (C) 2010 Zaheer Abbas Merali  <zaheerabbas at merali dot org>
# Copyright (C) 2010 Andoni Morales Alastruey <ylatuya@gmail.com>

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
import optparse
import logging
from urllib.parse import urlsplit

# 3rdparty
from gi.repository import Gst, Gdk, Gtk, GObject
GObject.threads_init()

from twisted.internet import gtk2reactor
gtk2reactor.install()
from twisted.internet import reactor

# own
from .fetcher import HlsFetcher
from .m3u8 import M3U8

#-------------------------------------------------------------------------------
# HlsController 
#-------------------------------------------------------------------------------

class HlsController:

    def __init__(self, fetcher=None):
        self.fetcher = fetcher
        self.player = None
        self._player_sequence = None
        self._n_segments_keep = None

    def set_player(self, player):
        self.player = player
        if player:
            self.player.connect_about_to_finish(self.on_player_about_to_finish)
            self._n_segments_keep = self.fetcher.n_segments_keep
            self.fetcher.n_segments_keep = -1

    def _start(self, first_file):
        (path, l, f) = first_file
        self._player_sequence = f['sequence']
        if self.player:
            self.player.set_uri(path)
            self.player.play()

    def start(self):
        d = self.fetcher.start()
        d.addCallback(self._start)

    def _set_next_uri(self):
        # keep only the past three segments
        if self._n_segments_keep != -1:
            self.fetcher.delete_cache(lambda x:
                x <= self._player_sequence - self._n_segments_keep)
        self._player_sequence += 1
        d = self.fetcher.get_file(self._player_sequence)
        d.addCallback(self.player.set_uri)

    def on_player_about_to_finish(self):
        reactor.callFromThread(self._set_next_uri)

#-------------------------------------------------------------------------------
# GstPlayer
#-------------------------------------------------------------------------------

class GstPlayer:

    def __init__(self, display=True):
        if display:
            self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
            self.window.set_title("Video-Player")
            self.window.set_default_size(500, 400)
            self.window.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            self.window.connect('delete-event', lambda _: reactor.stop())
            self.movie_window = Gtk.DrawingArea()
            self.window.add(self.movie_window)
            self.window.show_all()

        self.player = Gst.Pipeline("player")
        self.appsrc = Gst.ElementFactory.make("appsrc", "source")
        self.appsrc.connect("enough-data", self.on_enough_data)
        self.appsrc.connect("need-data", self.on_need_data)
        self.appsrc.set_property("max-bytes", 10000)
        
        if display:
            self.decodebin = Gst.ElementFactory.make("decodebin2", "decodebin")
            self.decodebin.connect("new-decoded-pad", self.on_decoded_pad)
            self.player.add(self.appsrc, self.decodebin)
            link_many(self.appsrc, self.decodebin)
        else:
            sink = Gst.ElementFactory.make("filesink", "filesink")
            sink.set_property("location", "/tmp/hls-player.ts")
            self.player.add(self.appsrc, sink)
            link_many(self.appsrc, sink)
            
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)
        self._playing = False
        self._need_data = False
        self._cb = None

    def need_data(self):
        return self._need_data

    def play(self):
        self.player.set_state(Gst.State.PLAYING)
        self._playing = True

    def stop(self):
        self.player.set_state(Gst.State.NULL)
        self._playing = False

    def set_uri(self, filepath):
        logging.debug("Pushing %r to appsrc" % filepath)
        # FIXME: BIG hack to reduce the initial starting time...
        queue0 = self.decodebin.get_by_name("multiqueue0")
        if queue0:
            queue0.set_property("max-size-bytes", 100000)
        f = open(filepath)
        self.appsrc.emit('push-buffer', Gst.Buffer(f.read()))

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.player.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.ERROR:
            self.player.set_state(Gst.State.NULL)
            err, debug = message.parse_error()
            logging.error("Error: %s" % err, debug)
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.player:
                o, n, p = message.parse_state_changed()

    def on_sync_message(self, bus, message):
        logging.debug("GstMessage: %r" % (message,))
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            Gdk.threads_enter()
            Gdk.Display.get_default().sync()
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_xwindow_id(self.movie_window.window.xid)
            Gdk.threads_leave()

    def on_decoded_pad(self, decodebin, pad, more_pad):
        c = pad.get_caps().to_string()
        if "video" in c:
            q1 = Gst.ElementFactory.make("queue", "vqueue")
            q1.props.max_size_buffers = 0
            q1.props.max_size_time = 0
            colorspace = Gst.ElementFactory.make("ffmpegcolorspace", "colorspace")
            videosink = Gst.ElementFactory.make("xvimagesink", "videosink")
            self.player.add(q1, colorspace, videosink)
            Gst.Element.link(q1, colorspace)
            Gst.Element.link(colorspace, videosink)
            for e in [q1, colorspace, videosink]:
                e.set_state(Gst.State.PLAYING)
            sink_pad = q1.get_pad("sink")
            pad.link(sink_pad)
        elif "audio" in c:
            q2 = Gst.ElementFactory.make("queue", "aqueue")
            q2.props.max_size_buffers = 0
            q2.props.max_size_time = 0
            audioconv = Gst.ElementFactory.make("audioconvert", "audioconv")
            audioresample =  Gst.ElementFactory.make("audioresample", "ar")
            audiosink = Gst.ElementFactory.make("autoaudiosink", "audiosink")
            self.player.add(q2, audioconv, audioresample, audiosink)
            link_many(q2, audioconv, audioresample, audiosink)
            for e in [q2, audioconv, audioresample, audiosink]:
                e.set_state(Gst.State.PLAYING)
            sink_pad = q2.get_pad("sink")
            pad.link(sink_pad)

    def on_enough_data(self):
        logging.info("Player is full up!");
        self._need_data = False;

    def on_need_data(self, src, length):
        self._need_data = True;
        self._on_about_to_finish()

    def _on_about_to_finish(self, p=None):
        if self._cb:
            self._cb()

    def connect_about_to_finish(self, cb):
        self._cb = cb


# TODO: find more appropriate solution
def link_many(*queues):
    def link_inner(e1, e2):
        Gst.Element.link(e1, e2)
        return e2
        
    reduce(link_inner, queues)


def main():
    Gdk.threads_init()
    parser = optparse.OptionParser(usage='%prog [options] url...', version="%prog")

    parser.add_option('-v', '--verbose', 
        action="store_true",
        dest='verbose', 
        default=False,
        help='print some debugging (default: %default)')
        
    parser.add_option('-b', '--bitrate', 
        action="store",
        dest='bitrate', 
        default=200000, 
        type="int",
        help='desired bitrate (default: %default)')
        
    parser.add_option('-k', '--keep', 
        action="store",
        dest='keep',
        default=3, 
        type="int",
        help='number of segments ot keep (default: %default, -1: unlimited)')
        
    parser.add_option('-r', '--referer', 
        action="store", 
        metavar="URL",
        dest='referer', 
        default=None,
        help='Sends the "Referer Page" information with URL')
        
    parser.add_option('-D', '--no-display', 
        action="store_true",
        dest='nodisplay', 
        default=False,
        help='display no video (default: %default)')
        
    parser.add_option('-s', '--save', 
        action="store_true",
        dest='save', 
        default=False,
        help='save instead of watch (saves to /tmp/hls-player.ts)')
        
    parser.add_option('-p', '--path', 
        action="store", 
        metavar="PATH",
        dest='path', 
        default=None,
        help='download files to PATH')
        
    parser.add_option('-n', '--number', 
        action="store",
        dest='n', 
        default=1, 
        type="int",
        help='number of player to start (default: %default)')

    options, args = parser.parse_args()

    if len(args) == 0:
        parser.print_help()
        sys.exit(1)

    if options.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%d %b %Y %H:%M:%S')

    for url in args:
        for l in range(options.n):
            if urlsplit(url).scheme == '':
                url = "http://" + url

            c = HlsController(HlsFetcher(url, options))
            if not options.nodisplay:
                p = GstPlayer(display = not options.save)
                c.set_player(p)

            c.start()

    reactor.run()

if __name__ == '__main__':
    sys.exit(main())