#-------------------------------------------------------------------------------
# Imports 
#-------------------------------------------------------------------------------

from twisted.internet import reactor

#-------------------------------------------------------------------------------
# HlsController 
#-------------------------------------------------------------------------------

class HlsController:

    def __init__(self, *, fetcher, player, options):
        self.fetcher = fetcher
        self.player = player
        self.options = options

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
