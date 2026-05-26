"""
CV Parser — kompletny pipeline
PDF (text/skan/wielokolumnowy) → tekst → LLM → JSON

Wymagania:
    pip install pymupdf surya-ocr ollama

Użycie:
    from cv_parser import parse_cv
    result = parse_cv("cv.pdf")
"""

import json
import re
import fitz  # pymupdf
from pathlib import Path
from typing import Optional
import urllib.request

# ─────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────

import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL    = "qwen3:30b-a3b"   # zmień na swój model
OCR_LANGUAGES   = ["en", "pl"]
MIN_TEXT_LENGTH = 80                # poniżej tej liczby znaków → traktuj stronę jako skan


# ─────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a CV parser. Extract data from CV text and return ONLY valid JSON.

ABSOLUTE RULES:
- Return ONLY valid JSON. No markdown, no explanation, no preamble.
- NEVER invent or infer data. If it is not in the text, it does not exist.
- NEVER include personal identifiers: full name, email, phone, address, URLs.
- Use null for missing optional strings, [] for missing lists.

JSON SCHEMA:
{
  "experience": [
    {
      "title": string,
      "company": string,
      "start": string or null,
      "end": string or null,
      "location": string or null,
      "description": [string],
      "technologies": [string]
    }
  ],
  "education": [
    {
      "degree": string,
      "field": string,
      "institution": string,
      "start": string or null,
      "end": string or null,
      "notes": string or null
    }
  ],
  "skills": {
    "programming_languages": [string],
    "frameworks_and_libraries": [string],
    "tools_and_platforms": [string],
    "other": [string]
  },
  "languages": [
    { "name": string, "level": string or null }
  ],
  "extras": [
    {
      "category": string,
      "items": [
        {
          "title": string,
          "date": string or null,
          "description": string or null,
          "details": [string]
        }
      ]
    }
  ]
}

ROUTING RULES:

experience[].description  → bullet points listed under that role, verbatim
experience[].technologies → only tools/software explicitly named under that specific role, else []

education[].notes         → GPA, honors, Dean's List, thesis, scholarships — as one string
                            DO NOT copy these into extras[]

skills[]                  → ONLY what is in the Skills section
  programming_languages   → Python, SQL, Java, C++, HTML, CSS, JavaScript...
  frameworks_and_libraries→ React, Django, FastAPI, Spring...
  tools_and_platforms     → Docker, AWS, Git, Figma, Jira...
  other                   → soft skills, methodologies, domain knowledge
  If CV has no programming languages → []

languages[]               → spoken/written human languages only, never in skills.other
                            If none listed → []

extras[]                  → ONLY for sections explicitly labeled in the CV:
                            Certifications, Awards, Projects, Publications, Volunteering
                            DO NOT fabricate categories from experience bullets
                            DO NOT duplicate data from education[] or experience[]
                            If no such section exists → []

DEDUPLICATION: every piece of information appears in EXACTLY ONE field.
"""

USER_PROMPT = """Parse this CV text and return ONLY valid JSON. No markdown. No invented data.

