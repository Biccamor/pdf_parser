"""
Moduł OCR — ekstrakcja tekstu z obrazów przez lokalny model Ollama (glm-ocr).

Funkcje:
    get_text_ollama(image_path, model) — zwraca surowy tekst z obrazu, bez danych osobowych.
"""

from ollama import chat, ResponseError, AsyncClient
from fastapi import HTTPException
from prompt import _OCR_PROMPT

async def get_text_ollama(image_path: str, model: str = "glm-ocr:latest") -> str:
    """Wysyła obraz do lokalnego modelu Ollama i zwraca wyekstrahowany tekst bez danych osobowych."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    try:
        response = await AsyncClient().chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": _OCR_PROMPT,
                    "images": [image_bytes],
                }
            ],
            options={"temperature": 0},
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    return response.message.content.strip()
