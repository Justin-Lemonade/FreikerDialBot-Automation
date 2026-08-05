"""Regression tests for the Mini App readiness fixes:

- The built frontend bundle calls every endpoint under an "/api" prefix
  (confirmed by inspecting index-*.js -- the compiled app's api client
  concatenates a `"/api"` base with paths like `/session/current`).
  These tests lock in that both the prefixed and bare forms resolve to
  the same handler, since test_mini_app_api.py's existing tests already
  cover the bare form and must keep passing unmodified.
- Static file serving for the pre-built frontend (index.html, assets)
  now shares the same port as the API.
- MiniAppService now wires through backend.build_backend() instead of
  constructing Database/StatisticsEngine/SessionManager/QueueEngine
  itself.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from backend import Backend, build_backend
from config import Settings
from database import Database
from mini_app_api import MiniAppAPI, create_service


@pytest.fixture()
def api_server(tmp_path: Path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<div id=\"root\"></div>")

    db_path = tmp_path / "mini_app.db"
    settings = Settings(
        telegram_bot_token="123456:TEST",
        openai_api_key=None,
        mini_app_url=None,
        mini_app_static_dir=static_dir,
    )
    database = Database(db_path)
    backend = build_backend(settings=settings, database=database)
    service = create_service(backend=backend)

    api = MiniAppAPI(service)
    server = api.create_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _request(server, path: str, method: str = "GET", payload: dict | None = None):
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else None), resp.headers
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body), exc.headers
        except json.JSONDecodeError:
            return exc.code, body, exc.headers


class TestApiPrefixRouting:
    """The compiled frontend bundle (index-*.js) calls every endpoint
    with a leading "/api" -- e.g. GET /api/session/current -- which the
    original bare-path-only routing table never matched."""

    def test_prefixed_get_endpoint_matches(self, api_server):
        server, _service = api_server
        status, body, _ = _request(server, "/api/session/current")
        assert status == 200
        assert "sessionId" in body

    def test_bare_get_endpoint_still_matches(self, api_server):
        """Existing callers/tests using the bare path must keep working."""
        server, _service = api_server
        status, body, _ = _request(server, "/session/current")
        assert status == 200
        assert "sessionId" in body

    def test_prefixed_post_endpoint_matches(self, api_server):
        server, service = api_server
        service.database.insert_customers(
            [{"loan_number": "R1", "first_name": "Route", "last_name": "Test",
              "phone_numbers": ["+15550001111"], "balance": "10", "days_overdue": "1"}]
        )
        status, body, _ = _request(server, "/api/session/next", method="POST")
        assert status == 200
        assert body["customer"]["loanNumber"] == "R1"

    def test_unmatched_api_path_returns_404_json_not_static_fallback(self, api_server):
        server, _service = api_server
        status, body, headers = _request(server, "/api/does-not-exist")
        assert status == 404
        assert headers.get("Content-Type") == "application/json"


class TestStaticFileServing:
    """The built frontend (index.html + /assets/*) is served from the
    same port/process as the API, so no separate static server is
    needed to make the Mini App reachable."""

    def test_root_serves_index_html(self, api_server):
        server, _service = api_server
        port = server.server_address[1]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert "text/html" in resp.headers.get("Content-Type", "")
            assert b"<div id=\"root\">" in resp.read()

    def test_unmatched_non_api_path_returns_404_not_index_html(self, api_server):
        """This app has no client-side URL routing -- an unmatched path
        (e.g. a bare, not-yet-implemented API route with no /api
        prefix) must 404, not silently serve the app shell. Silently
        returning 200+HTML here would mask real 404s from callers that
        still use bare paths (see test_mini_app_api.py)."""
        server, _service = api_server
        port = server.server_address[1]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/some/deep/link")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 404

    def test_directory_traversal_is_rejected(self, api_server):
        """Regression test for the static-path containment check: a '..'
        segment must never serve a file outside the static dir. The old
        string-prefix check was bypassable by sibling-directory prefix
        collisions; Path.is_relative_to() resolves this properly."""
        server, service = api_server
        secret = service.backend.settings.mini_app_static_dir.parent / "secret.txt"
        secret.write_text("TOP_SECRET")
        port = server.server_address[1]

        for path in (
            "/../secret.txt",
            "/%2e%2e/secret.txt",
        ):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req, timeout=5)
            assert exc_info.value.code == 404, f"{path} must not serve files outside static dir"


class TestBackendReuse:
    """MiniAppService must be built on top of backend.build_backend(),
    not a second independent construction of the same services."""

    def test_service_exposes_a_backend_instance(self, api_server):
        _server, service = api_server
        assert isinstance(service.backend, Backend)

    def test_service_components_are_the_backends_components(self, api_server):
        _server, service = api_server
        assert service.database is service.backend.database
        assert service.queue_engine is service.backend.queue_engine
        assert service.statistics is service.backend.statistics
        assert service.session_manager is service.backend.session_manager
