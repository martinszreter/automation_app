"""One-off verification for BOARD_HTML v64 ChamDigital rollout section.

Guarded by a unique Agent Bus DONE marker so the redeploy webhook cannot recurse:
first execution verifies live page + bootmode, reports DONE, then invokes the official
portfolio redeploy webhook; the webhook-triggered deployment sees the DONE marker
and exits without invoking another redeploy.
"""
from __future__ import annotations

import json
import urllib.request

BUS_URL = "https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k"
REDEPLOY_URL = "https://startend.app.n8n.cloud/webhook/redeploy-portfolio-7k4q9x"
BOARD_URL = "https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html"
BOOTMODE_URL = "https://portfolio-production-f01d.up.railway.app/bootmode.txt"
MARKER = "HQ_GPT_CHAMDIGITAL_ROLLOUT_20260830"
TIMEOUT = 30


def get_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict) -> object:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def bus_state() -> dict:
    value = json.loads(get_text(BUS_URL))
    if not isinstance(value, dict) or not value.get("bus_cursor"):
        raise RuntimeError("Agent Bus GET did not return a cursor")
    return value


def already_reported(state: dict) -> bool:
    for row in state.get("recent", []):
        if row.get("team") == "GPT_CURSOR" and MARKER in str(row.get("what", "")):
            return True
    return False


def main() -> None:
    state = bus_state()
    if already_reported(state):
        print("VERIFY_GUARD bus DONE already exists; skip redeploy webhook")
        return

    board = get_text(BOARD_URL)
    if "HQ_GPT_CHAMDIGITAL_ROLLOUT_20260830" not in board or "CH proves the machine. AT proves replication. DE scales the winning verticals." not in board:
        raise RuntimeError("live portfolio does not contain the ChamDigital rollout section")
    bootmode = get_text(BOOTMODE_URL).strip()
    if bootmode != "canon":
        raise RuntimeError(f"bootmode is {bootmode!r}, expected 'canon'")
    print("LIVE_VERIFY_OK", len(board), "bootmode", bootmode)

    done = post_json(
        BUS_URL,
        {
            "team": "GPT_CURSOR",
            "project": "4.1",
            "type": "DONE",
            "what": f"{MARKER}: consolidated Grok Swiss census + CH→AT→DE rollout thesis into 00_INITIATIVES v48, 03_DECISIONS v145 and BOARD_HTML v64; live HQ section verified.",
            "next": "Finish Claim 38 product-quality/checkout gate; after it passes, produce the first 20–50 Cham/Ennetsee personalised previews toward 10 paying D-CH customers.",
            "link": BOARD_URL,
            "bus_cursor": state["bus_cursor"],
        },
    )
    print("BUS_DONE_OK", json.dumps(done, ensure_ascii=False)[:500])

    redeploy = post_json(REDEPLOY_URL, {"who": "HQ_GPT", "why": "BOARD_HTML v64"})
    if not isinstance(redeploy, dict) or redeploy.get("serviceInstanceRedeploy") is not True:
        raise RuntimeError(f"official redeploy webhook failed: {redeploy!r}")
    print("REDEPLOY_WEBHOOK_OK", json.dumps(redeploy, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
