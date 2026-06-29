"""Konwersja base64 ↔ PDF."""

import base64
import os


def save_bytes_as_pdf(directory: str, b64_data: str, file_name: str) -> str:
    """Dekoduj base64 i zapisz jako PDF. Zwraca pełną ścieżkę."""
    os.makedirs(directory, exist_ok=True)

    if not file_name.endswith(".pdf"):
        file_name = f"{file_name}.pdf"

    full_path = os.path.join(directory, file_name)

    pdf_bytes = base64.b64decode(b64_data)
    with open(full_path, "wb") as f:
        f.write(pdf_bytes)

    return full_path
