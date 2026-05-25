import io
import os
import sys
import tempfile

# ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fitz
import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from main import render_page_as_image, merge_cv_pages, app
from cv_schema import CVData


def _make_pdf_bytes(text_content: str = "") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    if text_content:
        page.insert_text((72, 72), text_content, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_render_page_as_image_creates_jpg(tmp_path):
    pdf_path = tmp_path / "one.pdf"
    pdf_path.write_bytes(_make_pdf_bytes("Hello"))

    image_path = render_page_as_image(str(pdf_path), 0)
    try:
        assert os.path.exists(image_path)
        assert image_path.endswith(".jpg")
    finally:
        if os.path.exists(image_path):
            os.unlink(image_path)


def test_merge_cv_pages_merges_and_deduplicates():
    base = CVData().model_dump()

    # Two pages with overlapping entries
    p1 = {
        "experience": [
            {"title": "Dev", "company": "X", "start": "2023", "end": "2024", "description": [], "technologies": ["Python"]}
        ],
        "education": [
            {"degree": "BSc", "institution": "Uni", "start": "2018", "end": "2022"}
        ],
        "skills": base["skills"],
        "extras": [],
    }

    p2 = {
        "experience": [
            {"title": "Dev", "company": "X", "start": "2023", "end": "2024", "description": [], "technologies": ["Python"]}
        ],
        "education": [
            {"degree": "BSc", "institution": "Uni", "start": "2018", "end": "2022"}
        ],
        "skills": base["skills"],
        "extras": [],
    }

    merged = merge_cv_pages([p1, p2])
    # duplicates should be deduplicated
    assert len(merged["experience"]) == 1
    assert len(merged["education"]) == 1


def test_parser_endpoint_uses_vision_extractor(monkeypatch):
    client = TestClient(app)

    pdf_bytes = _make_pdf_bytes("Some text here")

    async def fake_extract(path):
        return CVData().model_dump()

    monkeypatch.setattr("main.extract_cv_with_vision", AsyncMock(side_effect=fake_extract))

    files = {"cv": ("cv.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    response = client.post("/parser", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["model"].startswith("qwen")
    assert data["cv"] == CVData().model_dump()
