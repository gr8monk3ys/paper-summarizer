"""Tests for the security middleware module.

Covers the three middlewares in ``paper_summarizer.web.security``:
HTTPS redirect, security headers, and CSRF origin validation. Each is
mounted on a minimal Starlette app and exercised via ``TestClient`` so
the tests stay isolated from the LLM/database stack.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from paper_summarizer.web.security import (
    CSRFMiddleware,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
)


def _make_app(middleware_cls, **kwargs) -> Starlette:
    """Build a tiny app with a couple of routes wrapped by ``middleware_cls``."""

    async def ok(request):  # noqa: ANN001
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/thing", ok, methods=["GET", "POST", "PUT", "PATCH", "DELETE"]),
            Route("/auth/login", ok, methods=["POST"]),
            Route("/static/x", ok, methods=["POST"]),
        ]
    )
    app.add_middleware(middleware_cls, **kwargs)
    return app


# ---------------------------------------------------------------------------
# HTTPSRedirectMiddleware
# ---------------------------------------------------------------------------


class TestHTTPSRedirectMiddleware:
    def _client(self) -> TestClient:
        return TestClient(_make_app(HTTPSRedirectMiddleware))

    def test_redirects_http_forwarded_proto(self):
        resp = self._client().get(
            "/thing",
            headers={"x-forwarded-proto": "http"},
            follow_redirects=False,
        )
        assert resp.status_code == 301
        assert resp.headers["location"].startswith("https://")

    def test_passes_through_when_https(self):
        resp = self._client().get(
            "/thing", headers={"x-forwarded-proto": "https"}
        )
        assert resp.status_code == 200
        assert resp.text == "ok"

    def test_passes_through_without_header(self):
        resp = self._client().get("/thing")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class TestSecurityHeadersMiddleware:
    def test_sets_baseline_headers(self):
        client = TestClient(_make_app(SecurityHeadersMiddleware, app_env="development"))
        resp = client.get("/thing")
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
        assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_hsts_only_in_production(self):
        dev = TestClient(_make_app(SecurityHeadersMiddleware, app_env="development"))
        assert "Strict-Transport-Security" not in dev.get("/thing").headers

        prod = TestClient(_make_app(SecurityHeadersMiddleware, app_env="production"))
        prod_headers = prod.get("/thing").headers
        assert "Strict-Transport-Security" in prod_headers
        assert "max-age=31536000" in prod_headers["Strict-Transport-Security"]


# ---------------------------------------------------------------------------
# CSRFMiddleware
# ---------------------------------------------------------------------------


class TestCSRFMiddleware:
    def _client(self, **kwargs) -> TestClient:
        return TestClient(_make_app(CSRFMiddleware, **kwargs))

    def test_safe_methods_never_checked(self):
        # GET is not state-changing, so a mismatched origin is irrelevant.
        resp = self._client().get(
            "/thing", headers={"origin": "http://evil.example"}
        )
        assert resp.status_code == 200

    def test_post_without_origin_allowed(self):
        # No Origin/Referer header -> nothing to validate against, allowed.
        resp = self._client().post("/thing")
        assert resp.status_code == 200

    def test_post_matching_origin_allowed(self):
        resp = self._client().post(
            "/thing",
            headers={"origin": "http://testserver", "host": "testserver"},
        )
        assert resp.status_code == 200

    def test_post_mismatched_origin_rejected(self):
        resp = self._client().post(
            "/thing",
            headers={"origin": "http://evil.example", "host": "testserver"},
        )
        assert resp.status_code == 403
        assert resp.json() == {"error": "Invalid origin"}

    def test_port_aware_mismatch_rejected(self):
        # Same host but different port must be treated as a mismatch.
        resp = self._client().post(
            "/thing",
            headers={"origin": "http://localhost:3000", "host": "localhost:8000"},
        )
        assert resp.status_code == 403

    def test_referer_used_when_origin_absent(self):
        resp = self._client().post(
            "/thing",
            headers={"referer": "http://evil.example/page", "host": "testserver"},
        )
        assert resp.status_code == 403

    def test_exempt_auth_path_skips_check(self):
        resp = self._client().post(
            "/auth/login",
            headers={"origin": "http://evil.example", "host": "testserver"},
        )
        assert resp.status_code == 200

    def test_exempt_static_path_skips_check(self):
        resp = self._client().post(
            "/static/x",
            headers={"origin": "http://evil.example", "host": "testserver"},
        )
        assert resp.status_code == 200

    def test_custom_exempt_paths_override_default(self):
        # With a custom exempt list, the default auth path is no longer exempt.
        client = self._client(exempt_paths=("/thing",))
        rejected = client.post(
            "/auth/login",
            headers={"origin": "http://evil.example", "host": "testserver"},
        )
        assert rejected.status_code == 403

        allowed = client.post(
            "/thing",
            headers={"origin": "http://evil.example", "host": "testserver"},
        )
        assert allowed.status_code == 200
