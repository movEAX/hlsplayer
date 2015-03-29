#------------------------------------------------------------------------------
# Imports 
#------------------------------------------------------------------------------

import sys
import asyncio
import optparse
import logging
from concurrent.futures import ProcessPoolExecutor

from gi.repository import Gtk

from .player import GstPlayer
from .fetcher import start as start_fetch

#------------------------------------------------------------------------------
# Entry point
#------------------------------------------------------------------------------

def main():
    parser = optparse.OptionParser(
        usage='%prog [options] url...', 
        version="%prog")

    parser.add_option('-v', '--verbose', 
        action="store_true",
        dest='verbose', 
        default=False,
        help='print some debugging (default: %default)')
        
    options, args = parser.parse_args()

    if len(args) == 0:
        parser.print_help()
        sys.exit(1)

    if options.verbose:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%d %b %Y %H:%M:%S')

    url = args[0]
    url = url.startswith("http") and url or ('http://' + url) 

    start_fetch(url)
    loop = asyncio.get_event_loop()
    executor = ProcessPoolExecutor(1)
    asyncio.async(loop.run_in_executor(executor, _run_player))

    loop.run_forever()

def _run_player():
    player = GstPlayer()
    player.play()
    Gtk.main()

if __name__ == '__main__':
    sys.exit(main())
