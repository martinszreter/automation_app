# Deploying STARTEND

This guide deploys the app on a single Ubuntu 24.04 server (e.g. Hetzner) reachable on port 80.

## 1. Server Access

SSH into your server:

```bash
ssh root@YOUR_SERVER_IP
```

## 2. Set Up a GitHub Deploy Key

This lets the server pull the private repo without your personal credentials.

**On the server**, generate a key pair:

```bash
ssh-keygen -t ed25519 -C "deploy@startend" -f ~/.ssh/deploy_key -N ""
```

Print the public key and copy it:

```bash
cat ~/.ssh/deploy_key.pub
```

**On GitHub**, go to the repo → **Settings → Deploy keys → Add deploy key**.
Paste the public key, give it a name like "Hetzner server", and save.
Leave "Allow write access" **unchecked** (read-only is enough).

Tell SSH to use this key for GitHub:

```bash
cat >> ~/.ssh/config << 'EOF'
Host github.com
  IdentityFile ~/.ssh/deploy_key
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

## 3. Clone the Repo

```bash
cd /opt
git clone git@github.com:martinszreter/automation_app.git
cd automation_app
```

## 4. Configure Environment

```bash
cp .env.example .env
nano .env
```

Fill in **real values** for every variable. At minimum change:
- `POSTGRES_PASSWORD` — use a strong random password
- `SECRET_KEY` — use a long random string

Save and exit (`Ctrl+X`, then `Y`, then `Enter`).

## 5. Deploy

```bash
sudo bash deploy.sh
```

The script installs Docker if needed, builds the app, starts it, and runs migrations.
It is safe to run again after updates.

## 6. Verify

Open `http://YOUR_SERVER_IP` in a browser. You should see the app.

Or from the server:

```bash
curl http://localhost/health
```

---

## Updating the App

```bash
cd /opt/automation_app
git pull origin main
sudo bash deploy.sh
```

## Viewing Logs

```bash
cd /opt/automation_app

# All logs
docker compose -f docker-compose.prod.yml logs

# Follow logs in real-time
docker compose -f docker-compose.prod.yml logs -f

# App logs only
docker compose -f docker-compose.prod.yml logs -f app
```

## Restarting

```bash
cd /opt/automation_app
docker compose -f docker-compose.prod.yml restart
```

## Stopping

```bash
cd /opt/automation_app
docker compose -f docker-compose.prod.yml down
```

> **Note:** Your database data is stored in a Docker volume and survives restarts and redeployments. To delete it (destroys all data!), run `docker compose -f docker-compose.prod.yml down -v`.
