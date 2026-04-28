"""
Moduł strukturyzacji CV przez lokalny LLM (Ollama).

Funkcje:
    extract_cv_structure(raw_text, model) — zwraca ustrukturyzowany słownik CV bez danych osobowych.
"""

from ollama import chat, ResponseError
from fastapi import HTTPException

from cv_schema import CVData


_SYSTEM_PROMPT = """You are an expert CV/resume parser. Your task is to extract structured data from CV text.
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

_USER_PROMPT_TEMPLATE = """Extract all CV information from the text below. Sections may be mixed or out of order — identify them by content.
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


def extract_cv_structure(raw_text: str, model: str = "qwen3.6-35b-a3b") -> dict:
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
            options={"temperature": 0},
        )
    except (ResponseError, ConnectionError) as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable ({model}): {e}")

    try:
        return CVData.model_validate_json(response.message.content).model_dump()
    except Exception:
        return CVData().model_dump()
