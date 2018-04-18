"""
Tool to support bulk import of University of Cambridge SMS into JWPlayer.

Usage:
    sms2jwplayer (-h | --help)
    sms2jwplayer genmrss [--verbose] --base=URL --base-image-url=URL [--strip-leading=N]
        [--output=FILE] [--limit=NUMBER] [--offset=NUMBER] <csv>
    sms2jwplayer fetch [--verbose] [--base-name=NAME]
    sms2jwplayer genupdatejob [--verbose] [--strip-leading=N]
        [--output=FILE] --base=URL --base-image-url=URL <csv> <metadata>...
    sms2jwplayer applyupdatejob [--verbose] [--log-file=FILE] [<update>]
    sms2jwplayer analytics [--output=FILE] [--verbose] <date>
    sms2jwplayer tidy [--output=FILE] [--verbose] <metadata>...

Options:
    -h, --help          Show a brief usage summary.
    -v, --verbose       Increase verbosity.

    <csv>               CSV export from SMS.
    <metadata>          JSON file containing video list result as returned by jwplayer /videos/list
                        endpoint.
    <update>            JSON file specifying update jobs as returned from genupdatejob. If omitted,
                        use stdin.

    <date>              Date in YYYY-MM-DD format.

    --output=FILE       Output file. If omitted, use stdout.

    --base=URL          Base URL to use for links in MRSS feed.
    --base-image-url=URL          Base URL to use for thumbnail images in MRSS feed.
    --strip-leading=N   Number of leading components of filename path to strip
                        from filenames in the CSV. [default: 1]

    --base-name=NAME    Base of filename used to save results to.
                        [default: videos_]

    --limit=NUMBER      Limit feed to last NUMBER most updated videos. [default: 1000]
    --offset=NUMBER     Start feed at NUMBER-th most recently updated. This index is 0-based
                        [default: 0]

Sub commands:

    genmrss             Generate an MRSS feed for the export.
    fetch               Fetch details on all videos in jwplayer.
    genupdatejob        Generate list of missing metadata for each video key.
    applyupdatejob      Use JWPlatform API to update videos based on a job description file.
    analytics           Generate SMS analytics for a given day.
    tidy                Generate an update job which tidies the jwplayer database.

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
    elif opts['analytics']:
        from . import analytics
        analytics.main(opts)
    elif opts['tidy']:
        from . import tidy
        tidy.main(opts)
