"""
Moduł OCR i strukturyzacji CV przez lokalne modele Ollama.

Funkcje:
    get_text_ollama(image_path, model)  — OCR obrazka przez glm-ocr
    extract_cv_structure(raw_text, model) — strukturyzacja tekstu do JSON CV przez mistral:7b
"""

from ollama import chat, ResponseError
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List

class CVData(BaseModel):
    education: List[str] = Field(
        default_factory=list,
        description="List of educational institutions, degrees, and years of study. Keep original language. ALWAYS include dates if present. Example: ['Warsaw University - Computer Science (2015-2020)']. DO NOT include any personal names."
    )
    experience: List[str] = Field(
        default_factory=list,
        description="Employment history. Keep original language. ALWAYS include dates, job title, and company name. Example: ['Senior Developer at Google (2020-2023)']. DO NOT include any personal names or contact details."
    )
    skills: List[str] = Field(
        default_factory=list,
        description="List of hard and soft skills. If they are in categories keep category names too and order them as they are in the CV. Keep concise. Example: ['Python', 'SQL', 'Time management']."
    )
    extra: List[str] = Field(
        default_factory=list,
        description="Additional information: foreign languages, driver's license, certificates, hobbies. If none found in CV, return an empty list []. DO NOT include any personal names or contact details."
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
- Skip any embedded images, icons, logos, or decorative elements.
- CRITICAL: REMOVE all personal data before returning: full names, first names, last names, email addresses, phone numbers, home addresses, national ID numbers (e.g. PESEL), dates of birth, LinkedIn URLs, GitHub URLs, personal websites, or any other identifying information. Replace them with empty string or skip the line entirely."""

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


def extract_cv_structure(raw_text: str, model: str = "mistral:7b") -> dict:
    # Guard clause — przed budowaniem prompta
    if not raw_text.strip():
        return CVData().model_dump()

    system_prompt = """You are an expert CV/resume parser. Your task is to extract structured data from CV text.
IMPORTANT: The input text may come from a PDF parser and sections can appear interleaved or out of order.
You MUST identify content by its meaning, not just its position in the text.
- Education entries: universities, colleges, schools, degrees (Bachelor, Master, PhD, etc.), field of study, graduation years.
- Experience entries: job titles, company names, employment dates, work descriptions.
- Skills: technical tools, programming languages, soft skills.
- Extra: languages spoken, certificates, hobbies, awards, volunteering.

CRITICAL PRIVACY RULE — ABSOLUTE PROHIBITION:
You MUST NOT include ANY personal data in your output under any circumstances.
This includes but is not limited to:
  - Full names, first names, last names, initials
  - Email addresses
  - Phone numbers (mobile, landline, fax)
  - Home addresses, postal codes, cities of residence
  - National ID numbers (PESEL, SSN, passport number, etc.)
  - Dates of birth or age
  - Profile URLs (LinkedIn, GitHub, personal website, portfolio)
  - Any other identifying information
If any of the above appear in the source text, SKIP them entirely. Do not copy them into any field."""

    prompt = f"""Extract all CV information from the text below. Sections may be mixed or out of order — identify them by content.
RULES:
- Keep all values in their original language.
- Always include dates/years in experience and education entries.
- If a field has no data, return [] for arrays.
- NEVER invent or guess missing data.
- Education includes: universities, colleges, degrees, exchange semesters, thesis projects.
- Experience includes: jobs, internships, teaching assistant roles, part-time work.
- ABSOLUTE RULE: Do NOT copy any personal data into the output (names, emails, phones, addresses, IDs, URLs, date of birth). Skip them completely.

CV TEXT:
{raw_text}"""

    try:
        response = chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            format=CVData.model_json_schema(),
            options={"temperature": 0},
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    try:
        return CVData.model_validate_json(response.message.content).model_dump()
    except Exception:
        return CVData().model_dump()