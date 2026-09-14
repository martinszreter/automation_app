"""Reply Engine policy (issue #76): origins resumed, footer killed, R1-R3, bans."""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services import xautopilot_reply as reply
from app.services.xautopilot_judge import ToneProfile
from app.services.xautopilot_reply import (
    ORIGIN_KEYS,
    REPLY_ENGINE_ID,
    REPLY_SLOTS,
    ExistingReply,
    Root,
    active_origins,
    check_media_source,
    check_stranger_reply,
    coverage,
    judge_reply,
    pick_best_reply,
    plan_reply_pack,
    strip_experiment_footer,
)

NOW = datetime(2026, 9, 14, 9, 0, tzinfo=timezone.utc)
HANDLES = "alex_startend, @filip_startend, startend_nyc"
GOOD = "Ein leerer Tisch am Samstag kostet CHF 260. Eine Erinnerung am Vortag kostet einen Rappen."


@pytest.fixture(autouse=True)
def _flagship_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xa_flagship_handles", HANDLES)
    monkeypatch.setattr(settings, "xa_paused_origins", "")


def _profile() -> ToneProfile:
    return ToneProfile(customer="startend", language="de", max_hashtags=2)


def _root(origin: str = "alex", author: str = "@alex_startend", id: str = "root-1") -> Root:
    return Root(id=id, author=author, origin=origin, text="Flagship root", posted_at=NOW)


# --- origins resumed ---------------------------------------------------------


def test_the_three_flagship_origins_are_resumed_by_default() -> None:
    assert ORIGIN_KEYS == ("alex", "filip", "nyc")
    assert [origin.key for origin in active_origins()] == ["alex", "filip", "nyc"]


def test_an_operator_can_still_hold_one_origin_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xa_paused_origins", "filip")
    assert [origin.key for origin in active_origins()] == ["alex", "nyc"]
    assert reply.check_origin(_root("filip")).code == "origin_paused"
    assert reply.check_origin(_root("alex")) is None


def test_origin_lookup_takes_key_or_label_and_rejects_strangers() -> None:
    assert reply.get_origin("NYC").key == "nyc"
    assert reply.get_origin(" Alex ").kind == "persona"
    assert reply.get_origin("berlin") is None
    assert reply.check_origin(_root("berlin")).code == "stranger_reply"


# --- the experiment footer is dead -------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        f"{GOOD}\n\n— Experiment 7/30",
        f"{GOOD}\n— experiment",
        f"{GOOD} | experiment 12/30",
        f"{GOOD} (experiment)",
        f"{GOOD}\n#experiment",
        f"{GOOD}\n-- Experiment, Tag 4",
    ],
)
def test_every_footer_shape_is_stripped(text: str) -> None:
    assert strip_experiment_footer(text) == GOOD
    assert reply.check_experiment_footer(text).code == "experiment_footer"


def test_stripping_leaves_a_clean_post_and_a_real_dash_alone() -> None:
    assert strip_experiment_footer(GOOD) == GOOD
    assert reply.check_experiment_footer(GOOD) is None
    kept = "Reservierung — bestätigt in 20 Sekunden."
    assert strip_experiment_footer(kept) == kept


def test_a_post_about_experiments_in_its_body_survives() -> None:
    body = "Wir haben ein Experiment gefahren: zwei Wochen ohne Erinnerungen, danach zwei Wochen mit. Der Unterschied lag bei 14 Prozent."
    assert strip_experiment_footer(body) == body


# --- Grokywood Imagine only --------------------------------------------------


@pytest.mark.parametrize("source", ["Grokywood Imagine", "grok imagine", "GROKYWOOD", "imagine"])
def test_grokywood_imagine_media_passes(source: str) -> None:
    assert check_media_source([{"source": source}]) is None


@pytest.mark.parametrize("source", ["midjourney", "stock photo", "dall-e 3", "customer upload", ""])
def test_any_other_media_source_is_vetoed(source: str) -> None:
    veto = check_media_source([{"source": source}])
    assert veto is not None and veto.code == "media_source"


def test_a_reply_without_media_is_not_a_media_problem() -> None:
    assert check_media_source([]) is None
    assert check_media_source(None) is None


# --- stranger replies BAN ----------------------------------------------------


def test_replying_to_our_own_flagship_root_is_allowed() -> None:
    assert check_stranger_reply(_root()) is None
    assert check_stranger_reply(_root(author="Filip_StartEnd")) is None


def test_replying_to_a_stranger_is_banned() -> None:
    veto = check_stranger_reply(_root(author="@some_stranger"))
    assert veto is not None and veto.code == "stranger_reply"


