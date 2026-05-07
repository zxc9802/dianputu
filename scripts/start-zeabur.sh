#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-3000}"

/app/.venv/bin/uvicorn app.main:app --app-dir /app/backend --host 127.0.0.1 --port 8000 &
backend_pid="$!"

cd /app/frontend
npm run start -- -p 3001 &
frontend_pid="$!"

cat >/tmp/dianputu-nginx.conf <<EOF
events {}

http {
  client_max_body_size 50m;
  proxy_read_timeout 600s;
  proxy_send_timeout 600s;
  proxy_connect_timeout 60s;

  server {
    listen ${PORT};

    location /api/ {
      proxy_pass http://127.0.0.1:8000/api/;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Real-IP \$remote_addr;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
      proxy_pass http://127.0.0.1:3001;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Real-IP \$remote_addr;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto \$scheme;
    }
  }
}
EOF

cleanup() {
  kill "$backend_pid" 2>/dev/null || true
  kill "$frontend_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

nginx -c /tmp/dianputu-nginx.conf -g "daemon off;"
