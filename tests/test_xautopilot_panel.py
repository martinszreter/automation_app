"""W2-A2: panel calendar, metrics, pause/resume, next invoice, weekly digest."""

from datetime import datetime, time, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services import xautopilot_panel as panel
from app.services.google_oauth import dumps_state
from tests.test_x_autopilot import _client, _mock_db, _plan


# --- pure pieces -------------------------------------------------------------


def test_parse_slots_accepts_the_engine_formats_and_defaults() -> None:
    assert panel.parse_slots("09:00, 13:30") == [time(9, 0), time(13, 30)]
    assert panel.parse_slots("9 13 18") == [time(9, 0), time(13, 0), time(18, 0)]
    assert panel.parse_slots("") == list(panel.DEFAULT_SLOTS_UTC)
    assert panel.parse_slots("25:00 nonsense") == list(panel.DEFAULT_SLOTS_UTC)


def test_calendar_has_seven_days_and_one_post_per_day_by_default() -> None:
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    days = panel.build_calendar(now=now, slots_utc=panel.parse_slots(""), daily_cap=1)

    assert len(days) == 7
    assert sum(len(d.slots) for d in days) == 7
    assert days[0].day.isoformat() == "2026-09-09"
    assert all(slot.status == "scheduled" for d in days for slot in d.slots)
    # 07:00 UTC is 09:00 in Zurich during summer time.
    assert days[0].slots[0].at_local.strftime("%H:%M") == "09:00"


def test_calendar_respects_daily_cap_and_paused_state() -> None:
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    days = panel.build_calendar(now=now, slots_utc=panel.parse_slots("7,11,15"), daily_cap=2, paused=True)
    assert sum(len(d.slots) for d in days) == 14
    assert {slot.status for d in days for slot in d.slots} == {"paused"}


def test_format_chf_uses_swiss_apostrophe_thousands() -> None:
    assert panel.format_chf(139000) == "1'390"
    assert panel.format_chf(24900) == "249"
    assert panel.format_chf(100) == "1"
    assert panel.format_chf(1050) == "10.50"


@pytest.mark.asyncio
async def test_upcoming_invoice_reads_stripe_and_degrades(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        panel,
        "stripe_request",
        AsyncMock(return_value={"amount_due": 24900, "currency": "chf", "next_payment_attempt": 1760000000}),
    )
    invoice = await panel.upcoming_invoice("sub_1")
    assert invoice["amount_due_cents"] == 24900 and invoice["currency"] == "CHF" and invoice["due_at"]

    assert await panel.upcoming_invoice(None) is None
    monkeypatch.setattr(panel, "stripe_request", AsyncMock(side_effect=panel.StripeError("boom")))
    assert await panel.upcoming_invoice("sub_1") is None


@pytest.mark.asyncio
async def test_lane_call_needs_a_url_and_handles_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "n8n_xa_panel_url", "")
    with pytest.raises(panel.PanelLaneNotConfigured):
        await panel.lane_call("profile", email="x@y.ch")

    monkeypatch.setattr(settings, "n8n_xa_panel_url", "https://n8n.invalid/webhook/xa-panel")

    class FakeResponse:
        def __init__(self, status: int, payload: dict) -> None:
            self.status_code = status
            self._payload = payload
            self.text = "x"

        def json(self) -> dict:
            return self._payload

    calls: list[dict] = []

    def client_answering(status: int, payload: dict) -> type:
        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self) -> "FakeClient":
                return self

            async def __aexit__(self, *args) -> bool:
                return False

            async def post(self, url: str, json: dict) -> FakeResponse:
                calls.append(json)
                return FakeResponse(status, payload)

        return FakeClient

    monkeypatch.setattr("app.services.xautopilot_panel.httpx.AsyncClient", client_answering(200, {"found": True, "agent": {"agent_name": "beiz"}}))
    assert await panel.lane_profile(email="Kunde@Example.ch") == {"agent_name": "beiz"}
    assert calls[-1] == {"action": "profile", "email": "kunde@example.ch", "agent": ""}

    monkeypatch.setattr("app.services.xautopilot_panel.httpx.AsyncClient", client_answering(500, {}))
    with pytest.raises(panel.PanelLaneError):
        await panel.lane_recent_posts("beiz")


@pytest.mark.asyncio
async def test_load_panel_data_without_a_lane_still_builds_the_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "n8n_xa_panel_url", "")
    monkeypatch.setattr(panel, "upcoming_invoice", AsyncMock(return_value=None))
    data = await panel.load_panel_data(_plan(), now=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))

    assert data.agent is None and data.posts == [] and data.lane_error is None
    assert data.scheduled_count == 7 and not data.paused


