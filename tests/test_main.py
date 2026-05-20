"""Testy integracyjne endpointu /parser — FastAPI TestClient + mocki."""

import json
import io
import os
import tempfile

import pytest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
import fitz

from main import app
from cv_schema import CVData


client = TestClient(app)


def _make_pdf_bytes(text_content: str = "") -> bytes:
    """Tworzy minimalny poprawny PDF z podanym tekstem (lub pusty)."""
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

    def test_pdf_header_check_reads_first_4_bytes(self):
        """Plik zaczynający się od %PDF ale z bzdurami dalej — przechodzi walidację header,
        ale fitz (PyMuPDF) rzuci błąd przy otwieraniu.
        """
        content = b"%PDF-1.4 garbage content"
        files = _make_upload(content)
        with pytest.raises(fitz.FileDataError):
            client.post("/parser", files=files)

    @patch("main._docling_available", False)
    def test_fallback_when_docling_unavailable(self):
        """Kiedy docling jest niedostępny, zwracany jest fallback model dump."""
        pdf_bytes = _make_pdf_bytes("Some text")
        files = _make_upload(pdf_bytes)
        response = client.post("/parser", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "qwen2.5-vl-7b (fallback)"
        assert "cv" in data

    @patch("main._docling_available", True)
    @patch("main.process_pdf_with_docling", new_callable=AsyncMock, create=True)
    @patch("main.extract_text_from_assembled", new_callable=AsyncMock)
    def test_normal_flow_with_docling(self, mock_extract, mock_process):
        """Normalny przepływ - docling dostępny, wyciąga tekst, potem qwen wyciąga CV."""
        mock_process.return_value = "Assembled text from regions"
        expected_cv = CVData(experience=[], education=[]).model_dump()
        mock_extract.return_value = expected_cv

        pdf_bytes = _make_pdf_bytes("Some text")
        files = _make_upload(pdf_bytes)
        response = client.post("/parser", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "qwen2.5-vl-7b (docling)"
        assert data["cv"] == expected_cv
        mock_process.assert_called_once()
        mock_extract.assert_called_once_with("Assembled text from regions", model="qwen2.5-vl-7b")

    @patch("main._docling_available", True)
    @patch("main.process_pdf_with_docling", new_callable=AsyncMock, create=True)
    def test_empty_text_from_docling(self, mock_process):
        """Jeśli docling zwróci pusty tekst, zwracamy pusty słownik CV bez wołania qwen."""
        mock_process.return_value = "   "
        
        pdf_bytes = _make_pdf_bytes("Some text")
        files = _make_upload(pdf_bytes)
        
        with patch("main.extract_text_from_assembled", new_callable=AsyncMock) as mock_extract:
            response = client.post("/parser", files=files)
            
            assert response.status_code == 200
            data = response.json()
            assert data["model"] == "qwen2.5-vl-7b (docling)"
            mock_process.assert_called_once()
            mock_extract.assert_not_called()

    @patch("main._docling_available", False)
    def test_temp_file_cleanup(self):
        """Plik tymczasowy jest usuwany po przetworzeniu, nawet w przypadku błędów."""
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

        for path in created_files:
            assert not os.path.exists(path), f"Temp file not cleaned up: {path}"
