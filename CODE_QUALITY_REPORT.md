# Code Quality Report: Paper Summarizer

**Date**: 2026-02-17
**Branch**: claude/evaluate-production-readiness-HwQ0x
**Previous Report**: 2026-02-09

## Project Overview

Paper Summarizer is a FastAPI-based web application for summarizing academic papers using LLMs (T5-Small locally or DeepSeek-R1 via Together AI). It includes user auth with JWT, background job processing (ARQ/Redis), a SQLite/Postgres-backed summary library, batch processing, evidence mapping, synthesis, and an observability stack (Prometheus/Grafana). ~2,700 lines of Python across 25 modules, plus 10 JavaScript files and Jinja2 templates. 100 tests at 80.5% coverage.

---

## Production Readiness Verdict: NEARLY READY

Since the last report (2026-02-09), all 7 original blocking issues have been resolved. The application now has a solid security posture with proper authentication, authorization, input validation, and security headers. However, **5 remaining issues** should be addressed before serving production traffic at scale.

---

## Issues Resolved Since Last Report

| # | Issue | Status |
|---|-------|--------|
| 1 | XSS via `innerHTML` in all frontend JS | **FIXED** — all replaced with `textContent`/`createElement` |
| 2 | Hardcoded default SECRET_KEY | **FIXED** — production validation rejects missing key |
| 3 | CI `continue-on-error: true` | **FIXED** — CI now blocks on failures |
| 4 | No code coverage tracking | **FIXED** — pytest-cov at 80.5%, threshold at 70% |
| 5 | No input validation on auth endpoints | **FIXED** — Pydantic with `EmailStr`, `min_length=8` |
| 6 | Missing HTTP request timeout | **FIXED** — `httpx.Client(timeout=30)` throughout |
| 7 | No type checking | **FIXED** — mypy configured and enforced in CI |
| — | No CORS middleware | **FIXED** — configurable via `CORS_ALLOWED_ORIGINS` |
| — | No rate limiting on auth | **FIXED** — per-email brute-force protection (5 attempts/15 min) |
| — | IDOR on resources | **VERIFIED SAFE** — all routes check `resource.user_id == current_user.id` |
| — | DNS timeout in URL validation | **FIXED** — 5s timeout via `ThreadPoolExecutor` |
| — | Dockerfile runs as root | **FIXED** — runs as `appuser`, build-essential purged |

---

## Remaining Issues

### Blocking (fix before production)

#### 1. No Token Revocation or Refresh — HIGH

`paper_summarizer/web/auth.py` — JWT tokens cannot be invalidated after issuance. There is no logout endpoint on the backend; the frontend simply clears `localStorage`. A stolen token remains valid for the full 24-hour expiration window.

**Impact**: Compromised tokens cannot be revoked.
**Fix**: Implement token blacklist in Redis, add `/auth/logout` endpoint, reduce access token TTL to 15-30 minutes, add refresh token rotation.

#### 2. Missing Database Foreign Key Constraints — HIGH

`paper_summarizer/web/models.py` — `Summary.user_id` and `Job.user_id` have no foreign key constraint to `User.id`. `SummaryEvidence.summary_id` has a FK but no `ondelete="CASCADE"`.

**Impact**: Orphan records accumulate if users or summaries are deleted. No referential integrity at the DB level.
**Fix**: Add an Alembic migration with `op.create_foreign_key()` for both tables, add `ondelete="CASCADE"` to evidence FK.

#### 3. Unbounded Query Results — MEDIUM

- `routes/summaries.py:258` — `/api/summaries/export` loads ALL user summaries with no limit
- `routes/summaries.py:158` — `/api/analytics` loads ALL summaries into memory for aggregation
- `routes/synthesis.py:26` — N+1 query: `[session.get(Summary, id) for id in ids]` instead of `WHERE IN`

**Impact**: Memory exhaustion for users with thousands of summaries.
**Fix**: Add pagination to export, use SQL aggregation for analytics, use `select().where(Summary.id.in_(...))` for synthesis.

