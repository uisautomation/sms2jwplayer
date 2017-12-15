#!/usr/bin/env bash
# Output SMS feed URL directly from SMS database.
#
# Usage:
#	export_sms_feed.sh <sms-host> <base-url> <feed> [<csv>]
#
# Options:
#
#	<sms-host>    Hostname of SMS box to log into. (E.g. root@example.com)
#	<base-url>    Base URL of SMS archive endpoint.
#	              (E.g. http://user:pass@download.example.com:1234/archive)
#	<file>        File to write feed to or "-" for stdout
#	<csv>         If specified, write CSV to this file.
#
# Environment variables:
#
#	SMS_SSH       SSH client to use instead of "ssh".
set -e

HOST=$1
BASE=$2
FEED=$3
CSV=$4

if [ -z "${FEED}" ]; then
	echo "usage: export_sms_feed <sms-host> <base-url> <feed> [<csv>]" >&2
	exit 1
fi

SMS_SSH=${SMS_SSH:-ssh}

function msg() {
	echo "$*" >&2
}

# Create a temporary directory to work in
tmpdir=$(mktemp -d "${TMPDIR:-/tmp/}$(basename $0).XXXXXXXXXXXX")
msg "-- Working in ${tmpdir}"

pushd "${tmpdir}" >/dev/null

msg "-- Generating SMS export CSV"
"${SMS_SSH}" "$HOST" psql sms sms >sms_export.csv <<EOL
COPY (
	SELECT
		sms_media.id AS media_id,
		sms_clip.id AS clip_id,
		sms_clip.format AS format,
		sms_clip.filename AS filename,
		sms_media.created AS created_at,
		sms_media.title AS title,
		sms_media.description AS description
	FROM
		sms_media
		JOIN sms_clip ON sms_media.id = sms_clip.media_id
	WHERE
		( sms_clip.format = 'archive-h264' OR sms_clip.format = 'audio' )
		AND sms_clip.quality = 'high'
		AND sms_clip.filename IS NOT NULL
	ORDER BY
		sms_media.id
) TO STDOUT DELIMITER ',' CSV HEADER;
EOL

msg "-- Generating feed"
sms2jwplayer -v genmrss --base="${BASE}" --output=feed.rss sms_export.csv

popd >/dev/null
msg "-- Writing feed to '${FEED}'"
if [ "${FEED}" == "-" ]; then
	cat "${tmpdir}/feed.rss"
else
	mv "${tmpdir}/feed.rss" "${FEED}"
fi

if [ ! -z "$CSV" ]; then
	echo "-- Writing export CSV to ${CSV}"
	mv "${tmpdir}/sms_export.csv" "$CSV"
fi

msg "-- Deleting workspace ${tmpdir}"
rm -r "${tmpdir}"
