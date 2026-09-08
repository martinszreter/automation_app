"""X Autopilot post quality: veto hard fails only, pick the best variant.

Deterministic — no model call, so the engines can run it on every candidate.
A post is vetoed for exactly these reasons (everything else passes):

  too_long        X length > 280 (a URL counts 23, wide glyphs/emoji count 2)
  spam            hashtag/mention/link floods, shouting, repeated punctuation,
                  emoji floods, follow-me / link-in-bio / giveaway phrases
  banned_claim    guarantees, comparisons against competitors, cures,
                  get-rich promises, plus the customer's own banned terms
  wrong_language  a stopword vote says the post is not in the customer's language
  duplicate       (near-)identical to a post from the last 30 days

Every veto is written as one JSON log line (``xa_judge_veto``) and, when
``N8N_XA_VETO_LOG_URL`` is set, posted to that n8n webhook so the ledger keeps
the reason next to the post.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_LENGTH = 280
URL_LENGTH = 23
DUPLICATE_WINDOW_DAYS = 30
MAX_MENTIONS = 3
MAX_URLS = 2
MAX_EMOJI = 6
EMOJI_DENSITY = 0.25
CAPS_RATIO = 0.6
CAPS_MIN_LETTERS = 20
NEAR_DUPLICATE_TRIGRAM = 0.6
NEAR_DUPLICATE_WORDS = 0.85
LANGUAGE_MIN_HITS = 3

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"(?<!\w)#\w+")
_MENTION_RE = re.compile(r"(?<!\w)@\w+")
_REPEAT_PUNCT_RE = re.compile(r"[!?]{3,}")
_REPEAT_LETTER_RE = re.compile(r"([^\W\d_])\1{4,}")
_WORD_RE = re.compile(r"[^\W\d_]+")
_DIGIT_RE = re.compile(r"\d")

SPAM_PHRASES: tuple[str, ...] = (
    "follow me",
    "folge mir",
    "folgt mir",
    "obserwuj mnie",
    "dm me",
    "schreib mir eine dm",
    "link in bio",
    "link in der bio",
    "rt to win",
    "retweet to win",
    "giveaway",
    "gewinnspiel",
    "click here",
    "hier klicken",
    "kliknij tutaj",
    "airdrop",
    "100% free",
    "100% gratis",
    "100% kostenlos",
    "make money fast",
    "schnelles geld",
)

BANNED_CLAIMS: dict[str, re.Pattern[str]] = {
    "guarantee": re.compile(
        r"\b(garantier\w*|guarantee\w*|gwarant\w*|risikofrei|risk[- ]?free|bez ryzyka)\b",
        re.IGNORECASE,
    ),
    "competitor_comparison": re.compile(
        r"\b(besser als (die|alle|jede\w*|unsere) (konkurrenz|anderen|mitbewerber|wettbewerber)"
        r"|better than (the|all|any|our) (competition|others|competitors|rest)"
        r"|lepsz\w* (niż|od) (konkurencj\w*|inn\w*)"
        r"|(nr\.?|no\.?|#)\s?1 (in|im|auf|w|na)"
        r"|die nummer (1|eins)|marktführer|market leader|lider rynku)\b",
        re.IGNORECASE,
    ),
    "cure": re.compile(r"\b(heilt|heilen|cures?|leczy|wyleczy)\b", re.IGNORECASE),
    "get_rich": re.compile(
        r"\b(schnell reich|reich werden|get rich|szybko (się )?wzbogac\w*|passives einkommen garantiert)\b",
        re.IGNORECASE,
    ),
}

# Small stopword votes — enough to tell de/en/pl/fr apart on a 280-char post.
STOPWORDS: dict[str, frozenset[str]] = {
    "de": frozenset(
        "der die das und ist nicht ein eine mit auf für von zu den dem im wir ich sie es "
        "auch wie bei nach aus oder wird sind noch mehr über als wenn nur sich haben hat "
        "wird werden kann man dass diese dieser einem einer ihr euch uns heute".split()
    ),
    "en": frozenset(
        "the and is not a an with on for of to in we i you it also how at from or will are "
        "still more about than if only that this your our they have has can be was were "
        "what when here there today".split()
    ),
    "pl": frozenset(
        "i jest nie na z do w się że to jak dla od po ale czy są już tylko przez bardzo "
        "może być jego ich nas was co gdy kiedy dziś więcej niż ten ta które który".split()
    ),
    "fr": frozenset(
        "le la les et est pas un une avec sur pour de à dans nous je vous il elle aussi "
        "comment ou sont encore plus que si des du ce cette votre notre aujourd'hui".split()
    ),
}


@dataclass
class ToneProfile:
    """What the judge knows about one customer (from agents + onboarding_leads)."""

    customer: str = ""
    language: str = "de"
    banned_terms: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    voice: str = ""
    max_hashtags: int = 2


@dataclass
class RecentPost:
    text: str
    posted_at: datetime | None = None


@dataclass
class Veto:
    code: str
    detail: str


@dataclass
class Report:
    text: str
    ok: bool
    score: float
    vetoes: list[Veto] = field(default_factory=list)
    length: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- helpers -----------------------------------------------------------------


def x_length(text: str) -> int:
    """Length the way X counts it: URLs are 23, wide glyphs and emoji are 2."""
    stripped = _URL_RE.sub("x" * URL_LENGTH, text.strip())
    total = 0
    for ch in stripped:
        wide = unicodedata.east_asian_width(ch) in ("W", "F") or ord(ch) >= 0x1F000
        total += 2 if wide else 1
    return total


def _emoji_count(text: str) -> int:
    return sum(1 for ch in text if ord(ch) >= 0x1F000 or unicodedata.category(ch) == "So")


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def detect_language(text: str) -> tuple[str | None, dict[str, int]]:
    """Return the stopword-vote winner (or None when the vote is too weak)."""
    words = _words(text)
    hits = {lang: sum(1 for w in words if w in stop) for lang, stop in STOPWORDS.items()}
    best = max(hits, key=lambda lang: hits[lang])
    if hits[best] < LANGUAGE_MIN_HITS:
        return None, hits
    return best, hits


def normalize_for_duplicate(text: str) -> str:
    cleaned = _URL_RE.sub(" ", text)
    cleaned = _MENTION_RE.sub(" ", cleaned)
    cleaned = cleaned.replace("#", " ")
    return " ".join(_words(cleaned))


def _trigrams(words: list[str]) -> set[tuple[str, str, str]]:
    return {tuple(words[i : i + 3]) for i in range(len(words) - 2)}  # type: ignore[misc]


def similarity(a: str, b: str) -> float:
    """0..1 overlap: word-trigram Jaccard for longer posts, word-set Jaccard for short ones."""
    wa, wb = normalize_for_duplicate(a).split(), normalize_for_duplicate(b).split()
    if not wa or not wb:
        return 0.0
    if len(wa) >= 8 and len(wb) >= 8:
        ta, tb = _trigrams(wa), _trigrams(wb)
        return len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    sa, sb = set(wa), set(wb)
    return len(sa & sb) / len(sa | sb)


def parse_posted_at(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _banned_terms(profile: ToneProfile) -> list[str]:
    terms: list[str] = []
    for raw in profile.banned_terms:
        for part in re.split(r"[,;\n]", raw or ""):
            term = part.strip().lower()
            if term:
                terms.append(term)
    return terms


# --- rules -------------------------------------------------------------------


def check_length(text: str) -> Veto | None:
    length = x_length(text)
    if length > MAX_LENGTH:
        return Veto("too_long", f"{length} > {MAX_LENGTH} characters (X count)")
    return None


def check_spam(text: str, profile: ToneProfile) -> Veto | None:
    lowered = text.lower()
    hashtags = len(_HASHTAG_RE.findall(text))
    if hashtags > max(profile.max_hashtags, 0) + 1:
        return Veto("spam", f"{hashtags} hashtags (limit {profile.max_hashtags})")
    mentions = len(_MENTION_RE.findall(text))
    if mentions > MAX_MENTIONS:
        return Veto("spam", f"{mentions} mentions (limit {MAX_MENTIONS})")
    urls = len(_URL_RE.findall(text))
    if urls > MAX_URLS:
        return Veto("spam", f"{urls} links (limit {MAX_URLS})")
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) >= CAPS_MIN_LETTERS:
        caps = sum(1 for ch in letters if ch.isupper()) / len(letters)
        if caps > CAPS_RATIO:
            return Veto("spam", f"{caps:.0%} upper-case letters")
    if _REPEAT_PUNCT_RE.search(text):
        return Veto("spam", "repeated !!! / ???")
    if _REPEAT_LETTER_RE.search(text):
        return Veto("spam", "a letter repeated five or more times")
    emoji = _emoji_count(text)
    visible = len(text.replace(" ", "")) or 1
    if emoji >= MAX_EMOJI or emoji / visible > EMOJI_DENSITY:
        return Veto("spam", f"{emoji} emoji")
    for phrase in SPAM_PHRASES:
        if phrase in lowered:
            return Veto("spam", f"spam phrase: {phrase!r}")
    return None


def check_banned_claims(text: str, profile: ToneProfile) -> Veto | None:
    for name, pattern in BANNED_CLAIMS.items():
        match = pattern.search(text)
        if match:
            return Veto("banned_claim", f"{name}: {match.group(0)!r}")
    lowered = text.lower()
    for term in _banned_terms(profile):
        if term in lowered:
            return Veto("banned_claim", f"customer banned term: {term!r}")
    return None


def check_language(text: str, profile: ToneProfile) -> Veto | None:
    expected = (profile.language or "").strip().lower()[:2]
    if expected not in STOPWORDS:
        return None
    detected, hits = detect_language(text)
    if detected is None or detected == expected:
        return None
    if hits[detected] > hits[expected] + 1:
        return Veto("wrong_language", f"reads as {detected} (votes {hits[detected]} vs {hits[expected]} for {expected})")
    return None


def check_duplicate(text: str, recent: list[RecentPost], *, now: datetime | None = None) -> Veto | None:
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(days=DUPLICATE_WINDOW_DAYS)
    normalized = normalize_for_duplicate(text)
    if not normalized:
        return None
    for post in recent:
        if post.posted_at is not None and post.posted_at < window_start:
            continue
        if normalize_for_duplicate(post.text) == normalized:
            return Veto("duplicate", "identical to a post from the last 30 days")
        overlap = similarity(text, post.text)
        threshold = NEAR_DUPLICATE_TRIGRAM if len(normalized.split()) >= 8 else NEAR_DUPLICATE_WORDS
        if overlap >= threshold:
            return Veto("duplicate", f"{overlap:.0%} overlap with a post from the last 30 days")
    return None


# --- scoring + verdict -------------------------------------------------------


def score_post(text: str, profile: ToneProfile) -> float:
    """Soft preference among posts that passed: not a veto, only a tie-breaker."""
    stripped = text.strip()
    score = 100.0
    score -= abs(x_length(stripped) - 200) / 4  # sweet spot around 200 characters
    if _DIGIT_RE.search(stripped):
        score += 8  # a concrete number beats an adjective
    if "\n" in stripped:
        score += 4  # visible structure
    hashtags = len(_HASHTAG_RE.findall(stripped))
    score -= 6 * max(0, hashtags - 1)
    first = stripped.split(" ", 1)[0].lower().strip(":,.!")
    if first in {"ich", "i", "ja", "wir", "we", "my"}:
        score -= 6  # weak, self-centred opening
    if stripped.endswith("?"):
        score += 3
    if _URL_RE.search(stripped):
        score -= 4
    return round(score, 2)


def judge_post(
    text: str,
    profile: ToneProfile,
    recent: list[RecentPost] | None = None,
    *,
    now: datetime | None = None,
) -> Report:
    vetoes: list[Veto] = []
    if not text or not text.strip():
        vetoes.append(Veto("too_long", "empty post"))
    for veto in (
        check_length(text),
        check_spam(text, profile),
        check_banned_claims(text, profile),
        check_language(text, profile),
        check_duplicate(text, recent or [], now=now),
    ):
        if veto is not None:
            vetoes.append(veto)
    ok = not vetoes
    return Report(
        text=text,
        ok=ok,
        score=score_post(text, profile) if ok else 0.0,
        vetoes=vetoes,
        length=x_length(text),
    )


def pick_best(
    candidates: list[str],
    profile: ToneProfile,
    recent: list[RecentPost] | None = None,
    *,
    now: datetime | None = None,
) -> tuple[Report | None, list[Report]]:
    """Judge every candidate; return (best passing report or None, all reports)."""
    reports = [judge_post(text, profile, recent, now=now) for text in candidates]
    passing = [report for report in reports if report.ok]
    if not passing:
        return None, reports
    return max(passing, key=lambda report: report.score), reports


# --- veto ledger -------------------------------------------------------------


def veto_rows(profile: ToneProfile, reports: list[Report]) -> list[dict[str, Any]]:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for report in reports:
        for veto in report.vetoes:
            rows.append(
                {
                    "table": "xautopilot_vetoes",
                    "customer": profile.customer,
                    "language": profile.language,
                    "code": veto.code,
                    "detail": veto.detail,
                    "text": report.text[:400],
                    "created_at": stamp,
                }
            )
    return rows


async def record_vetoes(profile: ToneProfile, reports: list[Report]) -> int:
    """Log every veto (one JSON line each) and post them to n8n when configured."""
    rows = veto_rows(profile, reports)
    for row in rows:
        logger.info("xa_judge_veto %s", json.dumps(row, ensure_ascii=False))
    url = settings.n8n_xa_veto_log_url.strip()
    if not rows or not url:
        return len(rows)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"vetoes": rows})
        if response.status_code >= 400:
            logger.warning("veto log webhook rejected rows: %s", response.status_code)
    except httpx.HTTPError as exc:
        logger.warning("veto log webhook unreachable: %s", exc)
    return len(rows)
