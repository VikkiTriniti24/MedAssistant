My Health App

Flask app with JWT auth, Symptom Checker, Drug Interactions (stub), and a Chat-based Diagnosis assistant (OpenAI or local stub).

Quick Start:

# 1) Create venv & install deps
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

Create .env in project root:
FLASK_ENV=development
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me-too
DATABASE_URL=sqlite:///instance/app.db

VERSION=0.1.0
ENV=development

# Chat model (works without API key via stub)
OPENAI_MODEL=gpt-4o-mini
# Optional real key:
# OPENAI_API_KEY=sk-...
# Force local stub (no API calls):
# AI_STUB=1

Database (Flask-Migrate):
flask --app health_app db init           # once
flask --app health_app db migrate -m "init"
flask --app health_app db upgrade

Dev seed data (demo user):
python instance/manage_db.py reset --yes
python instance/manage_db.py seed
# demo@example.com / password123

Run:
python run.py
# http://127.0.0.1:5000

/login – sign in (stores JWT in localStorage)

/register – optional signup

/ – dashboard (Chat, Symptom Checker, Drug Interactions)

/healthz – health check

API (cURL):

# Get token
TOKEN=$(
  curl -s http://127.0.0.1:5000/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"demo@example.com","password":"password123"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"], end="")'
)

# Symptom checker
curl -s --oauth2-bearer "$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symptoms":"fever 38.1, sore throat","onset":"sudden"}' \
  http://127.0.0.1:5000/health-check/

# Drug interactions (stubbed output)
curl -s --oauth2-bearer "$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"drugs":[{"name":"ibuprofen","dose":"400 mg"}]}' \
  http://127.0.0.1:5000/drug-check/

# Chat (OpenAI or stub)
curl -s --oauth2-bearer "$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Say something nice."}]}' \
  http://127.0.0.1:5000/chat/

Tests:

PYTHONPATH=. pytest -q
# or with coverage:
PYTHONPATH=. pytest --maxfail=1 -q --cov=health_app --cov-report=term-missing

Troubleshooting

401 / “Requires login” → Log in via /login or pass Authorization: Bearer <JWT>.

“Bad Authorization header” → Missing/empty token; use --oauth2-bearer "$TOKEN".

no such table: users → Run migrations: flask --app health_app db upgrade; for demo, run reset + seed.

OpenAI client errors → Use openai==1.40.3, httpx==0.27.2 (already pinned). Without API key, set AI_STUB=1.

Git (from PyCharm or CLI)

.gitignore already excludes .venv/, .env, .idea/, instance/*.db, etc.

git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
