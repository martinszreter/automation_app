"""W2-A1: post quality judge — 30 fixture posts, veto reasons recorded, best pick."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services import xautopilot_generate as xa_gen
from app.services import xautopilot_judge as judge
from app.services.xautopilot_judge import (
    RecentPost,
    ToneProfile,
    detect_language,
    judge_post,
    parse_posted_at,
    pick_best,
    similarity,
    x_length,
)

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "xautopilot_posts.json").read_text("utf-8"))
NOW = datetime.fromisoformat(FIXTURES["now"])
RECENT = [RecentPost(p["text"], parse_posted_at(p["posted_at"])) for p in FIXTURES["recent_posts"]]
POSTS = FIXTURES["posts"]


def _profile(language: str) -> ToneProfile:
    return ToneProfile(customer="beiz", language=language, banned_terms=["Wunderdiät, Abnehmwunder"], max_hashtags=2)


# --- the 30 fixture posts ----------------------------------------------------


def test_fixture_has_thirty_posts() -> None:
    assert len(POSTS) == 30
    assert len({p["id"] for p in POSTS}) == 30


@pytest.mark.parametrize("post", POSTS, ids=[f"post-{p['id']}" for p in POSTS])
def test_fixture_post_gets_exactly_the_expected_vetoes(post: dict) -> None:
    report = judge_post(post["text"], _profile(post["language"]), RECENT, now=NOW)

    assert sorted({v.code for v in report.vetoes}) == sorted(set(post["expected"])), report.vetoes
    assert report.ok is (not post["expected"])
    for veto in report.vetoes:
        assert veto.detail, "every veto carries a reason"
    if report.ok:
        assert report.score > 0
    else:
        assert report.score == 0.0


def test_fixture_covers_every_veto_code() -> None:
    seen = {code for p in POSTS for code in p["expected"]}
    assert seen == {"too_long", "spam", "banned_claim", "wrong_language", "duplicate"}


def test_vetoes_are_logged_one_json_line_each(caplog: pytest.LogCaptureFixture) -> None:
    profile = _profile("de")
    reports = [judge_post(p["text"], profile, RECENT, now=NOW) for p in POSTS]
    expected_vetoes = sum(len(r.vetoes) for r in reports)
    assert expected_vetoes >= 12

    with caplog.at_level(logging.INFO, logger="app.services.xautopilot_judge"):
        rows = judge.veto_rows(profile, reports)
        for row in rows:
            judge.logger.info("xa_judge_veto %s", json.dumps(row, ensure_ascii=False))

    lines = [rec.getMessage() for rec in caplog.records if rec.getMessage().startswith("xa_judge_veto ")]
    assert len(lines) == expected_vetoes == len(rows)
    parsed = json.loads(lines[0].split(" ", 1)[1])
    assert {"customer", "code", "detail", "text", "created_at"} <= set(parsed)


# --- rules in isolation ------------------------------------------------------


def test_x_length_counts_links_as_23_and_emoji_as_2() -> None:
    assert x_length("abc") == 3
    assert x_length("see https://example.com/a/very/long/path/indeed") == len("see ") + 23
    assert x_length("🔥") == 2


def test_language_vote_and_weak_votes() -> None:
    assert detect_language("Die Kunden kaufen nicht das Produkt, sie kaufen die Lösung für ihr Problem.")[0] == "de"
    assert detect_language("The customers do not buy the product, they buy the solution to their problem.")[0] == "en"
    assert detect_language("CHF 1'390")[0] is None


def test_similarity_and_duplicate_window() -> None:
    a = "Preise runden nach oben, nicht nach unten. Das sieht nach einer Entscheidung aus."
    assert similarity(a, a) == 1.0
    assert similarity(a, "Völlig anderer Text über etwas ganz anderes, ohne jede Überschneidung hier.") < 0.2

    old = RecentPost(a, datetime(2026, 1, 1, tzinfo=timezone.utc))
    fresh = RecentPost(a, datetime(2026, 9, 7, tzinfo=timezone.utc))
    assert judge.check_duplicate(a, [old], now=NOW) is None
    assert judge.check_duplicate(a, [fresh], now=NOW) is not None
    # An unknown posted_at is treated as recent (safer to veto than to repeat).
    assert judge.check_duplicate(a, [RecentPost(a, None)], now=NOW) is not None


def test_customer_banned_terms_are_split_and_case_insensitive() -> None:
    profile = ToneProfile(language="de", banned_terms=["Wunderdiät; ABNEHMWUNDER", "Kalorienbombe"])
    assert judge.check_banned_claims("Das neue abnehmwunder ist da", profile).code == "banned_claim"
    assert judge.check_banned_claims("Eine Kalorienbombe zum Zmittag", profile) is not None
    assert judge.check_banned_claims("Ein normaler Satz über Preise", profile) is None


def test_language_rule_is_off_for_unknown_profile_language() -> None:
    assert judge.check_language("The customers do not buy the product at all.", ToneProfile(language="xx")) is None


# --- best pick ---------------------------------------------------------------


def test_pick_best_skips_vetoed_variants_and_prefers_concrete_copy() -> None:
    profile = _profile("de")
    weak = "Ich finde, dass Reservierungen per WhatsApp irgendwie ganz praktisch sind."
    strong = "Ein leerer Tisch am Samstag kostet CHF 260. Eine Erinnerung am Vortag kostet einen Rappen.\n\nWelche Zahl ist grösser?"
    spam = "JETZT RESERVIEREN!!! #gastro #zürich #whatsapp #jetzt #reservation"

    best, reports = pick_best([weak, spam, strong], profile, RECENT, now=NOW)

    assert best is not None and best.text == strong
    assert [r.ok for r in reports] == [True, False, True]
    assert reports[1].vetoes[0].code == "spam"


def test_pick_best_returns_none_when_everything_is_vetoed() -> None:
    best, reports = pick_best(["JETZT!!! KAUFEN!!!", ""], _profile("de"))
    assert best is None
    assert all(not r.ok for r in reports)


# --- veto ledger webhook -----------------------------------------------------


@pytest.mark.asyncio
async def test_record_vetoes_posts_rows_to_n8n_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "n8n_xa_veto_log_url", "https://n8n.invalid/webhook/vetoes")
    posted: dict = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url: str, json: dict) -> FakeResponse:
            posted["url"] = url
            posted["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.xautopilot_judge.httpx.AsyncClient", FakeClient)
    reports = [judge_post("JETZT KAUFEN!!! Folge mir", _profile("de"))]

    count = await judge.record_vetoes(_profile("de"), reports)

    assert count == len(posted["json"]["vetoes"]) >= 1
    assert posted["json"]["vetoes"][0]["code"] == "spam"


@pytest.mark.asyncio
async def test_record_vetoes_without_webhook_only_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "n8n_xa_veto_log_url", "")
    reports = [judge_post("Alles gut hier, ein ganz normaler Satz über Preise.", _profile("de"))]
    assert await judge.record_vetoes(_profile("de"), reports) == 0


# --- generation (Claude) -----------------------------------------------------


def test_generation_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(xa_gen.GenerationNotConfigured):
        xa_gen._client()


def test_system_prompt_carries_the_customer_rules() -> None:
    prompt = xa_gen.system_prompt(ToneProfile(customer="Beiz", language="de", banned_terms=["Wunderdiät"], topics=["Gastro"]), 3)
    assert "German" in prompt and "Wunderdiät" in prompt and "Gastro" in prompt and "exactly 3" in prompt


def test_split_variants_uses_the_separator_line() -> None:
    text = "Erste Variante.\n---\nZweite Variante.\n---\nDritte Variante.\n---\nVierte."
    assert xa_gen.split_variants(text, 3) == ["Erste Variante.", "Zweite Variante.", "Dritte Variante."]


@pytest.mark.asyncio
async def test_generate_variants_parses_claude_text_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    block = MagicMock()
    block.type = "text"
    block.text = "A\n---\nB\n---\nC"
    response = MagicMock(stop_reason="end_turn", content=[block])
    client = MagicMock()
    client.beta.messages.create = AsyncMock(return_value=response)
    monkeypatch.setattr(xa_gen, "_client", lambda: client)

    variants = await xa_gen.generate_variants("Brief", ToneProfile(language="de"), count=3)

    assert variants == ["A", "B", "C"]
    kwargs = client.beta.messages.create.await_args.kwargs
    assert kwargs["model"] == "claude-opus-5"
    assert kwargs["fallbacks"] == [{"model": "claude-opus-4-8"}]
    assert kwargs["thinking"] == {"type": "adaptive"}


@pytest.mark.asyncio
async def test_generate_variants_surfaces_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.beta.messages.create = AsyncMock(return_value=MagicMock(stop_reason="refusal", content=[]))
    monkeypatch.setattr(xa_gen, "_client", lambda: client)
    with pytest.raises(xa_gen.GenerationError):
        await xa_gen.generate_variants("Brief", ToneProfile())


# --- HTTP endpoints ----------------------------------------------------------


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


JUDGE_BODY = {
    "profile": {"customer": "beiz", "language": "de", "banned_terms": ["Wunderdiät"], "max_hashtags": 2},
    "candidates": [
        "Ein leerer Tisch am Samstag kostet CHF 260. Eine Erinnerung kostet einen Rappen.",
        "JETZT RESERVIEREN!!! #gastro #zürich #whatsapp #jetzt",
    ],
    "recent_posts": [{"text": "Ein Angebot pro Seite.", "posted_at": "2026-09-01T08:00:00+00:00"}],
}


@pytest.mark.asyncio
async def test_judge_endpoint_requires_the_shared_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "judge-secret")
    async with _client() as client:
        missing = await client.post("/x-autopilot/judge", json=JUDGE_BODY)
        wrong = await client.post("/x-autopilot/judge", json=JUDGE_BODY, headers={"X-Judge-Key": "nope"})
    assert missing.status_code == 401
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_judge_endpoint_is_unavailable_without_a_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "")
    async with _client() as client:
        response = await client.post("/x-autopilot/judge", json=JUDGE_BODY, headers={"X-Judge-Key": "x"})
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_judge_endpoint_returns_best_and_recorded_vetoes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "judge-secret")
    monkeypatch.setattr(settings, "n8n_xa_veto_log_url", "")
    async with _client() as client:
        response = await client.post("/x-autopilot/judge", json=JUDGE_BODY, headers={"X-Judge-Key": "judge-secret"})

    assert response.status_code == 200
    body = response.json()
    assert body["best"] == JUDGE_BODY["candidates"][0]
    assert body["vetoes_recorded"] == 1
    assert body["reports"][1]["ok"] is False
    assert body["reports"][1]["vetoes"][0]["code"] == "spam"
    assert body["reports"][0]["length"] > 0


@pytest.mark.asyncio
async def test_compose_endpoint_generates_then_judges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "judge-secret")
    monkeypatch.setattr(settings, "n8n_xa_veto_log_url", "")
    generated = [
        "Ich finde WhatsApp-Reservationen irgendwie praktisch, ehrlich gesagt.",
        "Ein leerer Tisch am Samstag kostet CHF 260. Eine Erinnerung am Vortag kostet einen Rappen.",
        "GARANTIERT keine No-Shows mehr, versprochen!!!",
    ]
    monkeypatch.setattr("app.api.x_autopilot.generate_variants", AsyncMock(return_value=generated))
    body = {"profile": {"customer": "beiz", "language": "de"}, "brief": "No-Shows am Samstag", "variants": 3}

    async with _client() as client:
        response = await client.post("/x-autopilot/compose", json=body, headers={"X-Judge-Key": "judge-secret"})

    assert response.status_code == 200
    data = response.json()
    assert data["best"] == generated[1]
    assert {r["ok"] for r in data["reports"]} == {True, False}
    assert data["vetoes_recorded"] >= 1


@pytest.mark.asyncio
async def test_compose_endpoint_without_anthropic_key_is_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "judge-secret")
    monkeypatch.setattr("app.api.x_autopilot.generate_variants", AsyncMock(side_effect=xa_gen.GenerationNotConfigured("no key")))
    async with _client() as client:
        response = await client.post(
            "/x-autopilot/compose",
            json={"profile": {}, "brief": "x"},
            headers={"X-Judge-Key": "judge-secret"},
        )
    assert response.status_code == 503
