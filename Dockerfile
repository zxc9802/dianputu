FROM node:22-bookworm

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends nginx python3 python3-pip python3-venv \
  && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN python3 -m venv /app/.venv \
  && /app/.venv/bin/pip install --no-cache-dir -r backend/requirements.txt

COPY frontend/package*.json frontend/
RUN cd frontend && npm ci

COPY . .

ENV NEXT_PUBLIC_API_BASE_URL=""
RUN cd frontend && npm run build

EXPOSE 3000

CMD ["/bin/bash", "/app/scripts/start-zeabur.sh"]
