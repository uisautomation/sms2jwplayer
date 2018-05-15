#!/usr/bin/env bash
# Output SMS collection data directly from SMS database.
#
# Usage:
#   export_sms_collection_csv.sh <sms-host> [<csv>]
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
    echo "usage: export_sms_collection_csv.sh <sms-host> [<csv>]" >&2
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
"${SMS_SSH}" "$HOST" psql sms sms >sms_collection_export.csv <<EOL
COPY (
    SELECT
        id AS collection_id,
        name as title,
        description,
        website_url,
        creator,
        instid,
        groupid,
        image_id,
        acl,
        created,
        last_updated,
        updated_by,
        (
            SELECT array_to_string(array_agg(om.id), ',')
            FROM (
                SELECT id
                FROM sms_media m
                WHERE collection_id = sms_collection.id
                ORDER BY id
            ) om
        ) media_ids
    FROM sms_collection
    ORDER BY id
) TO STDOUT DELIMITER ',' CSV HEADER;
EOL
# the media_ids must be ordered - hence the additional sub-select

if [ ! -z "$CSV" ]; then
    echo "-- Writing export CSV to ${CSV}"
    mv "${tmpdir}/sms_collection_export.csv" "$CSV"
fi

msg "-- Deleting workspace ${tmpdir}"
rm -r "${tmpdir}"
