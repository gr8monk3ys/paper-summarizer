# Code Quality Report: Paper Summarizer

**Date**: 2026-02-09
**Branch**: claude/code-quality-review-pGWOK

## Project Overview

Paper Summarizer is a FastAPI-based web application for summarizing academic papers using LLMs (T5-Small locally or DeepSeek-R1 via Together AI). It includes user auth, background job processing (ARQ/Redis), a SQLite/Postgres-backed summary library, batch processing, evidence mapping, synthesis, and an observability stack (Prometheus/Grafana). ~2,700 lines of Python across 22 modules, plus 11 JavaScript files and 10 Jinja2 templates.

---

## Production Readiness Verdict: NOT PRODUCTION-READY

There are **7 blocking issues** that must be resolved before this application can safely serve real users.

---

## Blocking Issues (Must Fix)

### 1. XSS Vulnerabilities Across All Frontend JavaScript — HIGH

Multiple JavaScript files inject user-controlled data directly into the DOM via `innerHTML` without sanitization:

- `paper_summarizer/web/static/library.js:17-30` — summary titles and content
- `paper_summarizer/web/static/main.js:206-229` — evidence claims and text
- `paper_summarizer/web/static/batch.js:34-37` — batch results
- `paper_summarizer/web/static/synthesis.js:14-22, 51-53` — synthesis data

A malicious user could store JavaScript in a summary title or evidence claim that executes when any other user views the content. Use `textContent` for plain text or a sanitization library like DOMPurify.

### 2. Hardcoded Default Secret Key — HIGH

`paper_summarizer/web/config.py:14`:
```python
"SECRET_KEY": os.getenv("SECRET_KEY", "dev-secret-change-me"),
```
If deployed without setting `SECRET_KEY`, any attacker knowing the default can forge JWT tokens and impersonate any user. Production must fail to start if no strong secret is provided.

### 3. CI/CD Does Not Block on Failures — HIGH

`.github/workflows/ci.yml` has `continue-on-error: true` on both the lint and test jobs. This means broken code and failing tests merge without any gate. This defeats the purpose of CI entirely.

### 4. No Code Coverage Tracking — MEDIUM

There is no `pytest-cov`, no `.coveragerc`, no coverage thresholds. 32 tests exist across 3 files, but there is no way to know what percentage of the codebase is actually covered or to prevent coverage regressions.

### 5. No Input Validation on Auth Endpoints — MEDIUM

`paper_summarizer/web/auth.py:53-57, 75-79` — The register and login routes accept a raw `dict` with no email format validation and no password strength requirements. Users can register with `email=""` or `password="1"`.

### 6. Missing HTTP Request Timeout — MEDIUM

`paper_summarizer/core/summarizer.py:103`:
```python
response = requests.get(url)
```
No `timeout` parameter. A slow or unresponsive target URL will hang the worker/request thread indefinitely, eventually exhausting server resources.

### 7. No Type Checking Enforcement — MEDIUM

No `mypy` or equivalent configured. Type hints exist in some places but are missing in others (e.g., `auth.py` register/login, `routes.py` helpers). Without enforcement, type annotations are decorative and bugs slip through.

---

## Non-Blocking Issues (Should Fix)

### Code Organization

| Issue | Location | Severity |
|-------|----------|----------|
| `routes.py` is 971 lines with 35 handlers mixing HTML rendering, API logic, and DB operations | `web/routes.py` | Medium |
| `_get_settings()` and `_get_engine()` duplicated identically | `routes.py:51-68`, `auth.py:23-35` | Medium |
| Magic numbers scattered throughout | `config.py:17`, `routes.py:72-75`, `summarizer.py:161` | Low |

### Error Handling

| Issue | Location | Severity |
|-------|----------|----------|
| Bare `except Exception` in 8+ locations catches `KeyboardInterrupt`/`SystemExit` | `summarizer.py:48,85,106,144,163,187`, `auth.py:97`, `worker.py:95` | Medium |
| Unguarded `json.loads` on job results | `routes.py:401` | Low |

### Security Gaps

| Issue | Location | Severity |
|-------|----------|----------|
| No CORS middleware configured | `web/app.py` | Medium |
| Default Grafana admin password hardcoded in compose | `docker-compose.yml` | Low |

### Missing Infrastructure

| Item | Status |
|------|--------|
| Pre-commit hooks (`.pre-commit-config.yaml`) | Missing |
| ESLint for JavaScript | Missing |
| GitHub issue/PR templates | Missing |
| Architecture/deployment runbook | Missing |
| API route docstrings for OpenAPI docs | Missing |

---

## What's Done Well

The project gets many things right:

- **Security headers**: CSP, HSTS, X-Frame-Options, nosniff, Permissions-Policy, CSRF validation via `security.py`
- **SSRF protection**: Private IP/loopback/reserved address blocking in `validation.py`
- **File upload validation**: Size limits, magic byte checks, UTF-8 validation
- **Rate limiting**: Per-IP token bucket in `ratelimit.py`
- **Observability stack**: Prometheus metrics, Grafana dashboards, Sentry integration, request tracing with UUIDs
- **Database migrations**: Alembic with versioned migrations
- **Docker setup**: Multi-service compose with profiles (dev, observability), health checks, slim image
- **Dependency management**: `uv.lock` for reproducibility, Dependabot for automated updates across pip/npm/actions
- **File cleanup**: Temporary uploads properly cleaned in `try/finally` blocks
- **Background jobs**: ARQ worker with Redis for async processing
- **Documentation**: README, SECURITY.md, AGENTS.md with clear guidelines

---

## Recommendations (Priority Order)

1. **Sanitize all `innerHTML` usage** in JS files — use `textContent` or DOMPurify
2. **Fail on missing SECRET_KEY** in production — remove the default fallback
3. **Remove `continue-on-error: true`** from CI workflow
4. **Add `timeout=30`** to all `requests.get()` calls
5. **Add Pydantic schemas** with `EmailStr` and password validation to auth endpoints
6. **Add `pytest-cov`** with a minimum coverage threshold (e.g., 80%)
7. **Configure `mypy`** in `pyproject.toml` and add to CI
8. **Split `routes.py`** into focused modules (html, summaries, jobs, evidence)
9. **Extract shared helpers** (`_get_settings`, `_get_engine`) to a utility module
10. **Replace broad `except Exception`** with specific exception types
11. **Add pre-commit hooks** (black, mypy, ruff)
12. **Add ESLint** for the 11 JavaScript files
