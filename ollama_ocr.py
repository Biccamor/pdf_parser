"""
Moduł OCR i strukturyzacji CV przez lokalne modele Ollama.

Funkcje:
    get_text_ollama(image_path, model)  — OCR obrazka przez glm-ocr
    extract_cv_structure(raw_text, model) — strukturyzacja tekstu do JSON CV przez llama3.2:3b
"""

import json
import re
from ollama import chat, ResponseError
from fastapi import HTTPException
from pydantic import BaseModel

class CVData(BaseModel):
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    experience: List[str]
    education: List[str]
    skills: List[str]
    extra: Optional[List[str]]

def get_text_ollama(image_path: str, model: str = "glm-ocr") -> str:
    """Wysyła obraz do lokalnego modelu Ollama i zwraca wyekstrahowany tekst."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = f"""You extract ALL text from image, don't extract images or picture tags, everything should be in original language and return ONLY the raw text, no commentary. 
    
    RULES:
    - Return ONLY the raw text — no markdown, no code blocks, no explanations.
    - Keep values in their original language.
    """

    try:
        response = chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_bytes],
                }
            ],
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    return response.message.content.strip()


def extract_cv_structure(raw_text: str, model: str = "qwen3:4b") -> dict:
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

    if not raw_text.strip():
        return {
            "person_info": {"name": None, "email": None, "phone": None, "address": None},
            "education": [],
            "experience": [],
            "skills": [],
            "extra": None,
        }

    try:
        response = chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=CVData.model_json_schema()
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    raw = response.message.content.strip()

    # Wytnij JSON nawet jeśli model dołączył dodatkowy tekst
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: zwroć surowy tekst w extra zamiast crashować
        return {
            "person_info": {"name": None, "email": None, "phone": None, "address": None},
            "education": [],
            "experience": [],
            "skills": [],
            "extra": raw,
        }