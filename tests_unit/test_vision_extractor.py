import json
import os
import sys
import base64
from unittest.mock import patch, MagicMock

# ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import requests

from cv_schema import CVData
from vision_extractor import extract_cv_with_vision

def test_missing_file_returns_default():
    import asyncio

    result = asyncio.run(extract_cv_with_vision("nonexistent_file.jpg"))
    assert result == CVData().model_dump()


@patch("vision_extractor.requests.post")
def test_requests_exception_returns_default(mock_post, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_post.side_effect = requests.exceptions.RequestException("conn error")

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.requests.post")
def test_empty_response_returns_default(mock_post, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"message": {"content": "   "}}
    mock_post.return_value = mock_response

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.requests.post")
def test_invalid_json_response_returns_default(mock_post, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # content that does not match schema (experience should be list)
    bad = json.dumps({"experience": "notalist"})
    mock_response.json.return_value = {"message": {"content": bad}}
    mock_post.return_value = mock_response

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == CVData().model_dump()


@patch("vision_extractor.requests.post")
def test_valid_response_parsed(mock_post, tmp_path):
    import asyncio

    img = tmp_path / "img.jpg"
    img.write_bytes(b"\xff\xd8fakejpg")

    valid = CVData().model_dump()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"message": {"content": json.dumps(valid)}}
    mock_post.return_value = mock_response

    result = asyncio.run(extract_cv_with_vision(str(img)))
    assert result == valid
