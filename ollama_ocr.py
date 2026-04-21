"""
Moduł OCR i strukturyzacji CV przez lokalne modele Ollama.

Funkcje:
    get_text_ollama(image_path, model)  — OCR obrazka przez glm-ocr
    extract_cv_structure(raw_text, model) — strukturyzacja tekstu do JSON CV przez llama3.2:3b
"""

import json
import re
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


def extract_cv_structure(raw_text: str, model: str = "llama3.2:3b") -> dict:
    """
    Wysyła surowy tekst CV do modelu językowego i zwraca ustrukturyzowany słownik.

    Zwracany format:
    {
        "person_info": { "name", "email", "phone", "address" },
        "education":   [...],
        "experience":  [...],
        "skills":      [...],
        "extra":       "..."
    }
    """
    prompt = f"""You are a CV parser. Extract information from the CV text below, everything should be in original language and return ONLY a valid JSON object with this exact structure:

{{
  "person_info": {{
    "name": "full name or null",
    "email": "email address or null",
    "phone": "phone number or null",
    "address": "address or null"
  }},
  "education": ["list of education entries with years as strings"],
  "experience": ["list of work experience entries with years as strings"],
  "skills": ["list of skills as strings"],
  "extra": "any relevant information that does not fit the above categories, or null"
}}

Rules:
- Return ONLY the JSON object — no markdown, no code blocks, no explanations.
- Keep values in their original language.
- If a field has no data, use null for strings or [] for arrays.

CV TEXT:
{raw_text}"""

    response = chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.message.content.strip()

    # Wytnij JSON nawet jeśli model dołączył dodatkowy tekst
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    return json.loads(raw)