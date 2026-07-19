"""
Optional LLM layer.

The analyzer works fully offline out of the box (see analyzer.py). If you
set an LLM_API_KEY (and optionally LLM_API_BASE / LLM_MODEL) in the
environment, this module will call an OpenAI-compatible chat completions
endpoint to generate sharper, natural-language suggestions on top of the
local TF-IDF + keyword analysis. If no key is set, callers should fall
back to the local rule-based suggestions — the app never requires this.
"""

import json
import logging
import os
import re

import requests

logger = logging.getLogger("app.llm")

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://127.0.0.1:1234/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))


def is_configured() -> bool:
    return bool(LLM_API_KEY)


PROMPT_TEMPLATE = """You are an ATS resume reviewer. Compare the resume text to the \
job description and return ONLY valid JSON (no markdown, no prose) with this shape:

{{
  "match_score": <integer 0-100>,
  "missing_skills": [<strings>],
  "suggestions": [<3 to 5 short, specific, actionable strings>]
}}

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}
"""


def _strip_json_fences(content: str) -> str:
    """Local models often wrap JSON in ```json ... ``` — strip that if present."""
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    if match:
        return match.group(1)
    # Some models add stray prose before/after the JSON object — grab the
    # outermost {...} block as a fallback.
    match = re.search(r"(\{.*\})", content, re.DOTALL)
    return match.group(1) if match else content


def get_llm_suggestions(resume_text: str, jd_text: str) -> dict | None:
    """Returns parsed LLM JSON output, or None if the LLM call fails/unset."""
    if not is_configured():
        return None

    prompt = PROMPT_TEMPLATE.format(
        resume_text=resume_text[:6000],
        jd_text=jd_text[:3000],
    )

    try:
        response = requests.post(
            f"{LLM_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": LLM_MAX_TOKENS,
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.warning("LLM request failed (falling back to local scoring): %s", e)
        return None

    try:
        message = response.json()["choices"][0]["message"]
        content = message.get("content") or ""
        if not content.strip():
            # Some reasoning/thinking models (e.g. Gemma) put the answer in
            # reasoning_content if they run out of budget before finishing
            # the final "content" field.
            content = message.get("reasoning_content") or ""
        cleaned = _strip_json_fences(content)
        return json.loads(cleaned)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.warning(
            "LLM response could not be parsed as JSON (falling back to local "
            "scoring): %s | raw content: %.500s",
            e,
            content if "content" in dir() else response.text,
        )
        return None
