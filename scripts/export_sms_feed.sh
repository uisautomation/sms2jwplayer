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
		m.id AS media_id,
		sms_clip.id AS clip_id,
		sms_clip.format AS format,
		sms_clip.filename AS filename,
		m.created AS created_at,
		m.title AS title,
		m.description AS description,
		m.collection_id AS collection_id,
		sms_collection.instid AS instid,
		m.aspect_ratio AS aspect_ratio,
		m.creator AS creator,
		m.dspace AS in_dspace,
		m.publisher AS publisher,
		m.copyright AS copyright,
		m.language AS language,
		m.keywords AS keywords,
		m.visibility AS visibility,
		m.acl AS acl,
		m.screencast AS screencast,
		m.image_id AS image_id,
		m.dspace_path AS dspace_path,
		m.featured AS featured,
		m.branding AS branding,
		m.last_updated AS last_updated_at,
		m.updated_by AS updated_by,
		m.downloadable AS downloadable,
		m.withdrawn AS withdrawn,
		m.abstract AS abstract,
		m.priority AS priority
	FROM
		sms_media m
		JOIN sms_clip ON m.id = sms_clip.media_id
		JOIN sms_collection ON sms_collection.id = m.collection_id
	WHERE
		( sms_clip.format = 'archive-h264' OR sms_clip.format = 'audio' )
		AND sms_clip.quality = 'high'
		AND sms_clip.filename IS NOT NULL
	ORDER BY
		m.id
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
