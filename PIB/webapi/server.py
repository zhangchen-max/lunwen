from __future__ import annotations

import argparse
import mimetypes
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from webapi import artifacts as artifact_service
from webapi import oauth_bridge
from webapi.routes import cases as case_routes
from webapi.routes import releases as release_routes
from webapi.routes import runs as run_routes

REPO_ROOT = Path(__file__).resolve().parents[1]


def _oauth_error_status(code: str) -> int:
    if code == "timeout":
        return HTTPStatus.GATEWAY_TIMEOUT
    if code in {"provider_unavailable", "transport_error"}:
        return HTTPStatus.SERVICE_UNAVAILABLE
    if code in {"invalid_chat_payload", "oauth_auth_missing", "oauth_auth_invalid", "oauth_auth_mode_invalid"}:
        return HTTPStatus.BAD_REQUEST
    return HTTPStatus.BAD_GATEWAY


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def create_handler(repo_root: Path | None = None) -> type[BaseHTTPRequestHandler]:
    repo_root = repo_root or REPO_ROOT

    class Handler(BaseHTTPRequestHandler):
        server_version = "PIBWebAPI/0.1"

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _write_file(self, path: Path) -> None:
            body = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # pragma: no cover - trivial
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = parse_qs(parsed.query)
            if path == "/v1/models":
                try:
                    self._write_json(HTTPStatus.OK, oauth_bridge.list_models())
                except oauth_bridge.OAuthBridgeError as exc:
                    self._write_json(_oauth_error_status(exc.code), {"error": {"code": exc.code, "message": exc.message, "details": None, "retryable": exc.code in {"timeout", "provider_unavailable", "transport_error"}}})
                return
            if path == "/api/releases":
                status, payload = release_routes.get_releases(repo_root=repo_root)
                self._write_json(status, payload)
                return
            if path == "/api/runs/options":
                status, payload = run_routes.get_run_options(repo_root=repo_root)
                self._write_json(status, payload)
                return
            if path.startswith("/api/jobs/"):
                job_id = path.removeprefix("/api/jobs/")
                status, payload = release_routes.get_job(job_id, repo_root=repo_root)
                self._write_json(status, payload)
                return
            if path.startswith("/api/runs/"):
                if path.endswith("/slices"):
                    run_id = path.removeprefix("/api/runs/").removesuffix("/slices")
                    status, payload = case_routes.get_run_slices(run_id, repo_root=repo_root)
                    self._write_json(status, payload)
                    return
                if "/cases/" in path:
                    run_id, case_id = path.removeprefix("/api/runs/").split("/cases/", 1)
                    status, payload = case_routes.get_run_case_detail(run_id, case_id, repo_root=repo_root)
                    self._write_json(status, payload)
                    return
                if path.endswith("/cases"):
                    run_id = path.removeprefix("/api/runs/").removesuffix("/cases")
                    filters = {
                        'module': (query.get('module') or [None])[0],
                        'label': (query.get('label') or [None])[0],
                        'ambiguity': (query.get('ambiguity') or [None])[0],
                        'required_svcl_domains_count': (query.get('required_svcl_domains_count') or [None])[0],
                        'failure_bucket': (query.get('failure_bucket') or [None])[0],
                        'risk_positive': (query.get('risk_positive') or [None])[0],
                        'personality_spectrum': (query.get('personality_spectrum') or [None])[0],
                        'timeout_affected': (query.get('timeout_affected') or [None])[0],
                        'parse_affected': (query.get('parse_affected') or [None])[0],
                        'protocol_clean_only': (query.get('protocol_clean_only') or [None])[0],
                        'failure_source': (query.get('failure_source') or [None])[0],
                        'limit': (query.get('limit') or [None])[0],
                        'offset': (query.get('offset') or [None])[0],
                    }
                    status, payload = case_routes.get_run_cases(run_id, filters, repo_root=repo_root)
                    self._write_json(status, payload)
                    return
                if path.endswith("/summary"):
                    run_id = path.removeprefix("/api/runs/").removesuffix("/summary")
                    status, payload = run_routes.get_run_summary(run_id, repo_root=repo_root)
                    self._write_json(status, payload)
                    return
                if path.endswith("/artifacts/download"):
                    run_id = path.removeprefix("/api/runs/").removesuffix("/artifacts/download")
                    run_status, _ = run_routes.get_run(run_id, repo_root=repo_root)
                    if run_status != HTTPStatus.OK:
                        self._write_json(HTTPStatus.NOT_FOUND, {"error": {"code": "run_not_found", "message": f"Unknown run_id: {run_id}", "details": None, "retryable": False}})
                        return
                    requested_path = (query.get("path") or [None])[0]
                    try:
                        resolved = artifact_service.resolve_download_path(requested_path or "", repo_root=repo_root)
                    except artifact_service.ArtifactPathNotAllowedError as exc:
                        self._write_json(HTTPStatus.BAD_REQUEST, {"error": {"code": "artifact_path_not_allowed", "message": exc.message, "details": None, "retryable": False}})
                        return
                    except artifact_service.ArtifactNotFoundError as exc:
                        self._write_json(HTTPStatus.NOT_FOUND, {"error": {"code": "artifact_not_found", "message": exc.message, "details": None, "retryable": False}})
                        return
                    self._write_file(resolved)
                    return
                if path.endswith("/artifacts"):
                    run_id = path.removeprefix("/api/runs/").removesuffix("/artifacts")
                    status, payload = run_routes.get_run_artifacts(run_id, repo_root=repo_root)
                    self._write_json(status, payload)
                    return
                run_id = path.removeprefix("/api/runs/")
                status, payload = run_routes.get_run(run_id, repo_root=repo_root)
                self._write_json(status, payload)
                return
            if path.startswith("/api/releases/"):
                release_id = path.removeprefix("/api/releases/")
                status, payload = release_routes.get_release_detail(release_id, repo_root=repo_root)
                self._write_json(status, payload)
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": {"code": "not_found", "message": "Route not found", "details": None, "retryable": False}})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except json.JSONDecodeError:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": {"code": "invalid_json", "message": "Request body must be valid JSON", "details": None, "retryable": False}},
                )
                return
            if path == "/api/releases/validate-current":
                status, payload = release_routes.post_validate_current(repo_root=repo_root)
                self._write_json(status, payload)
                return
            if path == "/api/releases/freeze-current":
                status, payload = release_routes.post_freeze_current(repo_root=repo_root)
                self._write_json(status, payload)
                return
            if path == "/api/runs":
                status, response = run_routes.post_run(payload, repo_root=repo_root)
                self._write_json(status, response)
                return
            if path == "/v1/chat/completions":
                try:
                    response = oauth_bridge.chat_completion(payload, repo_root=repo_root)
                    self._write_json(HTTPStatus.OK, response)
                except oauth_bridge.OAuthBridgeError as exc:
                    self._write_json(_oauth_error_status(exc.code), {"error": {"code": exc.code, "message": exc.message, "details": None, "retryable": exc.code in {"timeout", "provider_unavailable", "transport_error"}}})
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": {"code": "not_found", "message": "Route not found", "details": None, "retryable": False}})

        def log_message(self, fmt: str, *args: Any) -> None:  # pragma: no cover - silence tests
            return

    return Handler


def create_server(host: str = "127.0.0.1", port: int = 8780, repo_root: Path | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), create_handler(repo_root=repo_root))


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the PIB product-layer web API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()
    os.environ["PIB_WEBAPI_BASE_URL"] = f"http://{args.host}:{args.port}"
    server = create_server(host=args.host, port=args.port)
    print(f"PIB webapi serving on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
