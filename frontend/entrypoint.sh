#!/bin/sh
# Write runtime env config so the API key doesn't need to be baked into the build.
# ADMIN_API_KEY is injected by Coolify (or any other host) as a runtime env var.
cat > /usr/share/nginx/html/env-config.js <<EOF
window.__ADMIN_API_KEY__ = '${ADMIN_API_KEY:-}';
EOF
exec nginx -g 'daemon off;'
