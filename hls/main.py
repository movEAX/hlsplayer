#------------------------------------------------------------------------------
# Imports 
#------------------------------------------------------------------------------

from .player import GstPlayer
from .controller import HlsController
from .fetcher import HlsFetcher

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
            level=logging.INFO,
            format='%(asctime)s %(levelname)-8s %(message)s',
            datefmt='%d %b %Y %H:%M:%S')

    url = args[0]
    url = url.startswith("http") and url or ('http://' + url) 

    player = GstPlayer()
    fetcher = HlsFetcher(url, options)
    controller = HlsController(
        fetcher=fetcher,
        player=player)
    controller.start()

    loop.run_forever()

if __name__ == '__main__':
    sys.exit(main())
