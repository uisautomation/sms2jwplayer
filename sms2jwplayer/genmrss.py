"""
The genmrss subcommand can be used to generate an `MRSS
<https://en.wikipedia.org/wiki/Media_RSS>`_ feed which is suitable for `bulk
import into jwplayer
<https://support.jwplayer.com/customer/portal/articles/2798456>`_.

"""
import base64
import hashlib
import logging
import urllib.parse
import sys

from jinja2 import Environment, select_autoescape

from . import csv as smscsv


LOG = logging.getLogger('genmrss')

MRSS_TEMPLATE_STR = '''
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
    <channel>
        <title>sms2jwplayer generated feed</title>
        <link>http://example.com/index.rss</link>
        <description>SMS Export Feed</description>
        {% for item in items %}<item>
            <title>{{item.title}}</title>
            <link>{{item|url}}</link>
            <description>{{item.description}}</description>
            <media:title>{{item.title}}</media:title>
            <media:description>{{item.description}}</media:description>
            <guid isPermaLink="false">{{item|guid}}</guid>
            <media:content url="{{item|url}}" isDefault="true">
            </media:content>
        </item>{% endfor %}
    </channel>
</rss>
'''.strip()


def guid(item):
    """Convert a :py:class:`~sms2jwplayer.csv.MediaItem` into a globally unique
    string formed by base 64 encoding the SHA2 of the concatenation of the media
    id as a decimal string, a literal colon (":") and the clip id as a decimal
    string.

    .. note::

        This is *not* intended to be cryptographically secure!

    """
    h = hashlib.sha256()
    h.update(str(item.media_id).encode('utf8'))
    h.update(b':')
    h.update(str(item.clip_id).encode('utf8'))
    return base64.b64encode(h.digest()).decode('utf8').strip('=')


def main(opts):
    with open(opts['<csv>']) as f:
        items = [m for m in smscsv.load(f) if m.format == 'archive-h264']
    items = items[::100]
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
    env.filters.update({'guid': guid, 'url': url})

    feed_content = env.from_string(MRSS_TEMPLATE_STR).render(
        items=items
    )
    if opts['<outfile>'] is None:
        sys.stdout.write(feed_content)
    else:
        with open(opts['<outfile>'], 'w') as f:
            f.write(feed_content)
