#!/usr/bin/env bash
set -xe
cd $HOME/sms2jwplayer
source venv/bin/activate

# ~/jwplatform-secrets.sh contains:
#
# export JWPLAYER_API_KEY="<redacted>"
# export JWPLAYER_API_SECRET="<redacted>"
# export JWPLAYER_API_ANALYTICS_SECRET="<redacted>"
source $HOME/jwplatform-secrets.sh

# Where to store export CSV
csv_output=$HOME/sms_export.csv

# Which directory to put video metadata in
metadata_dir=$HOME/jwplayer-meta

# Where to write updatejob to
update_job=$HOME/update_job.json

# Where stats go and who owns them
stats_dir=~sms/stats
stats_owner=sms

for offset in 0 1000 2000 3000 4000; do
        EXTRA_GENMRSS_OPTS="--limit 1000 --offset ${offset}" ./scripts/export_sms_feed.sh sms-node2.sms.cam.ac.uk \
                http://downloads.sms.cam.ac.uk:8074/2sYshTw1RVKkKxIdpMU8VwqgLRsdFaya/sms-archive02/ \
                https://sms.cam.ac.uk/image/ \
                /sms-archive02/feed-${offset}.rss "${csv_output}"
done
mv /sms-archive02/feed-0.rss /sms-archive02/feed.rss

# Temp directory for new metadata
new_metadata_dir=$(mktemp -d "$metadata_dir.XXXXXXX")

# Fetch metadata
echo "-- Fetching new metadata into $new_metadata_dir"
sms2jwplayer fetch --verbose --base-name="$new_metadata_dir/metadata_"

# Ensure metadata dir exists and is empty
if [ -d "$metadata_dir" ]; then
        echo "-- Removing existing metadata directory"
        rm -r "$metadata_dir"
fi

# Copy metadata over
echo "-- Renaming $new_metadata_dir to $metadata_dir"
mv "$new_metadata_dir" "$metadata_dir"

# Determine what metadata updates are required
echo "-- Determining metadata updates"
sms2jwplayer genupdatejob --verbose --output="${update_job}" "${csv_output}" "${metadata_dir}"/*.json

# Apply metadata updates
echo "-- Updating metadata"
sms2jwplayer applyupdatejob --verbose "${update_job}"

# Get stats for yesterday
update_date="yesterday"
echo "-- Updating view stats for ${update_date}"
if [ ! -d "${stats_dir}" ]; then
        mkdir -p "${stats_dir}"
fi
analytics_output=${stats_dir}/stats-$(date --date="${update_date}" +%Y%m%d).csv
sms2jwplayer analytics --verbose "--output=${analytics_output}" "$(date --date="${update_date}" -I)"

# ensure ownership
chown -R "${stats_owner}" "${stats_dir}"

# Copy stats to webapp VM.
scp ${analytics_output} root@daffy.sms.csx.cam.ac.uk:~sms/stats/