CV TEXT:
{text}
"""


# ─────────────────────────────────────────────
# 1. EKSTRAKCJA TEKSTU Z PDF
# ─────────────────────────────────────────────

def _cluster_x_positions(x_positions: list[float], page_width: float, gap_ratio: float = 0.12) -> list[float]:
    """Wykryj początki kolumn na podstawie skupisk pozycji x bloków."""
    if not x_positions:
        return [0.0]

    sorted_x = sorted(set(x_positions))
    gap = page_width * gap_ratio

    clusters: list[list[float]] = [[sorted_x[0]]]
    for x in sorted_x[1:]:
        if x - clusters[-1][-1] > gap:
            clusters.append([])
        clusters[-1].append(x)

    return [c[0] for c in clusters]


def _extract_text_multicolumn(page: fitz.Page) -> str:
    """Wyciągnij tekst ze strony z obsługą wielu kolumn."""
    blocks = [b for b in page.get_text("blocks") if b[4].strip()]
    if not blocks:
        return ""

    page_width = page.rect.width

    # pozycje x wszystkich bloków
    x_starts = [b[0] for b in blocks]
    col_starts = _cluster_x_positions(x_starts, page_width)
    n_cols = len(col_starts)

    if n_cols == 1:
        # jedna kolumna — sortuj po y
        blocks.sort(key=lambda b: b[1])
        return "\n".join(b[4].strip() for b in blocks)

    # wiele kolumn — przypisz każdy blok do kolumny po x
    col_width = page_width / n_cols
    columns: list[list] = [[] for _ in range(n_cols)]

    for b in blocks:
        # znajdź najbliższy col_start
        col_idx = min(
            range(n_cols),
            key=lambda i: abs(b[0] - col_starts[i])
        )
        columns[col_idx].append(b)

    # sortuj każdą kolumnę po y, złącz kolumna po kolumnie
    result_parts = []
    for col in columns:
        col.sort(key=lambda b: b[1])
        result_parts.append("\n".join(b[4].strip() for b in col))

    return "\n\n".join(result_parts)

def _ocr_page(page: fitz.Page) -> str:
    """OCR przez GLM-OCR w Ollama."""
    import base64

    pix = page.get_pixmap(dpi=300)
    img_b64 = base64.b64encode(pix.tobytes("png")).decode()

    payload = json.dumps({
        "model": "glm-ocr:latest",
        "prompt": "Extract all text from this document image. Preserve reading order. Return only the text.",
        "images": [img_b64],
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=800) as resp:
        data = json.loads(resp.read())
    return data["response"]



def extract_text(pdf_path: str) -> str:
    """
    Główna funkcja ekstrakcji tekstu z PDF.
    Obsługuje: text-PDF, skan, 1/2/3 kolumny.
    """
    doc = fitz.open(pdf_path)
    pages_text = []

    for page_num, page in enumerate(doc, start=1):
        raw_text = page.get_text("text").strip()

        if len(raw_text) >= MIN_TEXT_LENGTH:
            # strona ma tekst — użyj wielokolumnowej ekstrakcji
            text = _extract_text_multicolumn(page)
            source = "pymupdf"
        else:
            # skan lub strona bez tekstu — użyj OCR
            print(f"[Strona {page_num}] Mało tekstu ({len(raw_text)} znaków) → OCR")
            text = _ocr_page(page)
            source = "surya"

        if text.strip():
            pages_text.append(text.strip())

    doc.close()
    return "\n\n".join(pages_text)


# ─────────────────────────────────────────────
# 2. POSTPROCESSING JSON
# ─────────────────────────────────────────────

EDUCATION_NOISE = {
    "gpa", "cum laude", "magna cum laude", "summa cum laude",
    "dean's list", "deans list", "thesis", "scholarship", "presidential",
    "honor", "honours",
}

CERT_KEYWORDS = {"certification", "certificate", "certified", "licence", "license"}


def _is_education_noise(item: dict) -> bool:
    text = ((item.get("title") or "") + " " + (item.get("description") or "")).lower()
    return any(kw in text for kw in EDUCATION_NOISE)


def _dedup_string(s: str, sep: str = ",") -> str:
    parts = [p.strip() for p in s.split(sep)]
    seen: set[str] = set()
    result = []
    for p in parts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            result.append(p)
    return sep.join(result)


def postprocess(cv: dict) -> dict:
    """
    Napraw typowe błędy routingu małych modeli:
    - GPA/Dean's List w extras → usuń
    - certyfikaty w skills.other → przenieś do extras
    - duplikaty w education.notes
    - odwrócone daty start/end
    """

    # 1. Wyczyść extras z danych które należą do education
    cleaned_extras = []
    for category in cv.get("extras", []):
        clean_items = [i for i in category.get("items", []) if not _is_education_noise(i)]
        if clean_items:
            cleaned_extras.append({**category, "items": clean_items})
    cv["extras"] = cleaned_extras

    # 2. Wyciągnij certyfikaty z skills.other → przenieś do extras
    cert_items_found = []
    clean_other = []
    for skill in cv.get("skills", {}).get("other", []):
        if any(kw in skill.lower() for kw in CERT_KEYWORDS):
            cert_items_found.append(skill)
        else:
            clean_other.append(skill)
    cv["skills"]["other"] = clean_other

    if cert_items_found:
        cert_cat = next((c for c in cv["extras"] if c["category"] == "Certifications"), None)
        new_items = [
            {"title": c, "date": None, "description": None, "details": []}
            for c in cert_items_found
            if not (cert_cat and any(i["title"].lower() == c.lower() for i in cert_cat["items"]))
        ]
        if new_items:
            if cert_cat:
                cert_cat["items"].extend(new_items)
            else:
                cv["extras"].append({"category": "Certifications", "items": new_items})

    # 3. Deduplikacja w education.notes
    for edu in cv.get("education", []):
        if edu.get("notes"):
            edu["notes"] = _dedup_string(edu["notes"])

    # 4. Napraw odwrócone daty
    for entry in cv.get("education", []) + cv.get("experience", []):
        s, e = entry.get("start"), entry.get("end")
        if s and e and e not in ("CURRENT", "Present", "present") and s > e:
            entry["start"], entry["end"] = e, s

    return cv


# ─────────────────────────────────────────────
# 3. LLM — PARSOWANIE JSON
# ─────────────────────────────────────────────

def _call_ollama(text: str) -> str:
    """Wyślij tekst do Ollama i odbierz odpowiedź."""
    import urllib.request

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_PROMPT.format(text=text)},
        ],
        "stream": False,
        "options": {"temperature": 0},
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=700) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


def _parse_json_response(raw: str) -> dict:
    """Wyciągnij JSON z odpowiedzi modelu (usuń markdown jeśli jest)."""
    raw = raw.strip()

    # usuń ```json ... ``` jeśli model dodał
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ─────────────────────────────────────────────
# 4. GŁÓWNA FUNKCJA
# ─────────────────────────────────────────────

def parse_cv(pdf_path: str, save_text: bool = False) -> dict:
    """
    Sparsuj CV z PDF → JSON.

    Args:
        pdf_path:  ścieżka do pliku PDF
        save_text: jeśli True, zapisz wyciągnięty tekst do .txt (debug)

    Returns:
        dict z polami: experience, education, skills, languages, extras
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Plik nie istnieje: {pdf_path}")

    # 1. Wyciągnij tekst
    print(f"[1/3] Ekstrakcja tekstu: {path.name}")
    text = extract_text(str(path))

    if not text.strip():
        raise ValueError("Nie udało się wyciągnąć żadnego tekstu z PDF.")

    if save_text:
        txt_path = path.with_suffix(".extracted.txt")
        txt_path.write_text(text, encoding="utf-8")
        print(f"      Tekst zapisany: {txt_path}")

    print(f"      Wyciągnięto {len(text)} znaków")

    # 2. Parsuj LLM
    print(f"[2/3] Parsowanie przez LLM ({OLLAMA_MODEL})...")
    raw = _call_ollama(text)

    try:
        cv = _parse_json_response(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM zwrócił niepoprawny JSON: {e}\n\nOdpowiedź:\n{raw[:500]}")

    # 3. Postprocessing
    print("[3/3] Postprocessing...")
    cv = postprocess(cv)

    print("      Gotowe.")
    return cv


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Użycie: python cv_parser.py plik.pdf [--save-text]")
        sys.exit(1)

    pdf = sys.argv[1]
    save = "--save-text" in sys.argv

    try:
        result = parse_cv(pdf, save_text=save)
        print(json.dumps({"cv": result}, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)
