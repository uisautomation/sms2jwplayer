"""
The genmrss subcommand can be used to generate an `MRSS
<https://en.wikipedia.org/wiki/Media_RSS>`_ feed which is suitable for `bulk
import into jwplayer
<https://support.jwplayer.com/customer/portal/articles/2798456>`_.

"""
import logging
import urllib.parse
import sys

from jinja2 import Environment, select_autoescape

from . import csv as smscsv


LOG = logging.getLogger('genmrss')

#: Jinja2 template for MRSS feed output by ``genmrss``.
MRSS_TEMPLATE_STR = '''
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
    <channel>
        <title>sms2jwplayer generated feed</title>
        <link>http://example.com/index.rss</link>
        <description>SMS Export Feed</description>
{% for item in items %}
        <item>
            <title>{{item.title|sanitise}}</title>
            <link>{{item|url}}</link>
            <description>{{item.description|sanitise}}</description>
            <media:title>{{item.title|sanitise}}</media:title>
            <media:description>{{item.description|sanitise}}</media:description>
            <guid isPermaLink="false">{{item|url}}</guid>
            <media:content url="{{item|url}}" />
        </item>
{% endfor %}
    </channel>
</rss>
'''.strip()


def sanitise(s, max_length=4096):
    """
    Strip odd characters from a string and sanitise the length to maximise
    chances that the feed parse succeeds.

    """
    # Map control characters to empty string
    s = s.translate(dict.fromkeys(range(32)))

    # Truncate
    s = s[:max_length]
    return s


def main(opts):
    """
    Implementation of the ``sms2jwplayer genmrss`` subcommand. *opts* is an
    options dictionary as returned by :py:func:`docopt.docopt`.

    """
    with open(opts['<csv>']) as f:
        items = smscsv.load(f)
    LOG.info('Loaded %s item(s)', len(items))

    def url(item):
        """Return the URL for an item."""
        path_items = item.filename.strip('/').split('/')
        path_items = path_items[int(opts['--strip-leading']):]
        return urllib.parse.urljoin(opts['--base'] + '/', '/'.join(path_items))

    env = Environment(autoescape=select_autoescape(
        enabled_extensions=['html', 'xml'],
        default_for_string=True
    ))
    env.filters.update({'url': url, 'sanitise': sanitise})

    feed_content = env.from_string(MRSS_TEMPLATE_STR).render(
        items=items
    )
    if opts['<outfile>'] is None:
        sys.stdout.write(feed_content)
    else:
        with open(opts['<outfile>'], 'w') as f:
            f.write(feed_content)
