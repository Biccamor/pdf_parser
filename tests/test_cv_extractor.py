"""Testy jednostkowe dla modułu cv_extractor — strukturyzacja CV przez LLM."""

import json

import pytest
from unittest.mock import patch, MagicMock

from fastapi import HTTPException
from ollama import ResponseError

from cv_extractor import extract_cv_structure
from cv_schema import CVData


class TestExtractCvStructure:
    """Testy funkcji extract_cv_structure."""

    def test_empty_text_returns_default(self):
        """Pusty tekst → domyślny CVData bez wołania Ollama."""
        result = extract_cv_structure("")
        expected = CVData().model_dump()
        assert result == expected

    def test_whitespace_only_returns_default(self):
        """Same białe znaki → domyślny CVData."""
        result = extract_cv_structure("   \n\t  ")
        expected = CVData().model_dump()
        assert result == expected

    @patch("cv_extractor.chat")
    def test_valid_response_returns_parsed_data(self, mock_chat):
        """Poprawna odpowiedź JSON → zwraca sparsowane dane CV."""
        cv_json = json.dumps({
            "education": ["Warsaw University - CS (2018-2023)"],
            "experience": ["Dev at Google (2023-2024)"],
            "skills": ["Python", "Docker"],
            "extra": ["English B2"],
        })
        mock_response = MagicMock()
        mock_response.message.content = cv_json
        mock_chat.return_value = mock_response

        result = extract_cv_structure("some cv text")

        assert result["education"] == ["Warsaw University - CS (2018-2023)"]
        assert result["experience"] == ["Dev at Google (2023-2024)"]
        assert result["skills"] == ["Python", "Docker"]
        assert result["extra"] == ["English B2"]

    @patch("cv_extractor.chat")
    def test_invalid_json_returns_default(self, mock_chat):
        """Niepoprawny JSON z modelu → fallback na domyślny CVData."""
        mock_response = MagicMock()
        mock_response.message.content = "this is not json at all"
        mock_chat.return_value = mock_response

        result = extract_cv_structure("some cv text")
        expected = CVData().model_dump()
        assert result == expected

    @patch("cv_extractor.chat")
    def test_partial_json_fills_defaults(self, mock_chat):
        """Częściowy JSON (brakujące pola) → pola domyślne uzupełnione."""
        cv_json = json.dumps({
            "education": ["MIT (2020)"],
            "experience": [],
            "skills": [],
            "extra": [],
        })
        mock_response = MagicMock()
        mock_response.message.content = cv_json
        mock_chat.return_value = mock_response

        result = extract_cv_structure("cv text")

        assert result["education"] == ["MIT (2020)"]
        assert result["experience"] == []
        assert result["skills"] == []
        assert result["extra"] == []

    @patch("cv_extractor.chat")
    def test_response_error_raises_503(self, mock_chat):
        """ResponseError → HTTPException 503."""
        mock_chat.side_effect = ResponseError("model not loaded")

        with pytest.raises(HTTPException) as exc_info:
            extract_cv_structure("cv text")
        assert exc_info.value.status_code == 503

    @patch("cv_extractor.chat")
    def test_connection_error_raises_503(self, mock_chat):
        """ConnectionError → HTTPException 503."""
        mock_chat.side_effect = ConnectionError("connection refused")

        with pytest.raises(HTTPException) as exc_info:
            extract_cv_structure("cv text")
        assert exc_info.value.status_code == 503

    @patch("cv_extractor.chat")
    def test_prompt_contains_raw_text(self, mock_chat):
        """Sprawdza, że tekst CV jest zawarty w prompcie wysyłanym do modelu."""
        mock_response = MagicMock()
        mock_response.message.content = json.dumps(CVData().model_dump())
        mock_chat.return_value = mock_response

        raw = "UNIQUE_CV_CONTENT_12345"
        extract_cv_structure(raw)

        call_args = mock_chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_msg = messages[1]["content"]
        assert raw in user_msg

    @patch("cv_extractor.chat")
    def test_uses_default_model(self, mock_chat):
        """Domyślny model to qwen3.6-35b-a3b."""
        mock_response = MagicMock()
        mock_response.message.content = json.dumps(CVData().model_dump())
        mock_chat.return_value = mock_response

        extract_cv_structure("cv text")

        call_args = mock_chat.call_args
        model = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model == "qwen3.6-35b-a3b"

    @patch("cv_extractor.chat")
    def test_uses_json_schema_format(self, mock_chat):
        """Sprawdza, że format=CVData.model_json_schema() jest przekazywany."""
        mock_response = MagicMock()
        mock_response.message.content = json.dumps(CVData().model_dump())
        mock_chat.return_value = mock_response

        extract_cv_structure("cv text")

        call_args = mock_chat.call_args
        fmt = call_args.kwargs.get("format") or call_args[1].get("format")
        assert fmt == CVData.model_json_schema()
