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
from extraction import extract_text
from pathlib import Path
from prompt import SYSTEM_PROMPT, USER_PROMPT
# ─────────────────────────────────────────────
# KONFIGURACJA
# ─────────────────────────────────────────────

import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL    = "qwen3:30b-a3b"   # zmień na swój model
OCR_LANGUAGES   = ["en", "pl"]
MIN_TEXT_LENGTH = 80                # poniżej tej liczby znaków → traktuj stronę jako skan


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
