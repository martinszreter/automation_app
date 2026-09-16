"""X.com Reply Engine policy: flagship origins, R1-R3 packs, hard bans.

Deterministic — no model call, so the Reply Engine (n8n workflow
``HNUpMDQaYREs3HOl``) can run it on every root and every candidate reply before
anything reaches X. It answers three questions:

  which roots still owe replies   ``plan_reply_pack`` / ``coverage``
  may this reply be posted at all ``judge_reply`` (reply vetoes + the post judge)
  what does the text look like    ``strip_experiment_footer``

Ratified by Marcin on 14 Sep 2026 (GO, issue #76):

  * the flagship origins ALEX, FILIP and NYC are resumed — all three draft again;
  * the experiment footer is dead: it is stripped, and a candidate that still
    carries one is vetoed;
  * every flagship root carries exactly three replies, R1 R2 R3;
  * media may only come from Grokywood Imagine;
  * replying to an account that is not one of ours is BANNED.

Reply vetoes use the same ``Veto`` shape as ``xautopilot_judge`` and go to the
same ledger, so the reason sits next to the reply in one place:

  stranger_reply    the root's author is not a flagship account of ours
  origin_paused     the root's flagship origin is not drafting right now
  experiment_footer the candidate still carries the killed footer
  media_source      media that did not come from Grokywood Imagine
  pack_complete     R1-R3 already sit under this root
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.core.config import settings
from app.services.xautopilot_judge import (
    RecentPost,
    Report,
    ToneProfile,
    Veto,
    judge_post,
    score_post,
)

# n8n workflow that owns the reply lane. Identity, not config: a second engine
# posting under the same roots would double every pack.
REPLY_ENGINE_ID = "HNUpMDQaYREs3HOl"

# Exactly three replies under every flagship root — no more, no fewer.
REPLY_SLOTS: tuple[str, ...] = ("R1", "R2", "R3")

# Marcin, 14 Sep 2026: the pack has to read as one thread, so R2 answers R1 and
# R3 answers R2. All three still hang under the flagship root, and when a
# previous reply's id is not known yet the slot falls back to the root itself.
CHAIN_UNDER_PREVIOUS = True

RESUMED_ON = date(2026, 9, 14)

# The only image/video source a flagship post or reply may carry.
GROKYWOOD_IMAGINE = "grokywood_imagine"
_IMAGINE_NAMES = frozenset(
    {
        "grokywood imagine",
        "grokywood",
        "grok imagine",
        "grokimagine",
        "imagine",
    }
)

_HANDLE_RE = re.compile(r"[^a-z0-9_]")
_SPLIT_RE = re.compile(r"[,;\s]+")
_EXPERIMENT_RE = re.compile(r"\b(?:experiment|experimental|eksperyment|expérience)\w*\b", re.IGNORECASE)
# Trailing "— experiment 7/30", "| experiment", "-- Experiment", "(experiment)".
_FOOTER_TAIL_RE = re.compile(
    r"\s*(?:[—–|·•]|-{1,2})\s*[^\n]{0,60}$|\s*\([^()\n]{0,60}\)\s*$",
)
_FOOTER_MAX_CHARS = 80


@dataclass(frozen=True)
class Origin:
    """One flagship content origin. Resumed unless an operator pauses it."""

    key: str
    label: str
    kind: str


# Alex and Filip are persona origins, NYC is a place origin. Handles live in
# XA_FLAGSHIP_HANDLES (deployment config), never here.
ORIGINS: tuple[Origin, ...] = (
    Origin("alex", "ALEX", "persona"),
    Origin("filip", "FILIP", "persona"),
    Origin("nyc", "NYC", "place"),
)
ORIGIN_KEYS: tuple[str, ...] = tuple(origin.key for origin in ORIGINS)


@dataclass
class Root:
    """A flagship root post the Reply Engine works under."""

    id: str
    author: str = ""
    origin: str = ""
    text: str = ""
    posted_at: datetime | None = None


@dataclass
class ExistingReply:
    """A reply already sitting under a root, oldest first once sorted."""

    id: str = ""
    root_id: str = ""
    slot: str = ""
    posted_at: datetime | None = None


@dataclass
class ReplySlotPlan:
    slot: str
    root_id: str
    in_reply_to: str

    def to_dict(self) -> dict[str, Any]:
        return {"slot": self.slot, "root_id": self.root_id, "in_reply_to": self.in_reply_to}


@dataclass
class ReplyPlan:
    root_id: str
    origin: str
    posted: list[str] = field(default_factory=list)
    missing: list[ReplySlotPlan] = field(default_factory=list)
    blocked: Veto | None = None

    @property
    def complete(self) -> bool:
        return not self.missing and self.blocked is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "origin": self.origin,
            "posted": list(self.posted),
            "missing": [slot.to_dict() for slot in self.missing],
            "blocked": {"code": self.blocked.code, "detail": self.blocked.detail} if self.blocked else None,
            "complete": self.complete,
        }


@dataclass
class ReplyReport:
    """One candidate reply: the footer-free text plus every veto against it."""

    text: str
    ok: bool
    score: float
    slot: str = ""
    in_reply_to: str = ""
    vetoes: list[Veto] = field(default_factory=list)
    length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "ok": self.ok,
            "score": self.score,
            "slot": self.slot,
            "in_reply_to": self.in_reply_to,
            "vetoes": [{"code": v.code, "detail": v.detail} for v in self.vetoes],
            "length": self.length,
        }


# --- origins -----------------------------------------------------------------


def _split(raw: str) -> list[str]:
    return [part for part in _SPLIT_RE.split((raw or "").strip()) if part]


def paused_origins() -> set[str]:
    """Origin keys an operator paused through XA_PAUSED_ORIGINS. Empty = all run."""
    return {key.lower().strip("@") for key in _split(settings.xa_paused_origins)}


def active_origins() -> tuple[Origin, ...]:
    paused = paused_origins()
    return tuple(origin for origin in ORIGINS if origin.key not in paused)


def get_origin(key: str) -> Origin | None:
    needle = (key or "").strip().lower()
    for origin in ORIGINS:
        if origin.key == needle or origin.label.lower() == needle:
            return origin
    return None


def normalize_handle(handle: str) -> str:
    """``" @Alex_NYC "`` → ``"alex_nyc"``; anything unusable → ``""``."""
    return _HANDLE_RE.sub("", (handle or "").strip().lower().lstrip("@"))


def flagship_handles() -> set[str]:
    """Our own X accounts, from XA_FLAGSHIP_HANDLES. Empty means "we know none"."""
    return {h for h in (normalize_handle(part) for part in _split(settings.xa_flagship_handles)) if h}


# --- experiment footer (killed 14 Sep 2026) ----------------------------------


def _is_footer_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _FOOTER_MAX_CHARS:
        return False
    return bool(_EXPERIMENT_RE.search(stripped))


def strip_experiment_footer(text: str) -> str:
    """Remove the trailing experiment footer, whether it is its own line or a tail."""
    lines = (text or "").rstrip().split("\n")
    while lines and _is_footer_line(lines[-1]):
        lines.pop()
    body = "\n".join(lines).rstrip()
    while True:
        match = _FOOTER_TAIL_RE.search(body)
        if not match or not _EXPERIMENT_RE.search(match.group(0)):
            break
        body = body[: match.start()].rstrip()
    return body.strip()


def check_experiment_footer(text: str) -> Veto | None:
    if strip_experiment_footer(text) != (text or "").strip():
        return Veto("experiment_footer", "carries the experiment footer, killed 14 Sep 2026")
    return None


# --- Grokywood Imagine only --------------------------------------------------


def normalize_media_source(source: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (source or "").strip().lower()).strip()
    return GROKYWOOD_IMAGINE if cleaned in _IMAGINE_NAMES else cleaned


def check_media_source(media: list[dict[str, Any]] | None) -> Veto | None:
    """Every attached asset must name Grokywood Imagine as its source."""
    for item in media or []:
        raw = str((item or {}).get("source") or "").strip()
        if not raw:
            return Veto("media_source", "media without a source (Grokywood Imagine only)")
        if normalize_media_source(raw) != GROKYWOOD_IMAGINE:
            return Veto("media_source", f"media from {raw!r} (Grokywood Imagine only)")
    return None


# --- stranger replies BAN ----------------------------------------------------


def check_stranger_reply(root: Root) -> Veto | None:
    """Fail closed: unless the root is provably ours, the reply is banned."""
    author = normalize_handle(root.author)
    if not author:
        return Veto("stranger_reply", "root has no author handle")
    handles = flagship_handles()
    if not handles:
        return Veto("stranger_reply", "XA_FLAGSHIP_HANDLES is not set — no root can be proven ours")
    if author not in handles:
        return Veto("stranger_reply", f"@{author} is not a flagship account")
    return None


def check_origin(root: Root) -> Veto | None:
    origin = get_origin(root.origin)
    if origin is None:
        return Veto("stranger_reply", f"unknown flagship origin {root.origin!r}")
    if origin.key in paused_origins():
        return Veto("origin_paused", f"origin {origin.label} is paused")
    return None


def root_blocked(root: Root) -> Veto | None:
    """The one veto that stops the whole pack under this root, if any."""
    return check_stranger_reply(root) or check_origin(root)


# --- R1-R3 pack planning -----------------------------------------------------


def _ordered(replies: list[ExistingReply]) -> list[ExistingReply]:
    labelled = {r.slot.upper(): r for r in replies if r.slot.upper() in REPLY_SLOTS}
    if len(labelled) == len(replies):
        return [labelled[slot] for slot in REPLY_SLOTS if slot in labelled]
    return sorted(replies, key=lambda r: (r.posted_at is None, r.posted_at or datetime.min))


def plan_reply_pack(root: Root, existing: list[ExistingReply] | None = None) -> ReplyPlan:
    """Which of R1-R3 still have to be posted under ``root``, and under what."""
    blocked = root_blocked(root)
    plan = ReplyPlan(root_id=root.id, origin=(root.origin or "").strip().lower())
    if blocked is not None:
        plan.blocked = blocked
        return plan

    ordered = _ordered([r for r in (existing or []) if not r.root_id or r.root_id == root.id])[: len(REPLY_SLOTS)]
    plan.posted = [slot for slot, _ in zip(REPLY_SLOTS, ordered)]
    parent = ordered[-1].id if ordered and CHAIN_UNDER_PREVIOUS and ordered[-1].id else root.id
    for slot in REPLY_SLOTS[len(ordered) :]:
        plan.missing.append(ReplySlotPlan(slot=slot, root_id=root.id, in_reply_to=parent or root.id))
        # The next slot answers this one; its id only exists after it is posted,
        # so the engine has to re-plan between replies to get a true chain.
        parent = ""
    return plan


def coverage(
    roots: list[Root],
    replies: list[ExistingReply] | None = None,
) -> dict[str, Any]:
    """Pack state across every flagship root — the "fire R1-R3 everywhere" view."""
    by_root: dict[str, list[ExistingReply]] = {}
    for reply in replies or []:
        by_root.setdefault(reply.root_id, []).append(reply)
    plans = [plan_reply_pack(root, by_root.get(root.id, [])) for root in roots]
    return {
        "engine": REPLY_ENGINE_ID,
        "slots": list(REPLY_SLOTS),
        "active_origins": [origin.key for origin in active_origins()],
        "roots": [plan.to_dict() for plan in plans],
        "roots_total": len(plans),
        "roots_complete": sum(1 for plan in plans if plan.complete),
        "roots_blocked": sum(1 for plan in plans if plan.blocked is not None),
        "missing_total": sum(len(plan.missing) for plan in plans),
    }


# --- judging one candidate reply ---------------------------------------------


def judge_reply(
    text: str,
    root: Root,
    profile: ToneProfile,
    *,
    recent: list[RecentPost] | None = None,
    existing: list[ExistingReply] | None = None,
    media: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> ReplyReport:
    """Strip the dead footer, run the post judge, then the reply-only vetoes."""
    cleaned = strip_experiment_footer(text)
    base: Report = judge_post(cleaned, profile, recent or [], now=now)
    vetoes = list(base.vetoes)

    plan = plan_reply_pack(root, existing)
    if plan.blocked is not None:
        vetoes.append(plan.blocked)
    elif not plan.missing:
        vetoes.append(Veto("pack_complete", f"R1-R3 already posted under {root.id}"))

    footer = check_experiment_footer(text)
    if footer is not None:
        vetoes.append(footer)
    media_veto = check_media_source(media)
    if media_veto is not None:
        vetoes.append(media_veto)

    ok = not vetoes
    target = plan.missing[0] if plan.missing else None
    return ReplyReport(
        text=cleaned,
        ok=ok,
        score=score_post(cleaned, profile) if ok else 0.0,
        slot=target.slot if target else "",
        in_reply_to=target.in_reply_to if target else "",
        vetoes=vetoes,
        length=base.length,
    )


def pick_best_reply(
    candidates: list[str],
    root: Root,
    profile: ToneProfile,
    *,
    recent: list[RecentPost] | None = None,
    existing: list[ExistingReply] | None = None,
    media: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> tuple[ReplyReport | None, list[ReplyReport]]:
    """Judge every candidate; return (best passing report or None, all reports)."""
    reports = [
        judge_reply(text, root, profile, recent=recent, existing=existing, media=media, now=now)
        for text in candidates
    ]
    passing = [report for report in reports if report.ok]
    if not passing:
        return None, reports
    return max(passing, key=lambda report: report.score), reports


def veto_reports(reports: list[ReplyReport]) -> list[Report]:
    """Adapt reply reports to the post-judge shape so the veto ledger takes them."""
    return [
        Report(text=r.text, ok=r.ok, score=r.score, vetoes=list(r.vetoes), length=r.length)
        for r in reports
    ]
