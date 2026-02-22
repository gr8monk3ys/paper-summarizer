# Brutally Honest Repo Review (2026-02-18)

## TL;DR

This repo is **better than average for an indie FastAPI app**, but it still has a few sharp edges that will hurt if usage grows or if multiple contributors start landing changes quickly.

## What is genuinely solid

- **Test baseline is healthy**: `100 passed, 8 skipped` with **74.52%** coverage, above the configured 70% gate.
- **Architecture is clear**: separation between core summarization logic and web routes is straightforward to navigate.
- **Auth/security fundamentals are present**: JWT with expiry + JTI, login throttling, logout endpoint, request validation.
- **Operational basics exist**: migrations, Redis worker path, Prometheus/Grafana wiring, Docker/compose setup.

## Hard truths

### 1) The project has an accuracy debt in documentation

`CODE_QUALITY_REPORT.md` is stale and now materially inaccurate in several places:

- It says token revocation/logout is missing, but `/auth/logout` and a JTI blacklist are implemented.
- It says foreign keys are missing for `Summary.user_id` and `Job.user_id`, but both currently define `foreign_key="user.id"`.
- It reports old coverage numbers and now-mismatched readiness conclusions.

This kind of drift erodes trust quickly because new contributors cannot rely on audit docs.

### 2) Coverage passes, but risk is concentrated in the core product path

Current coverage hotspots are still weak in areas that matter most:

- `core/summarizer.py`: 29%
- `routes/synthesis.py`: 54%
- `routes/evidence.py`: 57%

So the quality gate is met, but confidence is uneven where feature complexity is highest.

### 3) Tooling is inconsistent with the repo narrative

- The repository includes mypy config, but does not enforce strict typed defs (`disallow_untyped_defs = false`).
- There is no formatter/linter config in `pyproject.toml` even though historical docs mention style checks in CI.
- This increases style drift and review friction over time.

### 4) API shape consistency is still rough

- `/api/summaries` returns an envelope (`items`, paging metadata).
- `/api/summaries/export` returns a bare array.

That inconsistency is survivable now, but becomes painful for frontend and SDK users as endpoints expand.

### 5) There is still duplication in route/worker flows

Job completion and summarization orchestration still have overlapping logic in API routes and worker codepaths. It is not catastrophic today, but it raises bug-fix cost and makes behavior drift likely.

## Prioritized fixes (highest ROI first)

1. **Repair trust in docs**: update/remove stale `CODE_QUALITY_REPORT.md` claims and add a lightweight “last verified” process.
2. **Raise confidence where it matters**: target tests for `core/summarizer.py`, synthesis, and evidence routes first.
3. **Normalize response contracts**: pick a consistent envelope convention for list/export APIs.
4. **Reduce duplication**: extract shared job completion helpers used by both web routes and worker.
5. **Tighten typing/lint posture**: move incrementally toward stricter mypy and add a formatter/linter policy.

## Bottom line

If this were a startup MVP, I would call it **ship-capable with guardrails**.

If this were expected to support a team and steady production growth, I’d call it **one or two focused hardening cycles away from “boringly reliable.”**
