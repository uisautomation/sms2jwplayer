#!/usr/bin/env bash
# Output SMS media data directly from SMS database.
#
# Usage:
#   export_sms_csv.sh <sms-host> [<csv>]
#
# Options:
#
#   <sms-host>    Hostname of SMS box to log into. (E.g. root@example.com)
#   <csv>         If specified, write CSV to this file.
#
# Environment variables:
#
#   SMS_SSH  SSH client to use instead of "ssh".
#
set -e

HOST=$1
CSV=$2

if [ -z "${HOST}" ]; then
    echo "usage: export_sms_csv.sh <sms-host> [<csv>]" >&2
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
        m.publisher AS publisher,
        m.copyright AS copyright,
        m.language AS language,
        m.keywords AS keywords,
        m.visibility AS visibility,
        coalesce(m.acl, sms_collection.acl) AS acl,
        m.screencast AS screencast,
        coalesce(m.image_id, sms_collection.image_id) AS image_id,
        md5(i.data) AS image_md5,
        m.featured AS featured,
        m.branding AS branding,
        m.last_updated AS last_updated_at,
        m.updated_by AS updated_by,
        m.downloadable AS downloadable,
        m.withdrawn AS withdrawn,
        sms_clip.quality AS quality
    FROM
        sms_media m
        JOIN sms_clip ON sms_clip.media_id = m.id
        JOIN sms_collection ON sms_collection.id = m.collection_id
        LEFT OUTER JOIN sms_image i on i.id = coalesce(m.image_id, sms_collection.image_id)
    WHERE NOT EXISTS (SELECT * FROM corrupted_clips WHERE corrupted_clips.clip_id = sms_clip.id)
    ORDER BY
        m.id
) TO STDOUT DELIMITER ',' CSV HEADER;
EOL

if [ ! -z "$CSV" ]; then
    echo "-- Writing export CSV to ${CSV}"
    mv "${tmpdir}/sms_export.csv" "$CSV"
fi

msg "-- Deleting workspace ${tmpdir}"
rm -r "${tmpdir}"