def test_digest_text_is_german_and_counts_the_week() -> None:
    plan = _plan()
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    posts = [
        {"text": "Neu diese Woche.", "posted_at": "2026-09-05T08:00:00+00:00", "impressions": 120, "likes": 4},
        {"text": "Alt.", "posted_at": "2026-08-01T08:00:00+00:00", "impressions": 9, "likes": 0},
    ]
    subject, body = digest = panel.digest_text(plan, posts, scheduled=7, panel_url="https://x.test/panel", now=now)

    assert subject == "X Autopilot — Ihre Woche: 1 Posts"
    assert "Neu diese Woche." in body and "Alt." not in body
    assert "120 Impressionen" in body and "Geplant für die nächsten 7 Tage: 7 Posts." in body
    assert "Status: aktiv." in body and "ß" not in body
    assert digest


# --- routes ------------------------------------------------------------------


async def _signed_in_panel(monkeypatch: pytest.MonkeyPatch, plan, *, method: str = "GET", path: str = "/x-autopilot/panel"):
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr("app.api.x_autopilot.google_oauth.exchange_code", AsyncMock(return_value={"access_token": "ya29.token"}))
    monkeypatch.setattr(
        "app.api.x_autopilot.google_oauth.fetch_userinfo",
        AsyncMock(return_value={"email": plan.email, "name": "Buyer", "sub": "123"}),
    )
    monkeypatch.setattr("app.api.x_autopilot.get_active_plan_for_email", AsyncMock(return_value=plan))
    monkeypatch.setattr("app.api.x_autopilot.google_oauth.read_sheet_values", AsyncMock(return_value={"row_count": 0, "rows": []}))
    state = dumps_state({"purpose": "login", "checkout": ""})
    db = _mock_db(existing=plan)
    async with _client(db) as client:
        await client.get("/x-autopilot/auth/google/callback", params={"code": "auth-code", "state": state})
        if method == "GET":
            return await client.get(path), db
        return await client.post(path), db


