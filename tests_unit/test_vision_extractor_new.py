import json
import os
import sys
import base64
from unittest.mock import patch, MagicMock, AsyncMock

# ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import httpx

from cv_schema import CVData
from vision_extractor import extract_cv_with_vision


def test_missing_file_returns_default():
    import asyncio

    result = asyncio.run(extract_cv_with_vision("nonexistent_file.jpg"))
    assert result == CVData().model_dump()


@patch("vision_extractor.httpx.AsyncClient")
def test_connection_error_returns_default(mock_client, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(side_effect=httpx.ConnectError("conn error"))
    mock_client.return_value.__aenter__.return_value = mock_instance

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.httpx.AsyncClient")
def test_timeout_error_returns_default(mock_client, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_client.return_value.__aenter__.return_value = mock_instance

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.httpx.AsyncClient")
def test_empty_response_returns_default(mock_client, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "   "}}
    
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_client.return_value.__aenter__.return_value = mock_instance

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.httpx.AsyncClient")
def test_invalid_json_response_returns_default(mock_client, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_response = MagicMock()
    bad = json.dumps({"experience": "notalist"})
    mock_response.json.return_value = {"message": {"content": bad}}
    
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_client.return_value.__aenter__.return_value = mock_instance

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.httpx.AsyncClient")
def test_valid_response_parsed(mock_client, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    valid = CVData().model_dump()
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": json.dumps(valid)}}
    
    mock_instance = AsyncMock()
    mock_instance.post = AsyncMock(return_value=mock_response)
    mock_client.return_value.__aenter__.return_value = mock_instance

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == valid
