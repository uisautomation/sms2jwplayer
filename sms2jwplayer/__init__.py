"""
Tool to support bulk import of University of Cambridge SMS into JWPlayer.

Usage:
    sms2jwplayer (-h | --help)
    sms2jwplayer genmrss [options] --base=URL [--strip-leading=N]
        <csv> [<outfile>]

Options:
    -h, --help          Show a brief usage summary.
    -v, --verbose       Increase verbosity.

    <csv>               CSV export from SMS.
    <outfile>           Output file. If omitted, use stdout.

    --base=URL          Base URL to use for links in MRSS feed.
    --strip-leading=N   Number of leading components of filename path to strip
                        from filenames in the CSV. [default: 1]

Sub commands:

    genmrss             Generate an MRSS feed for the export.

"""
import logging

import docopt


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(level=logging.INFO if opts['--verbose'] else logging.WARN)
    if opts['genmrss']:
        from . import genmrss
        genmrss.main(opts)
