"""
Moduł OCR — ekstrakcja tekstu z obrazów przez lokalny model Ollama (glm-ocr).

Funkcje:
    get_text_ollama(image_path, model) — zwraca surowy tekst z obrazu, bez danych osobowych.
"""

from ollama import chat, ResponseError
from fastapi import HTTPException


_OCR_PROMPT = """Extract ALL visible text from this document image.
RULES:
- Return ONLY the raw extracted text — no markdown, no code blocks, no explanations.
- Preserve the original reading order and line breaks.
- Keep all values in their original language.
- Skip any embedded images, icons, logos, or decorative elements.
- CRITICAL: REMOVE all personal data before returning: full names, first names, last names, \
email addresses, phone numbers, home addresses, national ID numbers (e.g. PESEL), \
dates of birth, LinkedIn URLs, GitHub URLs, personal websites, or any other identifying information. \
Replace them with empty string or skip the line entirely."""


def get_text_ollama(image_path: str, model: str = "glm-ocr:latest") -> str:
    """Wysyła obraz do lokalnego modelu Ollama i zwraca wyekstrahowany tekst bez danych osobowych."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    try:
        response = chat(
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
