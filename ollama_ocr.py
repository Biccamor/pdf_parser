"""
Moduł OCR i strukturyzacji CV przez lokalne modele Ollama.

Funkcje:
    get_text_ollama(image_path, model)  — OCR obrazka przez glm-ocr
    extract_cv_structure(raw_text, model) — strukturyzacja tekstu do JSON CV przez llama3.1
"""

from ollama import chat, ResponseError
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

class PersonInfo(BaseModel):
    name: Optional[str] = Field(
        None, 
        description="Full name of the candidate. Combine first and last name. If not found, return null."
    )
    email: Optional[str] = Field(
        None, 
        description="Email address. If not found, return null."
    )
    phone: Optional[str] = Field(
        None, 
        description="Phone number. If not found, return null."
    )
    address: Optional[str] = Field(
        None, 
        description="Home address, city, or location. If not found, return null."
    )

class CVData(BaseModel):
    person_info: PersonInfo = Field(
        default_factory=PersonInfo, 
        description="Candidate's basic contact and personal information."
    )
    education: List[str] = Field(
        default_factory=list, 
        description="List of educational institutions, degrees, and years of study. Keep original language. ALWAYS include dates if present. Example: ['Warsaw University - Computer Science (2015-2020)']."
    )
    experience: List[str] = Field(
        default_factory=list, 
        description="Employment history. Keep original language. ALWAYS include dates, job title, and company name. Example: ['Senior Developer at Google (2020-2023)']."
    )
    skills: List[str] = Field(
        default_factory=list, 
        description="List of hard and soft skills. If they are in categories keep category names too and order them as they are in the CV. Keep concise. Example: ['Python', 'SQL', 'Time management']."
    )
    extra: List[str] = Field(
        default_factory=list, 
        description="Additional information: foreign languages, driver's license, certificates, hobbies. If none found in CV, return an empty list []."
    )


def get_text_ollama(image_path: str, model: str = "glm-ocr:latest") -> str:
    """Wysyła obraz do lokalnego modelu Ollama i zwraca wyekstrahowany tekst."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = """Extract ALL visible text from this document image.
RULES:
- Return ONLY the raw extracted text — no markdown, no code blocks, no explanations.
- Preserve the original reading order and line breaks.
- Keep all values in their original language.
- Skip any embedded images, icons, logos, or decorative elements."""

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


def extract_cv_structure(raw_text: str, model: str = "llama3.1") -> dict:
    # Guard clause — przed budowaniem prompta
    if not raw_text.strip():
        return CVData().model_dump()

    prompt = f"""You are a CV parser. Extract structured information from the CV text below.
RULES:
- Keep all values in their original language.
- Always include dates/years in experience and education entries if present.
- Combine first and last name into a single 'name' field.
- If a field has no data, return null for strings or [] for arrays.
- NEVER invent, guess or fill in missing data — if unsure, return null.
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