def test_the_ban_fails_closed_without_configured_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "xa_flagship_handles", "")
    assert check_stranger_reply(_root()).code == "stranger_reply"
    assert check_stranger_reply(_root(author="")).code == "stranger_reply"


# --- R1-R3 under every flagship root -----------------------------------------


def test_a_fresh_root_owes_all_three_slots_starting_at_the_root() -> None:
    plan = plan_reply_pack(_root(), [])

    assert [slot.slot for slot in plan.missing] == list(REPLY_SLOTS) == ["R1", "R2", "R3"]
    assert plan.missing[0].in_reply_to == "root-1"
    assert plan.posted == []
    assert plan.complete is False


def test_the_next_slot_hangs_under_the_last_posted_reply() -> None:
    posted = [ExistingReply(id="r1", root_id="root-1", posted_at=NOW)]

    plan = plan_reply_pack(_root(), posted)

    assert plan.posted == ["R1"]
    assert [slot.slot for slot in plan.missing] == ["R2", "R3"]
    assert plan.missing[0].in_reply_to == "r1"


def test_slots_are_assigned_oldest_first_when_the_engine_did_not_label_them() -> None:
    older = ExistingReply(id="a", root_id="root-1", posted_at=datetime(2026, 9, 14, 8, tzinfo=timezone.utc))
    newer = ExistingReply(id="b", root_id="root-1", posted_at=datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc))

    plan = plan_reply_pack(_root(), [newer, older])

    assert plan.posted == ["R1", "R2"]
    assert plan.missing[0].in_reply_to == "b"


def test_a_full_pack_is_complete_and_asks_for_nothing_more() -> None:
    posted = [ExistingReply(id=f"r{i}", root_id="root-1", slot=slot) for i, slot in enumerate(REPLY_SLOTS, 1)]

    plan = plan_reply_pack(_root(), posted)

    assert plan.missing == []
    assert plan.complete is True


def test_a_blocked_root_gets_no_slots_at_all() -> None:
    plan = plan_reply_pack(_root(author="@some_stranger"), [])
    assert plan.missing == []
    assert plan.blocked is not None and plan.blocked.code == "stranger_reply"
    assert plan.complete is False


def test_coverage_counts_what_the_resume_still_owes() -> None:
    roots = [_root(id="root-1"), _root(id="root-2", origin="nyc", author="@startend_nyc"), _root(id="root-3", author="@stranger")]
    replies = [
        ExistingReply(id="a", root_id="root-1", posted_at=NOW),
        ExistingReply(id="b", root_id="root-1", posted_at=NOW),
    ]

    result = coverage(roots, replies)

    assert result["engine"] == REPLY_ENGINE_ID == "HNUpMDQaYREs3HOl"
    assert result["roots_total"] == 3
    assert result["roots_blocked"] == 1
    assert result["roots_complete"] == 0
    assert result["missing_total"] == 1 + 3  # root-1 owes R3, root-2 owes R1-R3
    assert result["active_origins"] == ["alex", "filip", "nyc"]


# --- judging one candidate reply ---------------------------------------------


def test_a_clean_reply_passes_and_is_aimed_at_the_next_slot() -> None:
    report = judge_reply(GOOD, _root(), _profile(), now=NOW)

    assert report.ok is True
    assert report.slot == "R1"
    assert report.in_reply_to == "root-1"
    assert report.score > 0


def test_the_footer_is_stripped_from_the_text_and_still_vetoed() -> None:
    report = judge_reply(f"{GOOD}\n\n— Experiment 7/30", _root(), _profile(), now=NOW)

    assert report.text == GOOD
    assert report.ok is False
    assert [v.code for v in report.vetoes] == ["experiment_footer"]


def test_the_post_judge_still_applies_to_replies() -> None:
    report = judge_reply("JETZT RESERVIEREN!!! #a #b #c #d", _root(), _profile(), now=NOW)
    assert report.ok is False
    assert "spam" in {v.code for v in report.vetoes}


def test_a_reply_to_a_stranger_never_passes_however_good_the_text_is() -> None:
    report = judge_reply(GOOD, _root(author="@some_stranger"), _profile(), now=NOW)
    assert report.ok is False
    assert [v.code for v in report.vetoes] == ["stranger_reply"]


def test_a_fourth_reply_under_a_full_pack_is_vetoed() -> None:
    posted = [ExistingReply(id=f"r{i}", root_id="root-1", slot=slot) for i, slot in enumerate(REPLY_SLOTS, 1)]

    report = judge_reply(GOOD, _root(), _profile(), existing=posted, now=NOW)

    assert [v.code for v in report.vetoes] == ["pack_complete"]


