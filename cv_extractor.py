"""
Moduł strukturyzacji CV przez lokalny LLM (Ollama).

Funkcje:
    extract_cv_structure(raw_text, model) — zwraca ustrukturyzowany słownik CV bez danych osobowych.
"""

import logging

from ollama import chat, ResponseError
from fastapi import HTTPException

from cv_schema import CVData
from prompt import _SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_USER_PROMPT_TEMPLATE = """Parse this CV into structured JSON. Classify ALL work/job entries into "experience" — do not leave it empty if the CV describes employment. Put the degree type (BSc, MSc, PhD, etc.) into "degree", NOT into "notes". Merge all skill/tech sections into "skills". Everything else goes into "extras" with fitting category names. Remove personal contact data entirely.

CV TEXT:
{raw_text}"""


def extract_cv_structure(raw_text: str, model: str = "qwen3:4b") -> dict:
    """Strukturyzuje surowy tekst CV do słownika zgodnego z CVData. Nie zwraca żadnych danych osobowych."""
    if not raw_text.strip():
        return CVData().model_dump()

    prompt = _USER_PROMPT_TEMPLATE.format(raw_text=raw_text)

    try:
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            format=CVData.model_json_schema(),
            options={"temperature": 0, "num_ctx": 12288},
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    raw_response = response.message.content
    logger.info("LLM raw response (%d chars): %s", len(raw_response), raw_response[:2000])

    try:
        return CVData.model_validate_json(raw_response).model_dump()
    except Exception as e:
        logger.warning("Failed to parse LLM response: %s", e)
        return CVData().model_dump()
