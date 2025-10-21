# Magic Chef – Your AI‑Powered Digital Cookbook (Flask + HTMX + Postgres)

https://img.shields.io/badge/license-MIT-blue.svg](LICENSE)
https://img.shields.io/badge/build-passing-brightgreen.svg]()
[![Contributions](https://img.shields.ions-welcome-orange.svg]()

Magic Chef is a Flask web app with a PostgreSQL database and an HTMX-powered frontend. It lets you **create, share, and organize recipes** in your personal digital cookbook—with superpowers:
**AI recipe generation from ingredients, recipe translation, and digitization of handwritten recipes from images**.

---

## ✨ Features

- **AI Recipe Generator**
  - Turn a list of ingredients into complete recipes (title, steps, timing, servings, nutritional hints).
- **Recipe Translation**
  - Translate any recipe to multiple languages (e.g., EN/DE/ES) with one click.
- **Handwritten Recipe Digitization (OCR)**
  - Upload photos/scans of handwritten recipes and convert to editable text.
- **HTMX Frontend**
  - Snappy, partial-page updates for forms, tables, modals, and inline actions (no SPA framework required).
- **Smart Search & Tags**
  - Filter by ingredients, cuisine, tags, diet; full-text search backed by Postgres.
- **Accounts & Sharing**
  - User auth (Flask-Login), private/public recipes, share links.
- **Media Uploads**
  - Store recipe images; configurable local/S3 storage.

---

## 🏗️ Tech Stack
- **Backend:** Python 3.11+, Flask, Jinja2, Flask-Login, Flask-WTF
- **Frontend:** HTMX, Hyperscript (optional), Tailwind/Bootstrap (choose your CSS path)
- **Database:** PostgreSQL 14+, SQLAlchemy 2.x, Alembic migrations
- **AI & Services (pluggable):**
  - **Generation:** OpenAI (or other LLM provider)
  - **Translation:** DeepL / Google Translate / Azure Translator
  - **OCR:** Tesseract (local) or cloud OCR (Google Vision / Azure Cognitive Services)
- **Storage:** Local filesystem or S3-compatible (via `boto3`)
- **Dev/Ops:** `.env` config, Docker Compose (optional), pytest

---

## 📦 Project Structure (suggested)

```
magic-chef/
├─ app/
│  ├─ __init__.py           # create_app(), extensions, blueprints
│  ├─ config.py             # Config classes (Dev/Test/Prod)
│  ├─ models.py             # SQLAlchemy models (User, Recipe, Step, Tag, Image, etc.)
│  ├─ services/
│  │  ├─ ai.py              # ingredient->recipe generation
│  │  ├─ translate.py       # translation adapters
│  │  └─ ocr.py             # OCR adapters
│  ├─ blueprints/
│  │  ├─ auth.py            # signup/login/logout
│  │  ├─ recipes.py         # CRUD, search, tagging
│  │  ├─ htmx.py            # HTMX endpoints/partials
│  │  └─ uploads.py         # image upload/serve
│  ├─ templates/
│  │  ├─ base.html
│  │  ├─ _flash.html
│  │  └─ recipes/
│  │     ├─ index.html
│  │     ├─ show.html
│  │     ├─ edit.html
│  │     ├─ _form.html      # shared form
│  │     ├─ _row.html       # HTMX list row partial
│  │     └─ _translate_modal.html
│  ├─ static/
│  │  ├─ css/               # Tailwind/Bootstrap assets
│  │  └─ js/                # htmx.min.js, hyperscript, small helpers
│  └─ db/
│     └─ migrations/        # Alembic scripts
├─ tests/
│  └─ ...                   # pytest suites
├─ alembic.ini
├─ requirements.txt
├─ .env.example
├─ docker-compose.yml
└─ README.md
```

---

## 🚀 Getting Started
### Prerequisites

- **Python** 3.11+
- **PostgreSQL** 14+ (local or container)
- **Tesseract** (if using local OCR): install binary & language packs (e.g., `eng`, `de`)
- **API keys** for selected providers (e.g., OpenAI, DeepL/Google Translate, Cloud OCR)
- (Optional) **Docker** + **Docker Compose**

### 1) Clone & Create Virtual Env

```bash
git clone https://github.com/your-username/magic-chef.git
cd magic-chef

python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
# .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Configure Environment

Copy the example and fill in values:

```bash
cp .env.example .env
```

**`.env.example`**

```
# Flask
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=change-me

# App
APP_NAME=Magic Chef
APP_URL=http://127.0.0.1:5000
UPLOAD_DIR=./uploads
MAX_CONTENT_LENGTH_MB=10

# Database (SQLAlchemy URL)
DATABASE_URL=postgresql+psycopg://magic_chef:magic_chef@localhost:5432/magic_chef_dev

# AI Generation
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Translation
TRANSLATION_PROVIDER=deepl   # deepl|google|azure
TRANSLATION_API_KEY=...

# OCR
OCR_PROVIDER=tesseract       # tesseract|gcv|azure
TESSERACT_LANGS=eng,de,es

# Storage (optional)
STORAGE_PROVIDER=local       # local|s3
S3_BUCKET=
S3_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

> **Note:** If you prefer Docker, see the **Docker Compose** section below.

### 3) Prepare Database

Create a Postgres user/db (adjust to your setup):

```bash
# macOS/Linux example
createdb magic_chef_dev
createuser magic_chef --pwprompt  # set password to 'magic_chef'
# grant privileges as needed (or use psql to GRANT/ALTER)

# Run Alembic migrations
flask db upgrade
```

> If `flask` is not found, set the app: `export FLASK_APP=app:create_app` (Linux/macOS) or `set FLASK_APP=app:create_app` (Windows).

### 4) Run the App

```bash
flask run
# App is served at http://127.0.0.1:5000
```

---

## 🧪 Sample Workflows (HTMX + API)

### Generate a recipe from ingredients (HTMX form → partial)

- **Route (POST):** `/recipes/generate`
- **Payload:** `ingredients=tomato, basil, garlic`

**Example (curl for API-style usage):**
```bash
curl -X POST http://127.0.0.1:5000/recipes/generate \
  -H "Content-Type: application/json" \
  -d '{"ingredients": ["tomato","basil","garlic"], "servings": 2, "diet": "vegetarian"}'
```

### Translate a recipe

- **Route (POST):** `/recipes/<id>/translate`
- **Payload:** `target_lang=de`

```bash
curl -X POST http://127.0.0.1:5000/recipes/42/translate \
  -H "Content-Type: application/json" \
  -d '{"target_lang": "de"}'
```

### OCR from image upload

- **Route (POST):** `/recipes/ocr`
- **Form:** multipart with `image` file input
```bash
curl -X POST http://127.0.0.1:5000/recipes/ocr \
  -F "image=@/path/to/handwritten.jpg"
```

> HTMX endpoints typically return partial HTML fragments (e.g., a single `<tr>` for a table) that are swapped into the page.

---

## 🗃️ Database & Migrations

Common Alembic commands:
```bash
# Create migration from model changes
flask db migrate -m "add recipe translations"

# Apply migrations
flask db upgrade

# Roll back last migration
flask db downgrade -1
```

Key models (typical):
- `User(id, email, password_hash, ...)`
- `Recipe(id, user_id, title, summary, lang, servings, total_minutes, ... )`
- `RecipeStep(id, recipe_id, idx, text)`
- `RecipeTag(id, name)` + association table
- `RecipeImage(id, recipe_id, path, alt)`
- `AuditLog(...)` (optional)

---

## 🧩 HTMX Patterns Used

- **Inline create/edit** with `hx-post`/`hx-put`, target row swap via `hx-target="#row-{{ id }}" hx-swap="outerHTML"`.
- **Modals** for translation with server-rendered partials (`_translate_modal.html`).
- **Pagination & Search** powered by server-side queries; results streamed as partial tables.
- **Progressive enhancement:** Full-page fallback routes mirror partial endpoints.

---

## 🧰 Development Scripts (optional)
```bash
# Lint & tests
pytest -q
ruff check .
black --check .

# Generate Tailwind (if used)
# npx tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css --watch
```

---

## 🐳 Docker Compose (optional)

**`docker-compose.yml` (example):**
```yaml
version: "3.9"
services:
  db:
    image: postgres:14
    environment:
      POSTGRES_DB: magic_chef_dev
      POSTGRES_USER: magic_chef
      POSTGRES_PASSWORD: magic_chef
    ports:
      - "5432:5432"
    volumes:
      - dbdata:/var/lib/postgresql/data

  web:
    build: .
    command: flask run --host=0.0.0.0 --port=5000
    environment:
      FLASK_ENV: development
      SECRET_KEY: change-me
      DATABASE_URL: postgresql+psycopg://magic_chef:magic_chef@db:5432/magic_chef_dev
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      TRANSLATION_API_KEY: ${TRANSLATION_API_KEY}
      OCR_PROVIDER: tesseract
      TESSERACT_LANGS: eng,de,es
    volumes:
      - .:/app
      - uploads:/app/uploads
    ports:
      - "5000:5000"
    depends_on:
      - db
volumes:
  dbdata:
  uploads:
```

Build & run:
```bash
docker compose up --build
```

Run migrations in the container:

```bash
docker compose exec web flask db upgrade
```

---

## 🔐 Security & Privacy

- Store API keys only in `.env` / secrets manager (never commit them).
- Validate and sanitize uploaded images; enforce size/type limits.
- Use CSRF protection for forms, secure cookies for sessions.
- Rate-limit AI/OCR endpoints as needed.
- Consider background jobs for long OCR/AI tasks (Celery/RQ).

---

## 🧭 Roadmap

- [ ] Meal planning & shopping lists
- [ ] Nutritional analysis
- [ ] Bulk import/export (JSON/CSV)
- [ ] Public profiles & collections
- [ ] Background jobs for OCR/AI with progress UI

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/awesome-thing`
3. Commit changes: `git commit -m "feat: add awesome thing"`
4. Push & open a PR

Please run tests/linting before submitting.

---

## 📜 License

MIT License — see `LICENSE`.

---

### GitHub Repo Description

**Magic Chef – Flask + HTMX + Postgres digital cookbook. Create, share, and discover recipes with AI. Generate from ingredients, translate, and digitize handwritten notes.**

### SEO Keywords

`Flask recipe app, HTMX, PostgreSQL, AI recipes, digital cookbook, OCR handwritten recipes, recipe translation, OpenAI, DeepL, Tesseract, Python web`
``
