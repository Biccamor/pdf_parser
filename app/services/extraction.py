import json
import urllib.request

import fitz  # pymupdf

from app.config import OLLAMA_BASE_URL, MIN_TEXT_LENGTH


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


def _extract_text_multicolumn(page: fitz.Page) -> str: #type: ignore
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

def _ocr_page(page: fitz.Page) -> str: #type: ignore
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
    doc = fitz.open(pdf_path) #type: ignore
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