### Non-Blocking (should fix)

#### 4. Bare `except Exception` in Rate Limiter — MEDIUM

`paper_summarizer/web/ratelimit.py:81,104` — catches all exceptions including `SystemExit`/`KeyboardInterrupt`. Redis failures at line 81 fail open (allowing unlimited requests), while line 104 fails closed.

**Fix**: Catch `(ConnectionError, TimeoutError, redis.RedisError)` specifically. Choose consistent fail-open or fail-closed behavior.

#### 5. Code Duplication Across Jobs and Worker — MEDIUM

`_complete_job()` is duplicated identically in `routes/jobs.py:38-53` and `worker.py:22-37`. `_run_summary_job()` has similar duplication. Model validation logic (provider check, sentence range) is repeated in 3 files.

**Fix**: Extract shared helpers to `paper_summarizer/web/job_helpers.py`.

---

## Detailed Audit Results

### Security

| Area | Status | Details |
|------|--------|---------|
| Authentication | **Good** | JWT/HS256, bcrypt hashing, token expiration, brute-force protection |
| Authorization (IDOR) | **Good** | All routes verify `resource.user_id == current_user.id`, use 404 not 403 |
| CSRF Protection | **Good** | Origin/Referer validation middleware, port-aware comparison |
| Security Headers | **Good** | CSP, X-Frame-Options: DENY, nosniff, HSTS, Permissions-Policy, COOP, CORP |
| HTTPS Redirect | **Good** | Enabled when `APP_ENV=production`, uses `x-forwarded-proto` |
| SSRF Protection | **Good** | Blocks private IPs, loopback, link-local, port-restricted (80/443), DNS timeout |
| File Upload | **Good** | Extension whitelist, magic byte check, size limit (16MB), UTF-8 validation |
| XSS | **Good** | All `innerHTML` replaced; CSP blocks inline scripts |
| SQL Injection | **Good** | SQLModel ORM throughout, no raw SQL with user input |
| Rate Limiting | **Good** | Per-IP (60/min), per-IP auth (20/min), per-email login (5 attempts/15 min) |
| Token Storage | **Acceptable** | `localStorage` — vulnerable to XSS but CSP mitigates; consider httpOnly cookies |
| Token Revocation | **Missing** | No logout endpoint, no blacklist, 24h TTL too long |

### Database

| Area | Status | Details |
|------|--------|---------|
| ORM | **Good** | SQLModel/SQLAlchemy with parameterized queries |
| Connection Pooling | **Good** | PostgreSQL: pool_size=10, max_overflow=20, pre_ping=True, recycle=1800s |
| Migrations | **Good** | Alembic with 2 versioned migrations, both reversible |
| Indexes | **Good** | user.email (unique), summary.user_id, evidence.summary_id, job.user_id |
| Foreign Keys | **Weak** | Summary.user_id and Job.user_id lack FK constraints |
| Cascade Deletes | **Missing** | Deleting a summary orphans evidence records |
| Pagination | **Partial** | `/api/summaries` paginated (limit=50, max=200); export/analytics unbounded |
| Backup | **Partial** | SQLite backup script exists; no PostgreSQL support |

### Testing & CI

| Area | Status | Details |
|------|--------|---------|
| Test Count | **Good** | 100 tests passing, 8 skipped (torch-dependent) |
| Coverage | **Good** | 80.5% overall, threshold at 70% |
| Coverage Gaps | **Concerning** | `core/summarizer.py` at 36%, `routes/synthesis.py` at 60% |
| CI Pipeline | **Good** | Runs on PR + push to main: black, mypy, pytest |
| Security Tests | **Partial** | Auth & rate limiting tested; CSRF, IDOR, CSP middleware not tested |
| Integration Tests | **Partial** | API-level tests present; no E2E or load tests |
| Dependency Scanning | **Partial** | Dependabot configured; no SAST (bandit/CodeQL) |

### Observability

