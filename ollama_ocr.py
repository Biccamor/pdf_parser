"""
Moduł OCR i strukturyzacji CV przez lokalne modele Ollama.

Funkcje:
    get_text_ollama(image_path, model)  — OCR obrazka przez glm-ocr
    extract_cv_structure(raw_text, model) — strukturyzacja tekstu do JSON CV przez qwen3:4b
"""

import json
import re
from ollama import chat, ResponseError
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, List

class PersonInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class CVData(BaseModel):
    person_info: PersonInfo
    education: List[str] = []
    experience: List[str] = []
    skills: List[str] = []
    extra: List[Optional[str]] = []

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
            options={"temperature": 0},
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    return response.message.content.strip()


def extract_cv_structure(raw_text: str, model: str = "qwen3:4b") -> dict:
    # Guard clause — przed budowaniem prompta
    if not raw_text.strip():
        return CVData().model_dump()

    prompt = f"""You are a CV parser. Extract information from the CV text below.
Keep all values in their original language.
If a field has no data, use null for strings or [] for arrays.
For experience and education entries, include dates/years if present.
Combine first and last name into a single 'name' field.


CV TEXT:
{raw_text}"""

    try:
        response = chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=CVData.model_json_schema(),
            options={"temperature": 0},
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    try:
        return CVData.model_validate_json(response.message.content).model_dump()
    except Exception:
        return CVData().model_dump()