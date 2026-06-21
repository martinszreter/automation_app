#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "==> Checking Docker installation..."
if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
  echo "Docker installed."
else
  echo "Docker already installed."
fi

if ! docker compose version &>/dev/null; then
  echo "ERROR: 'docker compose' plugin not available. Please install docker-compose-plugin."
  exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in production values."
  exit 1
fi

echo "==> Building and starting services..."
docker compose -f docker-compose.prod.yml up --build -d

echo "==> Waiting for database to be ready..."
docker compose -f docker-compose.prod.yml exec -T db sh -c \
  'until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do sleep 1; done'

echo "==> Running database migrations..."
docker compose -f docker-compose.prod.yml exec -T app alembic upgrade head

echo "==> Deployment complete. App is running on port 80."
docker compose -f docker-compose.prod.yml ps
