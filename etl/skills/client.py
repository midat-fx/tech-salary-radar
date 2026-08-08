"""The one function that talks to Gemini.

Isolated so that nothing else in the package imports ``google.genai``: the
dependency pulls a network stack and expects a key, and a test that touches it
by accident fails in CI for a reason that has nothing to do with the change.
"""

from __future__ import annotations

import json
import os

from etl.config import LLM_MODEL
from etl.skills.prompt import PROMPT, RESPONSE_SCHEMA

__all__ = ["gemini_call", "GeminiUnavailable"]


class GeminiUnavailable(RuntimeError):
    """The call could not be made or came back unusable.

    Everything upstream treats this as one kind of failure and counts it; the
    distinction between a 503 and a malformed body does not change what the
    extractor does, and pretending otherwise would add a branch nobody takes.
    """


def gemini_call(payload: list[dict]) -> dict:
    """Send one batch, return the parsed structured answer.

    Temperature zero and a disabled thinking budget: the labels feed a stored
    cache and a published statistic, so two runs over the same postings should
    not disagree about what the ad says.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - the package is a hard dependency
        raise GeminiUnavailable("google-genai is not installed") from exc

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise GeminiUnavailable("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=key)
    content = PROMPT + "\n\nInput:\n" + json.dumps(payload, ensure_ascii=False)
    try:
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=content,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                temperature=0,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 429/503/timeout all mean "try later"
        raise GeminiUnavailable(str(exc)) from exc
    try:
        return json.loads(response.text)
    except (TypeError, ValueError) as exc:
        raise GeminiUnavailable(f"unparseable response: {response.text!r:.120}") from exc
