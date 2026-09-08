"""Stripe stand-in for the stranger e2e, CI only.

Implements just enough of the Stripe API for a Checkout to complete without a
key or the network:

* ``POST /v1/checkout/sessions`` -> ``{"id", "url", "payment_status": "unpaid"}``
  (the form body is kept, so the test can assert what the app sent);
* ``GET  /pay/<id>``  -> a minimal hosted-checkout page with one Pay button;
* ``POST /pay/<id>``  -> marks the session paid and redirects to the
  ``success_url`` with ``{CHECKOUT_SESSION_ID}`` substituted, exactly like
  Stripe does;
* ``GET  /v1/checkout/sessions/<id>`` -> the session, ``payment_status: paid``
  once the button was pressed;
* ``GET  /sessions.json`` -> everything it has seen (for assertions).

Usage: ``python3 ci/stub_stripe.py 8766`` and
``STRIPE_API_BASE=http://127.0.0.1:8766/v1 STRIPE_SECRET_KEY=sk_test_ci_stub``.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

SESSIONS: dict[str, dict] = {}
COUNTER = {"n": 0}

PAY_PAGE = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Stripe stand-in</title>
<style>body{font-family:system-ui,sans-serif;padding:32px;max-width:480px;margin:0 auto}
button{font-size:18px;padding:12px 24px;background:#635bff;color:#fff;border:0;border-radius:6px}</style></head>
<body><h1>Stripe stand-in</h1><p>Session <code>{id}</code></p><p>{name} — {amount} {currency}</p>
<form method="post" action="/pay/{id}"><button type="submit" id="pay">Pay {amount} {currency}</button></form>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, body: object) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _body(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return {key: values[0] for key, values in parse_qs(raw).items()}

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/checkout/sessions":
            form = self._body()
            COUNTER["n"] += 1
            session_id = f"cs_test_stub_{COUNTER['n']}"
            host = self.headers.get("Host") or "127.0.0.1"
            session = {
                "id": session_id,
                "object": "checkout.session",
                "url": f"http://{host}/pay/{session_id}",
                "payment_status": "unpaid",
                "status": "open",
                "mode": form.get("mode", "payment"),
                "success_url": form.get("success_url", ""),
                "cancel_url": form.get("cancel_url", ""),
                "amount_total": int(form.get("line_items[0][price_data][unit_amount]", "0") or 0),
                "currency": form.get("line_items[0][price_data][currency]", "chf"),
                "metadata": {
                    key[len("metadata["):-1]: value for key, value in form.items() if key.startswith("metadata[")
                },
                "customer_details": {"email": "stranger@example.com"},
                "_form": form,
            }
            SESSIONS[session_id] = session
            self._json(200, session)
            return
        if self.path.startswith("/pay/"):
            session_id = self.path[len("/pay/"):].split("?", 1)[0]
            session = SESSIONS.get(session_id)
            if not session:
                self._json(404, {"error": "unknown session"})
                return
            session["payment_status"] = "paid"
            session["status"] = "complete"
            target = session["success_url"].replace("{CHECKOUT_SESSION_ID}", session_id)
            self.send_response(303)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/favicon.ico":
            # The browser asks for it on the pay page; a 404 would count as a
            # console error in the e2e.
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path.startswith("/pay/"):
            session_id = self.path[len("/pay/"):].split("?", 1)[0]
            session = SESSIONS.get(session_id)
            if not session:
                self._json(404, {"error": "unknown session"})
                return
            name = session["_form"].get("line_items[0][price_data][product_data][name]", "Test")
            amount = f"{session['amount_total'] / 100:.2f}"
            self._html(
                PAY_PAGE.replace("{id}", session_id)
                .replace("{name}", name)
                .replace("{amount}", amount)
                .replace("{currency}", session["currency"].upper())
            )
            return
        if self.path.startswith("/v1/checkout/sessions/"):
            session = SESSIONS.get(self.path.rsplit("/", 1)[-1])
            if session:
                self._json(200, {k: v for k, v in session.items() if k != "_form"})
            else:
                self._json(404, {"error": "unknown session"})
            return
        if self.path == "/sessions.json":
            self._json(200, SESSIONS)
            return
        self._json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"stub stripe on http://127.0.0.1:{port}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
