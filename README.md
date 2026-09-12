# ZI/O

[简体中文](README.zh-CN.md) | [English](README.md)

ZI/O is a single-user, self-hosted temporal archive. Notes are timestamped events; Items provide long-lived context.

## Requirements

Python 3.11+, Node.js 20+ (the repository is verified with Python 3.14 and Node 25), and SQLite 3.35+.

## Local setup

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
npm --prefix frontend install
```

Set configuration in the shell (copy `backend/.env.example`, replace the secret, and export the values; the application intentionally does not load `.env` files implicitly):

```sh
export ZIO_DATABASE_PATH="$PWD/data/zio.sqlite3"
export ZIO_STATIC_PAGES_ROOT="$PWD/data/static-pages"
export ZIO_COVERS_ROOT="$PWD/data/covers"
export ZIO_FRONTEND_DIST="$PWD/frontend/dist"
export ZIO_PUBLIC_ORIGIN="http://127.0.0.1:8000"
export ZIO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ZIO_TIMEZONE="Asia/Shanghai"
```

Initialize the database and the only administrator (`misaka`) once:

```sh
PYTHONPATH=backend .venv/bin/python -m app.cli migrate
PYTHONPATH=backend .venv/bin/python -m app.cli init-admin
```

Build and run:

```sh
npm --prefix frontend run build
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/now`.

## Development mode

For day-to-day development, Vite provides hot updates, so there is no need to run `npm --prefix frontend run build` after every frontend change. Start the backend and frontend in two terminals from the repository root.

Terminal 1 — start the API and allow requests from the Vite development server:

```sh
export ZIO_PUBLIC_ORIGIN="http://127.0.0.1:5173"
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — start Vite:

```sh
npm --prefix frontend run dev
```

Open `http://127.0.0.1:5173/now`. Vite updates the page when frontend files change and proxies `/api` and `/page` to the backend on port 8000. Uvicorn's `--reload` option restarts the backend when Python files change. Run the production build only before serving the frontend through FastAPI or performing final verification.

The frontend defaults to Simplified Chinese. Use the language button in the top bar to switch to English; the choice is saved in the current browser.

## Operations

The service applies pending migrations at startup. Use `GET /api/health` for a health check. A systemd example is in `deploy/zio.service`; it runs one Uvicorn worker as a non-root user and expects TLS to be terminated by a reverse proxy. Keep `ZIO_SECRET_KEY` and the production origin in `/etc/zio/zio.env` with mode 600.

Static pages are self-contained UTF-8 HTML files placed under `ZIO_STATIC_PAGES_ROOT`. A Note's `static_path` is a relative `.html` path; the `/page/{note_id}` endpoint performs the same public/private check as Note details and applies a restrictive CSP. Item posters are uploaded from the management UI as JPEG, PNG, or WebP (5 MiB maximum) and stored under `ZIO_COVERS_ROOT`.

## Backup and restore

Use SQLite's online backup API while the service is running:

```sh
PYTHONPATH=backend .venv/bin/python -m app.cli backup /var/backups/zio-$(date +%Y%m%d-%H%M%S).sqlite3
```

For a restore, stop the service, copy the verified backup to a new file, run `PRAGMA integrity_check` with SQLite, retain the old database as a dated rollback copy, then atomically replace `ZIO_DATABASE_PATH` and restart. Never copy a live database file with `cp` as a backup method.

The current system structure and ASCII request flows are documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The complete request/response contract and stable error codes are in [`docs/API.md`](docs/API.md); requirements are in [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md).

## Verification

```sh
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
npm --prefix frontend run build
```
