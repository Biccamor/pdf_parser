"""
Moduł strukturyzacji CV przez lokalny LLM (Ollama).

Funkcje:
    extract_cv_structure(raw_text, model) — zwraca ustrukturyzowany słownik CV bez danych osobowych.
"""

import logging

from ollama import chat, ResponseError, AsyncClient
from fastapi import HTTPException

from cv_schema import CVData
from prompt import _SYSTEM_PROMPT, _USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)




async def extract_cv_structure(raw_text: str, model: str = "gemma4:latest") -> dict:
    """Strukturyzuje surowy tekst CV do słownika zgodnego z CVData. Nie zwraca żadnych danych osobowych."""
    if not raw_text.strip():
        return CVData().model_dump()

    prompt = _USER_PROMPT_TEMPLATE.format(raw_text=raw_text)

    try:
        response = await AsyncClient().chat(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            format=CVData.model_json_schema(),
            options={"temperature": 0, "num_ctx": 16384},
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
