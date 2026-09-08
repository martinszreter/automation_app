"""Stand-in for the canon RW webhook and the bus read-state URL, for CI only.

The real canon is an n8n webhook whose URL is a write key and therefore lives
only in the Railway environment. CI cannot (and must not) reach it, so this
tiny server answers the two reads ``boot/views_boot.py`` makes:

* ``POST /`` with ``{"action": "read", "keyValue": KEY}`` -> one canon row
  whose ``content`` is ``ci/fixtures/<KEY>.html`` (404 when no fixture);
* ``GET /bus`` -> an empty-but-valid bus state, so the bus page renders
  without console errors.

Usage: ``python3 ci/stub_canon.py 8765`` then
``CANON_RW_URL=http://127.0.0.1:8765/ BUS_STATE_URL=http://127.0.0.1:8765/bus``.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 — http.server API
        if self.path.startswith("/bus"):
            self._send(
                200,
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "counts": {"total": 0},
                    "retention": "ci",
                    "open_claims": [],
                    "open_asks": [],
                    "recent": [],
                    "recent_by_team": {},
                    "bus_cursor": "ci",
                },
            )
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 — http.server API
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "bad json"})
            return
        key = str(request.get("keyValue") or "")
        if request.get("action") != "read" or not key:
            self._send(404, {"error": f"unsupported request for {key!r}"})
            return
        fixture = FIXTURES / f"{key}.html"
        if fixture.is_file():
            content = fixture.read_text(encoding="utf-8")
        else:
            # Views without a dedicated fixture get a generic page, so the
            # whole boot script exits 0 in CI like it does on Railway.
            content = (FIXTURES / "_generic.html").read_text(encoding="utf-8").replace("__KEY__", key)
        self._send(200, [{"id": 1, "file": key, "version": 1, "content": content}])

    def log_message(self, fmt: str, *args: object) -> None:  # quiet
        return


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"stub canon on http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
