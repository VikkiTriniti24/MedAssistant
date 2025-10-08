# Deployment Guide

This document outlines how to deploy MedAssistant to a Linux host (Ubuntu/Debian-like). Adapt paths/commands for your environment.

## 1. Prerequisites
- Python 3.9+
- Virtualenv or venv
- SQLite (built-in with Python)
- Reverse proxy / TLS terminator (e.g., Nginx + Certbot)
- Optional: process manager (systemd, supervisor)

## 2. Checkout & Environment
```bash
# as deploy user
mkdir -p /opt/medassistant
cd /opt/medassistant
git clone <repo-url> app
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` (or export vars via systemd service):
```env
FLASK_ENV=production
SECRET_KEY=<random>
JWT_SECRET_KEY=<random>
DATABASE_URL=sqlite:///instance/health_app.db
AI_STUB=1  # remove when real OpenAI key is available
# OPENAI_API_KEY=sk-...
# Optional: control fallback language and wording when OpenAI is unavailable
# AI_FALLBACK_LANGUAGE=de            # supported: de | en (default de)
# AI_FALLBACK_PREFIX=MedAssistant-Notfallantwort:
# AI_FALLBACK_LINES=Hinweis 1|Hinweis 2|Hinweis 3
# Session / JWT
JWT_ACCESS_TOKEN_EXPIRES=1800
JWT_REFRESH_TOKEN_EXPIRES=604800
JWT_REFRESH_COOKIE_NAME=refresh_token
JWT_REFRESH_COOKIE_SECURE=true
JWT_REFRESH_COOKIE_SAMESITE=Lax
JWT_COOKIE_CSRF_PROTECT=false
# Email (optional SMTP)
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-user
MAIL_PASSWORD=your-pass
MAIL_DEFAULT_SENDER=no-reply@example.com
EMAIL_VERIFICATION_URL=https://your-host/auth/verify
EMAIL_VERIFICATION_TOKEN_MINUTES=60
```

## 3. Initialize Database
```bash
source .venv/bin/activate
flask --app health_app db upgrade
```

Seed demo data if desired:
```bash
python instance/manage_db.py seed
```

## 4. Application Startup
Development/simple deployment:
```bash
source .venv/bin/activate
HOST=0.0.0.0 PORT=8000 FLASK_DEBUG=0 python run.py
```

Production recommendation: run behind Gunicorn + systemd.
Example systemd unit (`/etc/systemd/system/medassistant.service`):
```
[Unit]
Description=MedAssistant API
After=network.target

[Service]
User=medassistant
WorkingDirectory=/opt/medassistant/app
Environment="PATH=/opt/medassistant/app/.venv/bin"
EnvironmentFile=/opt/medassistant/app/.env
ExecStart=/opt/medassistant/app/.venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 'health_app:create_app()'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Reload and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now medassistant
```

## 5. Reverse Proxy (Nginx)
```
server {
    listen 80;
    server_name your-domain;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
Add TLS via Certbot or equivalent.

## 6. Backups
- SQLite backups: `flask --app health_app backup-db` (default writes to `instance/backups`).
- For scheduled backups, create a cron entry using the same command.
- Retain multiple copies and move to off-host storage.
- Chat history: prune sessions/messages with `flask --app health_app prune-chat-history [--days=N]` (defaults to `CHAT_HISTORY_RETENTION_DAYS`, 90 by default).
- Reminder dispatch: trigger due reminders via `flask --app health_app dispatch-reminders [--grace-minutes=5]`.
- Audit export: collect support evidence with `flask --app health_app export-audit-logs [--start=ISO] [--end=ISO] [--format=csv] [--pseudonymize]`.
- The dashboard also exposes a **Data Exports** card for signed-in users (profile JSON, latest chat as JSON/TXT, admin-only audit CSV).

## 7. Monitoring & Logs
- Application log: systemd journal (`journalctl -u medassistant`).
- Audit logs: `SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50;`
- Rate limiting events: `SELECT * FROM rate_limit_hits`
- Prometheus scraping: `/metrics` exposes counters for AI fallbacks and rate-limit hits.

## 8. Upgrades
```bash
cd /opt/medassistant/app
git pull
source .venv/bin/activate
pip install -r requirements.txt
flask --app health_app db upgrade
sudo systemctl restart medassistant
```

## 9. Troubleshooting
- Missing tables: rerun `flask --app health_app db upgrade`.
- 401 responses: ensure JWT secret matches on server and clients.
- AI key errors: set `AI_STUB=1` for offline mode or configure `OPENAI_API_KEY`.
- AI fallback text in the wrong language: export `AI_FALLBACK_LANGUAGE=en` (or override `AI_FALLBACK_PREFIX`/`AI_FALLBACK_LINES`).
- Backups failing: verify SQLite path and permissions.

## 10. Checklist
- [ ] Environment variables configured
- [ ] Database upgraded & seeded (optional)
- [ ] Service running under systemd / supervisor
- [ ] Reverse proxy/TLS in place
- [ ] Backups scheduled and verified
- [ ] Monitoring/alerts configured (journal, audit logs)
- [ ] CI/CD workflow green on the main branch

## 11. CI/CD Pipeline
The repository ships with `.github/workflows/ci.yml` which provides:

- **Lint** job running Ruff to keep the codebase style-consistent.
- **Unit & integration tests** executed with `AI_STUB=1` to avoid live OpenAI calls while still exercising the suite.
- **Staging parity smoke** job that runs the smoke suite against a staging configuration (`ENV=staging`, `FLASK_ENV=production`) and publishes a tarball artifact you can deploy.

To enable deployments from Actions, connect the `staging` environment to your infrastructure (self-hosted runner or deployment credentials) and extend the final job with your release steps.
