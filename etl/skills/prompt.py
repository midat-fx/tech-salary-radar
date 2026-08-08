"""What the model is asked, and what it is allowed to answer.

The prompt is versioned and the version is stored on every label. That is not
bookkeeping: a prompt change alters what "this job needs Python" means, and a
premium computed over two generations of labels mixes two definitions of the
same skill. ADR 0003 turns that into a rule the aggregator enforces.

The version has moved once and moved back. ``v2`` widened the inference rules
and the evaluation set rejected it — it began inferring stacks from company
type. The rejection is why the constant is here with its history rather than
being a number someone bumps.
"""

from __future__ import annotations

from etl.config import PROMPT_VERSION
from etl.skills.catalog import CANONICAL

__all__ = ["PROMPT", "RESPONSE_SCHEMA", "PROMPT_VERSION", "VERSION_HISTORY", "build_payload"]

VERSION_HISTORY = {
    "v1": "explicit mentions only; a framework implies its language",
    "v2": "widened inference — rejected on eval evidence, never deployed",
}

#: Structured-output schema. The skill enum is the catalog itself, so the model
#: cannot answer with a name the pipeline has no column for — the one class of
#: error that would otherwise be silent, since an unknown name canonicalises to
#: None and disappears.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "skills": {"type": "ARRAY", "items": {"type": "STRING", "enum": CANONICAL}},
                },
                "required": ["id", "skills"],
            },
        }
    },
    "required": ["items"],
}

PROMPT = """You label job postings with technology skills.
Input: a JSON array of postings, each {"id": int, "title": str, "text": str}, in Russian or English.
For EVERY posting return the skills from the allowed list that are EXPLICITLY mentioned in its title or text.
Rules:
- Use only skills from the allowed list, with exact canonical spelling.
- Explicit mentions only ("питон" -> Python, "верстка" -> HTML/CSS). Do not infer skills from job title level, company type, or typical stacks.
- Single allowed inference: a framework implies its language (Django/FastAPI/Flask -> also Python).
- If nothing matches, return an empty skills array for that id.
- Return every input id exactly once."""


def build_payload(batch: list[dict], text_limit: int, title_limit: int = 200) -> list[dict]:
    """Trim a batch to what fits in one request.

    The text limit is generous on purpose. It was 1500 and the requirements
    section of a long job description lives past that, so the model was reading
    the company blurb and labelling nothing.
    """
    return [
        {
            "id": posting["id"],
            "title": (posting.get("title") or "")[:title_limit],
            "text": (posting.get("text") or "")[:text_limit],
        }
        for posting in batch
    ]
