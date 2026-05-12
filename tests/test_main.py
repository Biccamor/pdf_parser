"""Testy integracyjne endpointu /parser — FastAPI TestClient + mocki."""

import json
import io

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from main import app
from cv_schema import CVData


client = TestClient(app)


def _make_pdf_bytes(text_content: str = "") -> bytes:
    """Tworzy minimalny poprawny PDF z podanym tekstem (lub pusty)."""
    # Minimalny PDF — header + pusty content stream
    # Wystarczający by przejść walidację %PDF header
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    if text_content:
        page.insert_text((72, 72), text_content, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_upload(content: bytes, filename: str = "cv.pdf"):
    """Tworzy plik do uploadu w formacie akceptowanym przez TestClient."""
    return {"cv": (filename, io.BytesIO(content), "application/pdf")}


class TestParserEndpoint:
    """Testy endpointu POST /parser."""

    def test_rejects_non_pdf(self):
        """Plik bez nagłówka %PDF → 400."""
        files = _make_upload(b"This is not a PDF file at all")
        response = client.post("/parser", files=files)
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_rejects_empty_file(self):
        """Pusty plik → 400."""
        files = _make_upload(b"")
        response = client.post("/parser", files=files)
        assert response.status_code == 400

    @patch("main.extract_cv_structure")
    @patch("main.pymupdf4llm")
    def test_digital_pdf_uses_pymupdf_path(self, mock_pymupdf4llm, mock_extract):
        """Cyfrowy PDF (dużo tekstu) → ścieżka pymupdf4llm."""
        long_text = "Education Warsaw University " * 50  # >100 chars/page
        mock_pymupdf4llm.to_markdown.return_value = long_text
        mock_extract.return_value = CVData().model_dump()

        pdf_bytes = _make_pdf_bytes("Some real text content here for testing purposes and more text")
        files = _make_upload(pdf_bytes)
        response = client.post("/parser", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "pymupdf4llm" in data["model"]
        mock_extract.assert_called_once()

    @patch("main.get_text_ollama")
    @patch("main.extract_cv_structure")
    @patch("main.pymupdf4llm")
    def test_scanned_pdf_uses_ocr_path(self, mock_pymupdf4llm, mock_extract, mock_ocr):
        """Skan (mało tekstu) → ścieżka GLM OCR."""
        mock_pymupdf4llm.to_markdown.return_value = ""  # brak tekstu = skan
        mock_ocr.return_value = "OCR extracted text"
        mock_extract.return_value = CVData().model_dump()

        pdf_bytes = _make_pdf_bytes()  # pusty PDF
        files = _make_upload(pdf_bytes)
        response = client.post("/parser", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "glm-ocr" in data["model"]
        mock_ocr.assert_called()

    @patch("main.extract_cv_structure")
    @patch("main.pymupdf4llm")
    def test_response_has_model_and_cv_keys(self, mock_pymupdf4llm, mock_extract):
        """Odpowiedź zawiera klucze 'model' i 'cv'."""
        mock_pymupdf4llm.to_markdown.return_value = "a" * 200
        expected_cv = {
            "education": ["MIT (2020)"],
            "experience": [],
            "skills": ["Python"],
            "extra": [],
        }
        mock_extract.return_value = expected_cv

        pdf_bytes = _make_pdf_bytes("Some text content")
        files = _make_upload(pdf_bytes)
        response = client.post("/parser", files=files)

        data = response.json()
        assert "model" in data
        assert "cv" in data
        assert data["cv"] == expected_cv

    @patch("main.extract_cv_structure")
    @patch("main.pymupdf4llm")
    def test_temp_file_cleanup(self, mock_pymupdf4llm, mock_extract):
        """Plik tymczasowy jest usuwany po przetworzeniu."""
        import os
        import tempfile

        mock_pymupdf4llm.to_markdown.return_value = "x" * 200
        mock_extract.return_value = CVData().model_dump()

        # Śledź pliki tworzone w tempdir
        created_files = []
        original_mkstemp = tempfile.mkstemp

        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            created_files.append(path)
            return fd, path

        with patch("main.tempfile.mkstemp", side_effect=tracking_mkstemp):
            pdf_bytes = _make_pdf_bytes("Content")
            files = _make_upload(pdf_bytes)
            client.post("/parser", files=files)

        # Sprawdź, że pliki zostały usunięte
        for path in created_files:
            assert not os.path.exists(path), f"Temp file not cleaned up: {path}"

    def test_pdf_header_check_reads_first_4_bytes(self):
        """Plik zaczynający się od %PDF ale z bzdurami dalej — przechodzi walidację header,
        ale pymupdf rzuci FileDataError bo plik jest uszkodzony.
        """
        import pymupdf

        content = b"%PDF-1.4 garbage content"
        files = _make_upload(content)
        with pytest.raises(pymupdf.FileDataError):
            client.post("/parser", files=files)