@pytest.mark.asyncio
async def test_panel_shows_seven_scheduled_posts_metrics_and_next_invoice(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    plan.stripe_subscription_id = "sub_1"
    monkeypatch.setattr(
        "app.services.xautopilot_panel.lane_profile",
        AsyncMock(return_value={"agent_name": "beiz", "handle": "@beiz", "post_slot": "07:00", "daily_cap": 1}),
    )
    monkeypatch.setattr(
        "app.services.xautopilot_panel.lane_recent_posts",
        AsyncMock(return_value=[{"text": "Ein leerer Tisch kostet CHF 260.", "posted_at": "2026-09-01T08:00:00+00:00", "impressions": 1200, "likes": 14}]),
    )
    monkeypatch.setattr(
        "app.services.xautopilot_panel.upcoming_invoice",
        AsyncMock(return_value={"amount_due_cents": 24900, "currency": "CHF", "due_at": datetime(2026, 10, 1, tzinfo=timezone.utc)}),
    )

    response, db = await _signed_in_panel(monkeypatch, plan)

    assert response.status_code == 200
    assert response.text.count('data-testid="scheduled-post"') == 7
    assert "Plan aktiv" in response.text and "@beiz" in response.text
    assert "1200" in response.text and "Ein leerer Tisch" in response.text
    assert "CHF 249" in response.text and "01.10.2026" in response.text
    assert 'data-testid="pause-button"' in response.text
    assert plan.agent_name == "beiz"  # learned from the lane and persisted
    db.commit.assert_awaited()
    assert "ß" not in response.text


@pytest.mark.asyncio
async def test_panel_survives_a_dead_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    monkeypatch.setattr("app.services.xautopilot_panel.lane_profile", AsyncMock(side_effect=panel.PanelLaneError("down")))
    monkeypatch.setattr("app.services.xautopilot_panel.upcoming_invoice", AsyncMock(return_value=None))

    response, _db = await _signed_in_panel(monkeypatch, plan)

    assert response.status_code == 200
    assert response.text.count('data-testid="scheduled-post"') == 7
    assert "gerade nicht erreichbar" in response.text
    assert "keine (Einmalzahlung)" in response.text


@pytest.mark.asyncio
async def test_pause_marks_the_plan_and_tells_the_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    plan.agent_name = "beiz"
    set_status = AsyncMock(return_value=True)
    monkeypatch.setattr("app.api.x_autopilot.set_agent_status", set_status)

    response, db = await _signed_in_panel(monkeypatch, plan, method="POST", path="/x-autopilot/panel/pause")

    assert response.status_code == 303 and response.headers["location"] == "/x-autopilot/panel"
    assert plan.paused_at is not None
    set_status.assert_awaited_once_with("beiz", paused=True)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_paused_panel_shows_paused_slots_and_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    plan.paused_at = datetime(2026, 9, 8, tzinfo=timezone.utc)
    monkeypatch.setattr(settings, "n8n_xa_panel_url", "")
    monkeypatch.setattr("app.services.xautopilot_panel.upcoming_invoice", AsyncMock(return_value=None))

    response, _db = await _signed_in_panel(monkeypatch, plan)

    assert 'data-testid="plan-paused"' in response.text
    assert response.text.count('data-status="paused"') == 7
    assert 'data-testid="resume-button"' in response.text


@pytest.mark.asyncio
async def test_resume_clears_the_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    plan.paused_at = datetime(2026, 9, 8, tzinfo=timezone.utc)
    monkeypatch.setattr(settings, "n8n_xa_panel_url", "")

    response, _db = await _signed_in_panel(monkeypatch, plan, method="POST", path="/x-autopilot/panel/resume")

    assert response.status_code == 303
    assert plan.paused_at is None


@pytest.mark.asyncio
async def test_e2e_login_is_404_without_key_and_signs_in_with_it(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan()
    monkeypatch.setattr("app.api.x_autopilot.ensure_e2e_plan", AsyncMock(return_value=plan))
    monkeypatch.setattr("app.api.x_autopilot.get_active_plan_for_email", AsyncMock(return_value=plan))
    monkeypatch.setattr(settings, "n8n_xa_panel_url", "")
    monkeypatch.setattr("app.services.xautopilot_panel.upcoming_invoice", AsyncMock(return_value=None))
    monkeypatch.setattr("app.api.x_autopilot.google_oauth.read_sheet_values", AsyncMock(return_value={"row_count": 0, "rows": []}))

    monkeypatch.setattr(settings, "xa_e2e_key", "")
    async with _client(_mock_db(existing=plan)) as client:
        assert (await client.get("/x-autopilot/e2e/login", params={"key": "k", "email": plan.email})).status_code == 404

    monkeypatch.setattr(settings, "xa_e2e_key", "e2e-key")
    async with _client(_mock_db(existing=plan)) as client:
        wrong = await client.get("/x-autopilot/e2e/login", params={"key": "nope", "email": plan.email})
        login = await client.get("/x-autopilot/e2e/login", params={"key": "e2e-key", "email": plan.email})
        panel_page = await client.get("/x-autopilot/panel")

    assert wrong.status_code == 404
    assert login.status_code == 303 and login.headers["location"] == "/x-autopilot/panel"
    assert panel_page.status_code == 200
    assert panel_page.text.count('data-testid="scheduled-post"') == 7


@pytest.mark.asyncio
async def test_digest_run_mails_each_active_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "judge-secret")
    active = _plan()
    active.agent_name = "beiz"
    paused = _plan()
    paused.email = "paused@example.com"
    paused.paused_at = datetime(2026, 9, 8, tzinfo=timezone.utc)
    monkeypatch.setattr("app.api.x_autopilot.list_active_plans", AsyncMock(return_value=[active, paused]))
    monkeypatch.setattr("app.api.x_autopilot.lane_recent_posts", AsyncMock(return_value=[{"text": "Hallo", "posted_at": "2026-09-07T08:00:00+00:00"}]))
    monkeypatch.setattr("app.services.xautopilot_panel.lane_profile", AsyncMock(return_value=None))
    monkeypatch.setattr("app.services.xautopilot_panel.upcoming_invoice", AsyncMock(return_value=None))
    sent = AsyncMock()
    monkeypatch.setattr("app.api.x_autopilot.send_hq_mail", sent)

    async with _client(_mock_db()) as client:
        response = await client.post("/x-autopilot/digest/run", headers={"X-Judge-Key": "judge-secret"})

    assert response.status_code == 200
    assert response.json() == {"sent": 2, "skipped": []}
    recipients = {call.kwargs["to"] for call in sent.await_args_list}
    assert recipients == {"buyer@example.com", "paused@example.com"}
    bodies = [call.args[1] for call in sent.await_args_list]
    assert any("Status: pausiert" in b for b in bodies) and any("Status: aktiv." in b for b in bodies)
