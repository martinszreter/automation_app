# Deploying STARTEND

## Prerequisites

- A fresh Ubuntu 22.04 server (e.g. Hetzner CX22)
- Root or sudo access via SSH

## First-time Setup

### 1. Connect to your server

```bash
ssh root@YOUR_SERVER_IP
```

### 2. Get the code

```bash
apt-get update && apt-get install -y git
git clone https://github.com/martinszreter/automation_app.git /opt/startend
cd /opt/startend
```

### 3. Create the environment file

```bash
cp .env.example .env
nano .env
```

Change at minimum:
- `POSTGRES_PASSWORD` — use a strong random password
- Update the password inside `DATABASE_URL` to match

### 4. Deploy

```bash
bash deploy.sh
```

The app is now running at `http://YOUR_SERVER_IP`.

## Common Tasks

### Update to latest version

```bash
cd /opt/startend
git pull
bash deploy.sh
```

### View logs

```bash
cd /opt/startend
docker compose -f docker-compose.prod.yml logs -f        # all services
docker compose -f docker-compose.prod.yml logs -f app     # app only
docker compose -f docker-compose.prod.yml logs -f db      # database only
```

### Restart the app

```bash
cd /opt/startend
docker compose -f docker-compose.prod.yml restart
```

### Stop everything

```bash
cd /opt/startend
docker compose -f docker-compose.prod.yml down
```

### Check status

```bash
cd /opt/startend
docker compose -f docker-compose.prod.yml ps
```
