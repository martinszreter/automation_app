"""Three-variant X post generation with Claude (optional).

Runs only when ANTHROPIC_API_KEY is set; otherwise the n8n engines keep drafting
with their own Anthropic credential and send the variants to /x-autopilot/judge.
The judge (app.services.xautopilot_judge) always has the last word.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.services.xautopilot_judge import MAX_LENGTH, ToneProfile

FALLBACK_MODEL = "claude-opus-4-8"
_SEPARATOR = re.compile(r"^\s*---\s*$", re.MULTILINE)

LANGUAGE_NAMES = {"de": "German (Swiss spelling: ss, never ß)", "en": "English", "pl": "Polish", "fr": "French"}


class GenerationNotConfigured(RuntimeError):
    """ANTHROPIC_API_KEY is not set."""


class GenerationError(RuntimeError):
    """Claude refused or returned nothing usable."""


def system_prompt(profile: ToneProfile, count: int) -> str:
    language = LANGUAGE_NAMES.get((profile.language or "de")[:2], profile.language)
    topics = ", ".join(t for t in profile.topics if t.strip()) or "the customer's field"
    banned = ", ".join(t for t in profile.banned_terms if t.strip()) or "none"
    voice = profile.voice.strip() or "direct, concrete, no hype"
    return (
        f"You write posts for X on behalf of {profile.customer or 'a customer'}.\n"
        f"Language: {language}. Topics: {topics}. Voice: {voice}.\n"
        f"Hard rules: at most {MAX_LENGTH} characters per post (a link counts 23); "
        f"at most {profile.max_hashtags} hashtags; no guarantees, no comparisons against "
        "competitors, no cures, no get-rich promises, no follow-me or link-in-bio asks. "
        f"Never use these terms: {banned}.\n"
        f"Write exactly {count} different variants of one post for the brief. "
        "Vary the opening and the angle. Return only the variants, separated by a line "
        "that contains just --- and nothing else. No numbering, no commentary."
    )


def split_variants(text: str, count: int) -> list[str]:
    variants = [part.strip() for part in _SEPARATOR.split(text) if part.strip()]
    return variants[:count]


def _client() -> Any:
    key = settings.anthropic_api_key.strip()
    if not key:
        raise GenerationNotConfigured("ANTHROPIC_API_KEY is not set")
    import anthropic  # lazy: the app runs without the SDK when generation is off

    return anthropic.AsyncAnthropic(api_key=key)


async def generate_variants(brief: str, profile: ToneProfile, *, count: int = 3) -> list[str]:
    client = _client()
    response = await client.beta.messages.create(
        model=settings.xautopilot_generate_model.strip() or "claude-opus-5",
        max_tokens=4000,
        betas=["server-side-fallback-2026-06-01"],
        fallbacks=[{"model": FALLBACK_MODEL}],
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        system=system_prompt(profile, count),
        messages=[{"role": "user", "content": brief.strip()}],
    )
    if getattr(response, "stop_reason", None) == "refusal":
        raise GenerationError("Claude declined the brief")
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    variants = split_variants(text, count)
    if not variants:
        raise GenerationError("Claude returned no variants")
    return variants