def test_foreign_media_sinks_an_otherwise_fine_reply() -> None:
    report = judge_reply(GOOD, _root(), _profile(), media=[{"source": "midjourney"}], now=NOW)
    assert [v.code for v in report.vetoes] == ["media_source"]
    assert judge_reply(GOOD, _root(), _profile(), media=[{"source": "Grok Imagine"}], now=NOW).ok is True


def test_pick_best_reply_skips_the_vetoed_candidates() -> None:
    spam = "JETZT!!! #a #b #c #d #e"
    footered = f"{GOOD}\n— experiment 3/30"
    strong = "Ein leerer Tisch am Samstag kostet CHF 260.\n\nEine Erinnerung am Vortag kostet einen Rappen. Welche Zahl ist grösser?"

    best, reports = pick_best_reply([spam, footered, strong], _root(), _profile(), now=NOW)

    assert best is not None and best.text == strong
    assert best.slot == "R1"
    assert [r.ok for r in reports] == [False, False, True]


def test_pick_best_reply_returns_none_when_the_root_is_blocked() -> None:
    best, reports = pick_best_reply([GOOD], _root(author="@stranger"), _profile(), now=NOW)
    assert best is None
    assert reports[0].vetoes[0].code == "stranger_reply"


def test_veto_reports_carry_every_reason_into_the_ledger_shape() -> None:
    _, reports = pick_best_reply([f"{GOOD}\n— experiment"], _root(), _profile(), now=NOW)
    rows = reply.veto_reports(reports)
    assert [v.code for v in rows[0].vetoes] == ["experiment_footer"]
    assert rows[0].text == GOOD


# --- HTTP endpoints ----------------------------------------------------------


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def _judge_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "xautopilot_judge_key", "judge-key")
    monkeypatch.setattr(settings, "n8n_xa_veto_log_url", "")
    return "judge-key"


@pytest.mark.asyncio
async def test_plan_endpoint_lists_the_missing_slots(_judge_key: str) -> None:
    body = {
        "roots": [{"id": "root-1", "author": "@alex_startend", "origin": "alex"}],
        "replies": [{"id": "r1", "root_id": "root-1", "posted_at": "2026-09-14T08:00:00Z"}],
    }
    async with _client() as client:
        response = await client.post("/x-autopilot/replies/plan", json=body, headers={"X-Judge-Key": _judge_key})

    assert response.status_code == 200
    data = response.json()
    assert data["missing_total"] == 2
    assert [slot["slot"] for slot in data["roots"][0]["missing"]] == ["R2", "R3"]
    assert data["roots"][0]["missing"][0]["in_reply_to"] == "r1"


@pytest.mark.asyncio
async def test_judge_endpoint_picks_a_reply_and_names_its_slot(_judge_key: str) -> None:
    body = {
        "root": {"id": "root-1", "author": "@alex_startend", "origin": "alex"},
        "profile": {"customer": "startend", "language": "de"},
        "candidates": [GOOD],
        "media": [{"source": "Grokywood Imagine"}],
    }
    async with _client() as client:
        response = await client.post("/x-autopilot/replies/judge", json=body, headers={"X-Judge-Key": _judge_key})

    assert response.status_code == 200
    data = response.json()
    assert data["engine"] == REPLY_ENGINE_ID
    assert data["best"]["slot"] == "R1"
    assert data["best"]["in_reply_to"] == "root-1"


@pytest.mark.asyncio
async def test_judge_endpoint_reports_the_ban_instead_of_a_reply(_judge_key: str) -> None:
    body = {
        "root": {"id": "root-1", "author": "@some_stranger", "origin": "alex"},
        "candidates": [GOOD],
    }
    async with _client() as client:
        response = await client.post("/x-autopilot/replies/judge", json=body, headers={"X-Judge-Key": _judge_key})

    data = response.json()
    assert data["best"] is None
    assert data["reports"][0]["vetoes"][0]["code"] == "stranger_reply"
    assert data["vetoes_recorded"] == 1


@pytest.mark.asyncio
async def test_origins_endpoint_shows_the_resumed_three(_judge_key: str) -> None:
    async with _client() as client:
        response = await client.get("/x-autopilot/replies/origins", headers={"X-Judge-Key": _judge_key})

    assert [origin["key"] for origin in response.json()["origins"]] == ["alex", "filip", "nyc"]


@pytest.mark.asyncio
async def test_reply_endpoints_need_the_judge_key(_judge_key: str) -> None:
    async with _client() as client:
        assert (await client.post("/x-autopilot/replies/plan", json={"roots": []})).status_code == 401
        assert (await client.get("/x-autopilot/replies/origins")).status_code == 401
