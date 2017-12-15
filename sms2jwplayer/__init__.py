"""
Tool to support bulk import of University of Cambridge SMS into JWPlayer.

Usage:
    sms2jwplayer (-h | --help)
    sms2jwplayer genmrss [--verbose] --base=URL [--strip-leading=N]
        [--output=FILE] <csv>
    sms2jwplayer fetch [--verbose] [--base-name=NAME]
    sms2jwplayer genupdatejob [--verbose] [--strip-leading=N]
        [--output=FILE] <csv> <metadata>...
    sms2jwplayer applyupdatejob [--verbose] [<update>]

Options:
    -h, --help          Show a brief usage summary.
    -v, --verbose       Increase verbosity.

    <csv>               CSV export from SMS.
    <metadata>          JSON file containing video list result as returned by jwplayer /videos/list
                        endpoint.
    <update>            JSON file specifying update jobs as returned from genupdatejob. If omitted,
                        use stdin.

    --output=FILE       Output file. If omitted, use stdout.

    --base=URL          Base URL to use for links in MRSS feed.
    --strip-leading=N   Number of leading components of filename path to strip
                        from filenames in the CSV. [default: 1]

    --base-name=NAME    Base of filename used to save results to.
                        [default: videos_]

Sub commands:

    genmrss             Generate an MRSS feed for the export.
    fetch               Fetch details on all videos in jwplayer.
    genupdatejob        Generate list of missing metadata for each video key.

"""
import logging

import docopt


def main():
    opts = docopt.docopt(__doc__)
    logging.basicConfig(level=logging.INFO if opts['--verbose'] else logging.WARN)
    if opts['genmrss']:
        from . import genmrss
        genmrss.main(opts)
    elif opts['fetch']:
        from . import fetch
        fetch.main(opts)
    elif opts['genupdatejob']:
        from . import genupdatejob
        genupdatejob.main(opts)
    elif opts['applyupdatejob']:
        from . import applyupdatejob
        applyupdatejob.main(opts)