| Area | Status | Details |
|------|--------|---------|
| Health Check | **Good** | `/health` — deep check: DB `SELECT 1` + Redis ping, returns 503 on failure |
| Prometheus Metrics | **Good** | HTTP request count + latency histogram, 15s scrape interval |
| Grafana Dashboard | **Good** | 7 panels: req/min, p95 latency, error rates, status codes, by-path |
| Request Tracing | **Good** | UUID request IDs via `X-Request-ID` header, propagated in logs |
| Sentry | **Good** | Optional integration via `SENTRY_DSN`, environment-tagged |
| Logging | **Adequate** | Structured extras (request_id, method, path, status, duration_ms); not JSON format |
| Business Metrics | **Missing** | No job queue depth, summarization latency, or user activity metrics |
| Alerting | **Missing** | Prometheus has no alert rules configured |

### Deployment

| Area | Status | Details |
|------|--------|---------|
| Dockerfile | **Good** | python:3.11-slim, non-root user, build deps purged, health check |
| Docker Compose | **Good** | 5 services (app, worker, redis, prometheus, grafana), restart policies |
| Railway | **Good** | `railway.toml` with health check, restart on failure, max 5 retries |
| Resource Limits | **Missing** | No CPU/memory limits in docker-compose |
| Network Isolation | **Missing** | All services on default bridge network |
| Redis Persistence | **Missing** | No AOF/RDB config for Redis data durability |
| Grafana Password | **Weak** | Defaults to `admin` if `GRAFANA_ADMIN_PASSWORD` not set |

### Code Quality

| Area | Status | Details |
|------|--------|---------|
| Project Structure | **Good** | Clear separation: core/, web/routes/, web/static/, tests/ |
| Dependencies | **Good** | All pinned in uv.lock with SHA-256 hashes, Dependabot enabled |
| Type Checking | **Adequate** | mypy configured but `disallow_untyped_defs=false`; `dict[str, Any]` for settings |
| Error Handling | **Adequate** | Specific exceptions in most places; bare `except Exception` in rate limiter |
| API Consistency | **Partial** | `/api/summaries` returns `{items}`, `/api/summaries/export` returns bare array |
| Code Duplication | **Needs Work** | `_complete_job()` duplicated, file upload logic duplicated, model validation repeated in 3 files |

---

## What's Done Well

- **Defense in depth**: Security headers + CSRF + CORS + rate limiting + SSRF protection + input validation
- **IDOR protection**: Every route verifies resource ownership, returns 404 to avoid leaking existence
- **Brute-force protection**: Per-email login attempt tracking with 15-minute lockout
- **Graceful degradation**: Redis rate limiter falls back to in-memory; job queue falls back to background tasks
- **Database pooling**: PostgreSQL pool properly configured with pre_ping, recycle, overflow
- **Observability**: Request ID tracing, Prometheus metrics, Grafana dashboards, optional Sentry
- **File safety**: Upload validation (magic bytes, size, encoding), cleanup in `try/finally`
- **CI/CD**: Linting (black), type checking (mypy), tests with coverage enforcement
- **Dependency management**: Locked versions with hashes, automated updates via Dependabot

---

## Recommended Fix Priority

### Before production launch
1. Add token revocation + reduce TTL (security)
2. Add FK constraints via Alembic migration (data integrity)
3. Add pagination to export/analytics, fix N+1 in synthesis (reliability)

### Soon after launch
4. Narrow rate limiter exception handling (correctness)
5. Extract shared job helpers to eliminate duplication (maintainability)
6. Add Prometheus alerting rules for error rate + latency (operations)
7. Add resource limits to docker-compose (stability)
8. Increase summarizer.py test coverage from 36% (confidence)

### Nice to have
9. Structured JSON logging for log aggregation
10. Distributed tracing (Jaeger/Zipkin)
11. SAST scanning (bandit/CodeQL) in CI
12. API response consistency (always `{items}` not bare arrays)
13. TypedDict for settings instead of `dict[str, Any]`
14. httpOnly cookies instead of localStorage for tokens
