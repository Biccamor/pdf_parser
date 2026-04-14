"""
Moduł rezerwowy (not yet integrated) — OCR przez lokalny model Ollama.
Docelowo może zastąpić lub uzupełnić Tesseract dla dokumentów
wymagających rozumienia kontekstu (np. tabele, wielokolumnowe layouty).

Użycie:
    from ollama_ocr import get_text_ollama
    text = get_text_ollama(image_path="page.png", model="glm-ocr")
"""

from ollama import chat


def get_text_ollama(image_path: str, model: str = "glm-ocr") -> str:
    """Wysyła obraz do lokalnego modelu Ollama i zwraca wyekstrahowany tekst."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "Extract all text from this image. Return only the raw text, no commentary.",
                "images": [image_bytes],
            }
        ],
    )
    return response.message.content.strip()