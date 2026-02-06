# Paper Summarizer

![Dashboard](public/images/dashboard.png)

A modern web application that helps researchers and students quickly summarize academic papers using advanced language models. Built with FastAPI and Together AI, it provides an intuitive interface for summarizing papers from text, URLs, or file uploads.

## Features

- **Multiple Input Methods**: 
  - Direct text input
  - URL scraping
  - File upload (supports .txt, .md, .rst)
  - Batch processing for multiple files

- **Advanced Summarization**:
  - Choice of language models (T5-Small, DeepSeek-R1)
  - Local or Together AI processing
  - Configurable summary length
  - Optional citation handling

- **Modern Interface**:
  - Clean, responsive design with Tailwind CSS
  - Real-time processing feedback
  - Error handling and validation
  - Mobile-friendly layout

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gr8monk3ys/paper-summarizer.git
cd paper-summarizer
```

2. Install dependencies with uv:
```bash
uv sync --group dev
```
For local model support (torch/transformers), add:
```bash
uv sync --group dev --extra local
```

Note: On macOS Intel (`darwin/x86_64`), `torch` wheels are not available for the current environment. Local model tests are skipped and the app should use the Together AI provider unless you build torch from source or run on a supported platform.

3. Set up environment variables:
```bash
# Create a .env file with:
TOGETHER_API_KEY=your_api_key_here
APP_ENV=development
AUTO_CREATE_DB=true
SECRET_KEY=change-me
DEFAULT_PROVIDER=together_ai
LOCAL_MODELS_ENABLED=false
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
LOG_LEVEL=INFO
REDIS_URL=redis://redis:6379/0
SENTRY_DSN=
METRICS_ENABLED=true
LOCAL_MODELS=false
```

## Usage

1. Start the FastAPI server:
```bash
uvicorn paper_summarizer.web.app:app --reload --port 5000
```

2. Open your browser and navigate to `http://localhost:5000`

3. Choose your preferred input method:
   - Paste paper text directly
   - Enter a paper URL
   - Upload a paper file
   - Batch process multiple files

4. Configure summarization options:
   - Select model type (T5-Small or DeepSeek-R1)
   - Choose provider (Local or Together AI)
   - Set number of sentences
   - Toggle citation handling

5. Click "Generate Summary" and view the results
6. Use **Archive** to export or import summaries for backup
7. Use **Synthesis** to combine multiple summaries into a consensus view
8. Sign in via `/login` to access your personal summary library

## Data & API

- Summaries are stored in a local SQLite database at `data/paper_summarizer.db`.
- For production, set `DATABASE_URL` to a Postgres connection string (e.g., `postgresql+psycopg://user:pass@host:5432/paper_summarizer`) and run `alembic upgrade head`.
- Key endpoints:
  - `POST /summarize` for single summaries
  - `POST /batch` for batch uploads
  - `GET /api/summaries` to list saved summaries
  - `GET /export/{summary_id}?format=txt|md|pdf` to download a summary
  - `POST /api/summaries/{summary_id}/evidence/generate` to scaffold evidence maps
  - `PUT /api/summaries/{summary_id}/evidence/{evidence_id}` to edit evidence
  - `DELETE /api/summaries/{summary_id}/evidence/{evidence_id}` to delete evidence
  - `POST /api/summaries/synthesize` to generate a consensus snapshot
  - `GET /api/summaries/export` and `POST /api/summaries/import` for archive workflows
  - `GET /api/summaries/synthesize/export?format=txt|md|pdf` to export synthesis output
  - `POST /api/jobs/summarize` and `GET /api/jobs/{job_id}` for background job processing
  - `GET /metrics` for Prometheus metrics (when enabled)

## Development

- **Testing**: Run the test suite with:
```bash
uv run pytest
```

- **Migrations**: Apply database migrations with:
```bash
alembic upgrade head
```
For production, set `APP_ENV=production` and `AUTO_CREATE_DB=false` and apply migrations before starting the app.

- **Background Jobs**: Run the worker for queued summaries (requires Redis):
```bash
arq paper_summarizer.web.worker.WorkerSettings
```

- **Backups**: Create a local SQLite backup with:
```bash
python scripts/backup_db.py --keep 10
```

- **Docker (with jobs + Redis)**:
```bash
docker-compose up --build
```
Docker images install only the base dependencies; local model support is excluded to keep builds fast. Use `DEFAULT_PROVIDER=together_ai` and set `TOGETHER_API_KEY`.
Set `LOCAL_MODELS_ENABLED=true` and build with `--build-arg LOCAL_MODELS=true` if you want local models in Docker.

- **Docker with local models**:
```bash
LOCAL_MODELS=true docker-compose build --build-arg LOCAL_MODELS=true
LOCAL_MODELS_ENABLED=true docker-compose up
```

- **Observability stack (Prometheus + Grafana)**:
```bash
docker-compose --profile observability up --build
```
Grafana runs on `http://localhost:3000` (admin/admin by default).

- **Sentry alerting**:
  - Set `SENTRY_DSN` and configure alert rules in Sentry (errors, latency, or throughput).
  - Recommended: alert on `5xx` error rate and high latency (p95).

- **Code Style**: Follow PEP 8 guidelines
- **Documentation**: Add docstrings for new functions
- **Error Handling**: Include appropriate error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Together AI for providing the API
- FastAPI team for the excellent web framework
- Tailwind CSS for the styling framework
