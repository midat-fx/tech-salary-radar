"""Skill extraction via Gemini structured output, cached (PLAN.md §6, stage 5).

ATS boards have no free key_skills ground truth, so skills come only from the LLM (source='llm').
"""

RESPONSE_SCHEMA = None  # built from CANONICAL in stage 5 (see PLAN.md §6.2)

PROMPT = """You label job postings with technology skills.
Input: a JSON array of postings, each {"id": int, "title": str, "text": str}, in Russian or English.
For EVERY posting return the skills from the allowed list that are EXPLICITLY mentioned in its title or text.
Rules:
- Use only skills from the allowed list, with exact canonical spelling.
- Explicit mentions only ("питон" -> Python, "верстка" -> HTML/CSS). Do not infer skills from job title level, company type, or typical stacks.
- Single allowed inference: a framework implies its language (Django/FastAPI/Flask -> also Python).
- If nothing matches, return an empty skills array for that id.
- Return every input id exactly once."""


def extract_llm(batch):
    """Call Gemini on a batch of postings; return {index: [canonical skills]} for the batch."""
    raise NotImplementedError


def pending_queue(data_dir):
    """anti-join jobs - skills: job_uids not yet processed by the extractor."""
    raise NotImplementedError
