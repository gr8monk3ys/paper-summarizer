# Repository Guidelines

## Project Structure & Module Organization
The core package lives in `paper_summarizer/`.
Key paths:
- `paper_summarizer/core/` contains summarization logic and model adapters.
- `paper_summarizer/web/` hosts the FastAPI app (`app.py`), routes, auth, templates, and static assets.
- `data/` stores the local SQLite database (`paper_summarizer.db`) for summaries.
- `uploads/` is runtime storage for file uploads (also used by Docker volumes).
- `public/` contains screenshots and marketing assets used in `README.md`.
- `tests/` holds pytest suites and fixtures.

## Build, Test, and Development Commands
Typical local workflow:
- `uv sync --group dev` installs runtime + dev dependencies from `uv.lock`.
- `uv sync --group dev --extra local` installs optional local-model dependencies.
- `uvicorn paper_summarizer.web.app:app --reload --port 5000` runs the dev server.
- `uv run pytest` executes the full test suite.
- `alembic upgrade head` applies database migrations.
- `arq paper_summarizer.web.worker.WorkerSettings` runs the background worker (requires Redis).
- `python scripts/backup_db.py --keep 10` creates a SQLite backup and prunes old ones.
Containerized options:
- `docker-compose up --build` builds and runs the production container.
- `docker-compose --profile dev up --build` runs the hot-reload dev container.
- `docker-compose --profile observability up --build` starts Prometheus + Grafana.
- `LOCAL_MODELS=true docker-compose build --build-arg LOCAL_MODELS=true` builds images with local models.
- Grafana auto-loads the `Paper Summarizer` dashboard from `ops/grafana/dashboards/`.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation.
- Use `snake_case` for functions and variables, `PascalCase` for classes.
- Prefer descriptive module names like `routes.py`, `models.py`, `auth.py`.
- Add docstrings for new public functions and modules.
No formatter or linter is configured; keep changes small, readable, and consistent.

## Testing Guidelines
- Tests are written with `pytest` in `tests/`.
- Naming: `test_*.py` files and `test_*` functions.
- Run `uv run pytest` before opening a PR.
Note: On macOS Intel (`darwin/x86_64`), `torch` wheels are unavailable; local-model tests are skipped and Together AI should be used for development.

## Commit & Pull Request Guidelines
- Recent history follows Conventional Commit prefixes such as `feat:`, `chore:`, and `docs:`. Use the same style with an imperative subject.
- PRs should include a short summary, the test command(s) run, and screenshots for UI changes.
- Link related issues where applicable.

## Security & Configuration Tips
- Use `.env` for local configuration (e.g., `TOGETHER_API_KEY`, `SECRET_KEY`, `APP_ENV`).
- Avoid committing secrets or generated uploads under `uploads/`.
