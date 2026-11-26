"""Offline-only local HTTP server (127.0.0.1) for `pixelai studio`."""

from __future__ import annotations

import json
import mimetypes
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from pixelai.studio.api import StudioState, get_palettes_payload, render_studio_payload

STATIC_DIR = Path(__file__).parent / "static"


def make_handler(state: StudioState) -> type[BaseHTTPRequestHandler]:
    class StudioHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return  # keep CLI output clean

        def _send_json(self, data: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            raw = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/api/project":
                self._send_json({
                    "file_path": str(state.file_path) if state.file_path else None,
                    "spec": state.spec,
                })
                return
            if path == "/api/palettes":
                self._send_json(get_palettes_payload())
                return

            rel = "index.html" if path in ("/", "") else path.lstrip("/")
            file_path = (STATIC_DIR / rel).resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                return
            ctype, _ = mimetypes.guess_type(str(file_path))
            raw = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            try:
                body = self._read_json()
                if path == "/api/render":
                    self._send_json(render_studio_payload(body))
                    return
                if path == "/api/save":
                    if "spec" in body:
                        state.spec = body["spec"]
                    saved = state.save(body.get("path"))
                    self._send_json({"saved": str(saved)})
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown API endpoint")
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    return StudioHandler


def run_studio_server(
    file_path: str | Path | None = None,
    *,
    port: int = 5190,
    open_browser: bool = True,
) -> None:
    """Start the offline local Studio server bound strictly to 127.0.0.1."""
    state = StudioState.load(file_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    url = f"http://127.0.0.1:{port}"
    print(f"PixelAI Studio (offline) running at {url} — Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
