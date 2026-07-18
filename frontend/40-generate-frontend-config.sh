#!/bin/sh
# Runs automatically at container start (nginx:alpine sources every
# executable script in /docker-entrypoint.d/ in alphanumeric order).
# Generates /usr/share/nginx/html/config.js from config.template.js,
# substituting the API_BASE_URL env var so the frontend JS can read it
# as window.APP_CONFIG.apiBaseUrl without a rebuild.
set -eu

: "${API_BASE_URL:=}"

envsubst '${API_BASE_URL}' \
  < /etc/nginx/config.template.js \
  > /usr/share/nginx/html/config.js

echo "40-generate-frontend-config.sh: wrote config.js (API_BASE_URL='${API_BASE_URL}')"
