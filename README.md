# CareerBridge AI — Deployment README

AI-powered career copilot: resume analysis → skill extraction → career matching → gap analysis → learning roadmap → AI chat → resume builder.

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Local Development](#local-development)
3. [Deploy to Railway (Recommended)](#deploy-to-railway)
4. [Deploy to AWS Elastic Beanstalk + RDS](#deploy-to-aws-eb)
5. [Environment Variables Reference](#environment-variables)
6. [Database Backup & Migration](#database-backup--migration)
7. [File Storage Strategy](#file-storage-strategy)
8. [ML Models & Knowledge Base](#ml-models--knowledge-base)
9. [Security Notes](#security-notes)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## Project Structure

```
careerbridge-ai/
├── app.py                  # Flask application factory (entry point)
├── application.py          # AWS EB entry point (imports app.py factory)
├── run.py                  # Local dev runner
├── config.py               # All configuration classes
├── requirements.txt        # Production dependencies
├── Procfile                # Railway / Heroku start command
├── railway.json            # Railway platform config
├── nixpacks.toml           # Railway build config (Python + spaCy)
├── .env.example            # Safe template — copy to .env
│
├── api/                    # Flask blueprints (9 modules)
│   ├── auth.py             # /api/auth/* — register, login, logout
│   ├── resume.py           # /api/resume/* — upload, parse, confirm
│   ├── careers.py          # /api/careers/* — recommendations
│   ├── skills.py           # /api/skills/*
│   ├── roadmap.py          # /api/roadmap/*
│   ├── chat.py             # /api/chat/* — AI copilot
│   ├── profile.py          # /api/profile/*
│   ├── resume_builder.py   # /api/resume-builder/*
│   └── feedback.py         # /api/feedback/*
│
├── services/               # Business logic
│   ├── resume_parser.py    # PDF/DOCX extraction, validation
│   ├── skill_extractor.py  # Dictionary + alias skill matching
│   ├── section_detector.py # Resume section classification
│   ├── career_engine.py    # Hybrid KB + ML career ranking
│   ├── skill_gap_engine.py # Deterministic gap analysis
│   ├── roadmap_engine.py   # Topological sort roadmap
│   ├── chatbot.py          # Intent → context → LLM → validate
│   └── llm/                # LLM provider adapters
│       ├── base.py
│       ├── provider.py     # StubProvider + OpenAIProvider
│       ├── prompt_builder.py
│       └── response_validator.py
│
├── database/
│   ├── models.py           # 20 SQLAlchemy models
│   └── seed.py             # flask seed-db CLI command
│
├── kb/                     # Knowledge base (REQUIRED at runtime)
│   ├── skills.csv
│   ├── career_roles.csv
│   ├── role_skills.csv
│   ├── skill_prerequisites.csv
│   └── VERSION
│
├── models/                 # ML model artifacts (optional — KB fallback works)
│   └── v0.1-kb-baseline/   # career_model.joblib, intent_model.joblib, meta.json
│
├── static/                 # CSS + JS frontend (SPA)
│   ├── css/main.css
│   └── js/app.js, api.js
│
├── templates/index.html    # SPA shell served for all non-API routes
├── uploads/                # User-uploaded resumes (private, never public)
└── generated_resumes/      # Generated PDF resumes (private)
```

---

## Local Development

### Prerequisites
- Python 3.11+
- MySQL 8.0+ running locally
- Git

### Setup

```powershell
cd "e:\IBM Project\careerbridge-ai"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
copy .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY at minimum

# Create MySQL database
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS careerbridge CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Create tables and seed knowledge base
flask init-db
flask seed-db

# Run development server
python run.py
```

Open `http://localhost:5000` in your browser.

---

## Deploy to Railway

### Step 1 — Push to GitHub

```powershell
cd "e:\IBM Project\careerbridge-ai"
git init
git add .
git commit -m "Initial production deploy"
```

Go to https://github.com/new → create a **private** repo named `careerbridge-ai`, then:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/careerbridge-ai.git
git branch -M main
git push -u origin main
```

### Step 2 — Create Railway Project

1. Go to https://railway.app → **Login with GitHub**
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `careerbridge-ai` repo → **Deploy Now**

### Step 3 — Add MySQL Database

1. Inside your Railway project → click **+ New**
2. Choose **Database** → **MySQL**
3. In your web service's **Variables** tab, add `MYSQL_URL` as a Railway variable reference to the MySQL service's `MYSQL_URL` (for example, `${{MySQL.MYSQL_URL}}`; use the exact MySQL service name shown in your project). The app reads this URL automatically.

### Step 4 — Set Environment Variables

In Railway → your **web service** → **Variables** tab → click **RAW Editor**, paste:

```
FLASK_APP=app.py
FLASK_ENV=production
SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
LLM_PROVIDER=stub
UPLOAD_FOLDER=/tmp/uploads
GENERATED_FOLDER=/tmp/generated_resumes
MAX_CONTENT_LENGTH=5242880
MODEL_VERSION=v0.1-kb-baseline
KB_VERSION=v0.1
FEATURE_VERSION=v0.1
```

`SECRET_KEY` and a database URL (`MYSQL_URL` or `DATABASE_URL`) are required in production. The app now exits with a clear error if either is missing rather than using a development key or trying a local database.

> To enable the real AI copilot: set `LLM_PROVIDER=openai` and `LLM_API_KEY=sk-...`

### Step 5 — Get Your Live URL

Railway → your service → **Settings** → **Networking** → **Generate Domain**

Your app is live at: `https://careerbridge-ai-production.up.railway.app` 🎉

### Step 6 — Verify Deployment

```
GET https://your-app.up.railway.app/api/health
→ {"status": "ok", "version": "v0.1-kb-baseline"}
```

---

## Deploy to AWS Elastic Beanstalk + RDS

### Part A — Create RDS MySQL

1. AWS Console → **RDS** → **Create database**
   - Engine: **MySQL 8.0**
   - Template: **Free tier**
   - Instance: `db.t3.micro`
   - DB name: `careerbridge`
   - Username: `admin`, set a strong password
   - **Public access: NO**
   - VPC: Default
2. Wait ~5 min for the instance to start
3. Note the **Endpoint** URL (e.g. `careerbridge.xyz.us-east-1.rds.amazonaws.com`)

### Part B — Install & Configure EB CLI

```powershell
pip install awsebcli
aws configure   # Enter Access Key ID, Secret Access Key, region
```

### Part C — Initialize and Deploy

```powershell
cd "e:\IBM Project\careerbridge-ai"
eb init
# Select region, name: careerbridge-ai, Python 3.11, yes to SSH

eb create careerbridge-production --instance-type t2.micro --single

eb setenv `
  FLASK_APP=application.py `
  FLASK_ENV=production `
  SECRET_KEY=<your-secret> `
  RDS_HOSTNAME=careerbridge.xyz.us-east-1.rds.amazonaws.com `
  RDS_PORT=3306 `
  RDS_DB_NAME=careerbridge `
  RDS_USERNAME=admin `
  RDS_PASSWORD=<your-rds-password> `
  LLM_PROVIDER=stub `
  UPLOAD_FOLDER=/tmp/uploads `
  GENERATED_FOLDER=/tmp/generated_resumes `
  MODEL_VERSION=v0.1-kb-baseline `
  KB_VERSION=v0.1 `
  FEATURE_VERSION=v0.1

eb deploy
eb open
```

### Part D — Fix RDS Security Group

1. AWS Console → EB → your environment → **Configuration** → note EC2 security group
2. RDS → your DB → **Connectivity** → security group → **Add inbound rule**:
   - Type: MySQL/Aurora, Port: 3306, Source: EC2 security group ID

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Flask session signing key — generate with `secrets.token_hex(32)` |
| `FLASK_ENV` | ✅ | `production` or `development` |
| `DATABASE_URL` | ✅* | Full MySQL connection string |
| `MYSQL_URL` | ✅* | Auto-set by Railway MySQL plugin |
| `RDS_HOSTNAME` | ✅* | Auto-set by AWS EB RDS |
| `LLM_PROVIDER` | ✅ | `stub` (free) or `openai` |
| `LLM_API_KEY` | ⚠️ | Required only if `LLM_PROVIDER=openai` |
| `UPLOAD_FOLDER` | ✅ | Where uploaded resumes are stored |
| `GENERATED_FOLDER` | ✅ | Where generated PDF resumes are stored |
| `MODEL_VERSION` | ✅ | ML model version string |

*One of DATABASE_URL / MYSQL_URL / RDS_* is required.

---

## Database Backup & Migration

### Export local database (before deploying)

```powershell
# Backup your local database
mysqldump -u root -p careerbridge --no-data > schema_only.sql
mysqldump -u root -p careerbridge > full_backup.sql
```

> ⚠️ NEVER commit `full_backup.sql` to git — it contains user data.

### The cloud database is initialized automatically

When your app starts on Railway/EB, `start.py` runs:
```
flask seed-db   → Creates all tables and loads the knowledge-base CSV files
```

No manual SQL import is needed for a fresh deployment. The KB data from `kb/` CSV files is loaded automatically.

### Import existing user data (optional)

If you have production data to migrate:
```powershell
# Export only user tables (no KB data — it will be seeded automatically)
mysqldump -u root -p careerbridge users user_profiles resumes resume_analysis user_skills > user_data.sql

# Import into cloud DB (Railway: use the connection string from the MySQL plugin Variables tab)
mysql -h HOST -u USER -p DATABASE < user_data.sql
```

---

## File Storage Strategy

| File type | Location | Strategy |
|---|---|---|
| Uploaded resumes | `UPLOAD_FOLDER` | Ephemeral on Railway/EB — files are lost on redeploy |
| Generated PDFs | `GENERATED_FOLDER` | Ephemeral — regenerate on demand |
| KB CSV files | `kb/` | **Committed to repo** — required at startup for `flask seed-db` |
| ML model files | `models/` | Optional — app falls back to KB-only scoring if absent |
| spaCy model | Installed via `pip` | Downloaded during build (`en_core_web_sm`) |

### ⚠️ Persistent File Storage (Important)

Railway and AWS EB containers are **ephemeral** — uploaded resumes are deleted on every redeploy.

**For permanent user file storage**, add an S3 bucket:

1. Create a private S3 bucket (AWS Console → S3)
2. Set env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET`, `AWS_REGION`
3. The app currently writes to local filesystem — a future upgrade can swap `validate_and_save()` to upload to S3 instead

For now, `/tmp/uploads` works for demos and testing.

---

## ML Models & Knowledge Base

### Knowledge Base (Required)
The `kb/` folder contains 4 CSV files that are committed to the repo and loaded by `flask seed-db`:
- `skills.csv` — skill dictionary with aliases
- `career_roles.csv` — 10 tech career roles
- `role_skills.csv` — skill requirements per role
- `skill_prerequisites.csv` — prerequisite relationships

### ML Models (Optional)
The `models/v0.1-kb-baseline/` folder would contain:
- `career_model.joblib` — trained logistic regression career classifier
- `intent_model.joblib` — intent classification model
- `meta.json` — model metadata (roles, skill_ids)

**If model files are absent**, the app automatically falls back to KB-only scoring (KB coverage score with alpha=0). All features remain functional — career matching, gap analysis, roadmap, and the AI copilot all work without the ML model.

---

## Security Notes

| Area | Status | Notes |
|---|---|---|
| Passwords | ✅ bcrypt hashed | `werkzeug.security.generate_password_hash` |
| Session cookies | ✅ Secure | `HTTPOnly=True`, `SameSite=Lax`, `Secure=True` in production |
| HTTPS proxy | ✅ ProxyFix | Correctly reads `X-Forwarded-Proto` from Railway/EB load balancer |
| File validation | ✅ Magic bytes | Extension + MIME check, UUID storage keys, no path traversal |
| SQL injection | ✅ ORM | All queries via SQLAlchemy ORM or parameterized |
| LLM output | ✅ Validated | Guarantee language stripped, fabrication detection |
| Secrets | ✅ Env vars | No hardcoded credentials — all from environment |
| Rate limiting | ✅ Flask-Limiter | 200 req/day, 50 req/hour defaults |
| API auth | ✅ login_required | All data endpoints protected |
| Resume access | ✅ User-scoped | Queries always filter by `user_id=current_user.id` |

---

## Troubleshooting Guide

### Build fails: `spacy` or `numpy` install error
```
Solution: Ensure nixpacks.toml includes gcc, libffi, openssl.
nixpacks.toml already configures this. If still failing, try:
  pip install spacy==3.7.4 --no-build-isolation
```

### App crashes: `ModuleNotFoundError: No module named 'pymupdf'`
```
Solution: PyMuPDF package name changed. requirements.txt uses PyMuPDF>=1.24.10
which installs as `pymupdf`. The code handles both import names.
```

### Database connection error: `Can't connect to MySQL server`
```
Railway: Check that the MySQL plugin is added to your project.
         Verify MYSQL_URL is in the Variables tab.
AWS EB:  Check RDS security group allows inbound from EB EC2 security group.
         Verify RDS_HOSTNAME, RDS_USERNAME, RDS_PASSWORD are set.
Local:   Verify MySQL is running and DATABASE_URL is correct.
```

### `flask seed-db` fails: `Table already exists`
```
seed.py checks for existing records before inserting (idempotent).
If you see this error, the table structure changed.
Run: flask init-db   (safe — creates tables only if they don't exist)
Then: flask seed-db
```

### Upload fails: `File not found` after redeploy
```
Railway containers are ephemeral — /tmp is cleared on redeploy.
This is expected behavior. For permanent storage, integrate S3.
UPLOAD_FOLDER=/tmp/uploads is correct for demos.
```

### `SESSION_COOKIE_SECURE` blocks login on HTTP (local dev)
```
config.py sets SESSION_COOKIE_SECURE only when FLASK_ENV=production.
For local dev, set FLASK_ENV=development in your .env file.
```

### App health check fails: `GET /api/health returns 502`
```
The app is still starting. spaCy and ML model loading can take 30-60s.
Railway healthcheckTimeout is set to 60s. Wait for the full build to complete.
Check deploy logs: railway logs
```

### `flask seed-db` runs every deploy (re-seeding KB)
```
seed.py is idempotent — it checks for existing records and skips duplicates.
Re-seeding on every deploy is safe and ensures KB stays up to date.
```

### `SECRET_KEY` warning in logs
```
Never use the default 'dev-secret-change-me' in production.
Generate: python -c "import secrets; print(secrets.token_hex(32))"
Set the result as SECRET_KEY in your platform environment variables.
```

### Railway build takes >10 minutes
```
spaCy + scikit-learn + numpy download is ~500MB.
Railway caches the build layer — subsequent deploys are faster (~2-3 min).
First deploy typically takes 8-12 minutes.
```
