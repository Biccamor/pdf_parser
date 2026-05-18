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
            "education": [
                {
                    "degree": "BSc",
                    "field": "Computer Science",
                    "institution": "Warsaw University of Technology",
                    "start": "2018",
                    "end": "2023",
                    "notes": None,
                }
            ],
            "experience": [
                {
                    "title": "Developer",
                    "company": "Google",
                    "start": "2023",
                    "end": "2024",
                    "location": None,
                    "description": ["Built microservices"],
                    "technologies": ["Python", "Docker"],
                }
            ],
            "skills": {
                "programming_languages": ["Python"],
                "frameworks_and_libraries": [],
                "tools_and_platforms": ["Docker"],
                "other": [],
            },
            "extras": [
                {
                    "category": "Languages",
                    "items": [
                        {"title": "English", "date": None, "description": "B2", "details": []}
                    ],
                }
            ],
        })
        mock_response = MagicMock()
        mock_response.message.content = cv_json
        mock_chat.return_value = mock_response

        result = extract_cv_structure("some cv text")

        assert len(result["education"]) == 1
        assert result["education"][0]["institution"] == "Warsaw University of Technology"
        assert len(result["experience"]) == 1
        assert result["experience"][0]["company"] == "Google"
        assert result["skills"]["programming_languages"] == ["Python"]
        assert len(result["extras"]) == 1
        assert result["extras"][0]["category"] == "Languages"

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
            "education": [
                {
                    "degree": "MSc",
                    "field": None,
                    "institution": "MIT",
                    "start": "2020",
                    "end": None,
                    "notes": None,
                }
            ],
            "experience": [],
            "skills": {
                "programming_languages": [],
                "frameworks_and_libraries": [],
                "tools_and_platforms": [],
                "other": [],
            },
            "extras": [],
        })
        mock_response = MagicMock()
        mock_response.message.content = cv_json
        mock_chat.return_value = mock_response

        result = extract_cv_structure("cv text")

        assert len(result["education"]) == 1
        assert result["education"][0]["institution"] == "MIT"
        assert result["experience"] == []
        assert result["extras"] == []

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
        """Domyślny model to mellum7b."""
        mock_response = MagicMock()
        mock_response.message.content = json.dumps(CVData().model_dump())
        mock_chat.return_value = mock_response

        extract_cv_structure("cv text")

        call_args = mock_chat.call_args
        model = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model == "mellum7b"

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

    @patch("cv_extractor.chat")
    def test_extras_multiple_categories(self, mock_chat):
        """Extras z wieloma kategoriami są poprawnie parsowane."""
        cv_json = json.dumps({
            "experience": [],
            "education": [],
            "skills": {
                "programming_languages": [],
                "frameworks_and_libraries": [],
                "tools_and_platforms": [],
                "other": [],
            },
            "extras": [
                {
                    "category": "Certifications",
                    "items": [
                        {"title": "AWS Solutions Architect", "date": "2023", "description": "Amazon", "details": []}
                    ],
                },
                {
                    "category": "Volunteering",
                    "items": [
                        {"title": "Mentor", "date": "2020", "description": "CoderDojo", "details": ["Teaching kids programming"]}
                    ],
                },
                {
                    "category": "Interests",
                    "items": [
                        {"title": "Chess", "date": None, "description": None, "details": []},
                        {"title": "Rock climbing", "date": None, "description": None, "details": []},
                    ],
                },
            ],
        })
        mock_response = MagicMock()
        mock_response.message.content = cv_json
        mock_chat.return_value = mock_response

        result = extract_cv_structure("cv with extras")

        assert len(result["extras"]) == 3
        categories = [e["category"] for e in result["extras"]]
        assert "Certifications" in categories
        assert "Volunteering" in categories
        assert "Interests" in categories
        # Check nested items
        volunteering = next(e for e in result["extras"] if e["category"] == "Volunteering")
        assert volunteering["items"][0]["details"] == ["Teaching kids programming"]
