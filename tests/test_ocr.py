"""Testy jednostkowe dla modułu ocr — ekstrakcja tekstu przez Ollama glm-ocr."""

import pytest
from unittest.mock import patch, mock_open, MagicMock, AsyncMock

from fastapi import HTTPException
from ollama import ResponseError

from ocr import get_text_ollama

pytestmark = pytest.mark.anyio

@pytest.fixture
def mock_image_file(tmp_path):
    """Tworzy tymczasowy plik 'obrazu' do testów."""
    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0fake_jpeg_data")
    return str(img)


class TestGetTextOllama:
    """Testy funkcji get_text_ollama."""

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_returns_extracted_text(self, mock_chat, mock_image_file):
        """Poprawna odpowiedź modelu → zwraca tekst."""
        mock_response = MagicMock()
        mock_response.message.content = "Education\nWarsaw University 2020"
        mock_chat.return_value = mock_response

        result = await get_text_ollama(mock_image_file)
        assert result == "Education\nWarsaw University 2020"

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_strips_whitespace(self, mock_chat, mock_image_file):
        """Odpowiedź z whitespace na brzegach → przycięta."""
        mock_response = MagicMock()
        mock_response.message.content = "  some text  \n\n"
        mock_chat.return_value = mock_response

        result = await get_text_ollama(mock_image_file)
        assert result == "some text"

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_passes_image_bytes_to_chat(self, mock_chat, mock_image_file):
        """Sprawdza, że bajty obrazu są przekazywane do modelu."""
        mock_response = MagicMock()
        mock_response.message.content = "text"
        mock_chat.return_value = mock_response

        await get_text_ollama(mock_image_file)

        call_args = mock_chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        assert messages[0]["images"] is not None
        assert len(messages[0]["images"]) == 1

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_uses_default_model(self, mock_chat, mock_image_file):
        """Domyślny model to glm-ocr:latest."""
        mock_response = MagicMock()
        mock_response.message.content = "text"
        mock_chat.return_value = mock_response

        await get_text_ollama(mock_image_file)

        call_args = mock_chat.call_args
        model = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model == "glm-ocr:latest"

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_custom_model(self, mock_chat, mock_image_file):
        """Przekazanie custom modelu."""
        mock_response = MagicMock()
        mock_response.message.content = "text"
        mock_chat.return_value = mock_response

        await get_text_ollama(mock_image_file, model="custom-ocr:v2")

        call_args = mock_chat.call_args
        model = call_args.kwargs.get("model") or call_args[1].get("model")
        assert model == "custom-ocr:v2"

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_response_error_raises_503(self, mock_chat, mock_image_file):
        """ResponseError z Ollama → HTTPException 503."""
        mock_chat.side_effect = ResponseError("model not found")

        with pytest.raises(HTTPException) as exc_info:
            await get_text_ollama(mock_image_file)
        assert exc_info.value.status_code == 503

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_connection_error_raises_503(self, mock_chat, mock_image_file):
        """ConnectionError → HTTPException 503."""
        mock_chat.side_effect = ConnectionError("refused")

        with pytest.raises(HTTPException) as exc_info:
            await get_text_ollama(mock_image_file)
        assert exc_info.value.status_code == 503

    @patch("ocr.AsyncClient.chat", new_callable=AsyncMock)
    async def test_temperature_zero(self, mock_chat, mock_image_file):
        """Temperature powinno być 0 (deterministyczne odpowiedzi)."""
        mock_response = MagicMock()
        mock_response.message.content = "text"
        mock_chat.return_value = mock_response

        await get_text_ollama(mock_image_file)

        call_args = mock_chat.call_args
        options = call_args.kwargs.get("options") or call_args[1].get("options")
        assert options["temperature"] == 0
