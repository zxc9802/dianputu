#!/usr/bin/env bash
set -euo pipefail

export PORT="${PORT:-3000}"

backend_pid=""
frontend_pid=""
nginx_pid=""

cleanup() {
  for pid in "$nginx_pid" "$backend_pid" "$frontend_pid"; do
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

wait_for_port() {
  local name="$1"
  local port="$2"
  local pid="$3"

  for _ in $(seq 1 60); do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "$name exited before opening port $port" >&2
      wait "$pid" || true
      return 1
    fi

    if (: >"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1; then
      return 0
    fi

    sleep 1
  done

  echo "$name did not open port $port within 60 seconds" >&2
  return 1
}

wait_for_service_exit() {
  while true; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
      local exit_code=0
      wait "$backend_pid" || exit_code="$?"
      echo "backend process exited; shutting down container (exit code: $exit_code)." >&2
      return "$exit_code"
    fi

    if ! kill -0 "$frontend_pid" 2>/dev/null; then
      local exit_code=0
      wait "$frontend_pid" || exit_code="$?"
      echo "frontend process exited; shutting down container (exit code: $exit_code)." >&2
      return "$exit_code"
    fi

    if ! kill -0 "$nginx_pid" 2>/dev/null; then
      local exit_code=0
      wait "$nginx_pid" || exit_code="$?"
      echo "nginx process exited; shutting down container (exit code: $exit_code)." >&2
      return "$exit_code"
    fi

    sleep 1
  done
}

/app/.venv/bin/uvicorn app.main:app --app-dir /app/backend --host 127.0.0.1 --port 8000 &
backend_pid="$!"

cd /app/frontend
npm run start -- -p 3001 &
frontend_pid="$!"

wait_for_port "backend" 8000 "$backend_pid"
wait_for_port "frontend" 3001 "$frontend_pid"

cat >/tmp/dianputu-nginx.conf <<EOF
events {}

http {
  client_max_body_size 50m;
  proxy_read_timeout 600s;
  proxy_send_timeout 600s;
  proxy_connect_timeout 60s;

  server {
    listen ${PORT};

    location = /health {
      proxy_pass http://127.0.0.1:8000/health;
      proxy_http_version 1.1;
      proxy_set_header Host \$host;
      proxy_set_header X-Real-IP \$remote_addr;
      proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto \$scheme;
    }

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

nginx -c /tmp/dianputu-nginx.conf -g "daemon off;" &
nginx_pid="$!"

exit_code=0
wait_for_service_exit || exit_code="$?"
if [[ "$exit_code" -eq 0 ]]; then
  exit_code=1
fi
exit "$exit_code"
