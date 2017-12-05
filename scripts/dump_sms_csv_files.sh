#!/usr/bin/env bash
set -xe

psql sms sms >sms_export.csv <<EOL
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
