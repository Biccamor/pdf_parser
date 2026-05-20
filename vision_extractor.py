# -*- coding: utf-8 -*-
"""
Vision extractor - Qwen2.5-VL for CV text extraction from images.

Functions:
    extract_cv_with_vision(image_path, model) - returns structured JSON without personal data.
"""

import logging
import base64
from pathlib import Path

from pydantic import ValidationError
import requests

from cv_schema import CVData
from prompt import _QWEN_VISION_SYSTEM_PROMPT, _QWEN_VISION_USER_PROMPT

logger = logging.getLogger(__name__)


async def extract_cv_with_vision(image_path: str, model: str = "qwen2.5-vl-7b") -> dict:
    """
    Send image to Qwen2.5-VL and return structured CV without personal data.
    
    Args:
        image_path: path to CV page image
        model: model name in Ollama (default qwen2.5-vl-7b)
    
    Returns:
        CVData dict or empty CVData if parsing fails
    """
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    except FileNotFoundError:
        logger.error(f"Image file not found: {image_path}")
        return CVData().model_dump()

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": _QWEN_VISION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": _QWEN_VISION_USER_PROMPT,
                "images": [image_base64],
            },
        ],
        "stream": False,
        "format": CVData.model_json_schema(),
        "options": {"temperature": 0, "num_ctx": 8192},
    }

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        raw_response = result.get("message", {}).get("content", "")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return CVData().model_dump()

    if not raw_response.strip():
        logger.warning("Empty response from Qwen model")
        return CVData().model_dump()

    logger.info(f"Qwen raw response ({len(raw_response)} chars): {raw_response[:500]}")

    try:
        return CVData.model_validate_json(raw_response).model_dump()
    except ValidationError as e:
        logger.warning(f"Failed to parse Qwen response: {e}")
        return CVData().model_dump()


async def extract_text_from_assembled(raw_text: str, model: str = "qwen2.5-vl-7b") -> dict:
    """
    Send assembled region text to Qwen for final structured CV extraction.
    
    Args:
        raw_text: assembled text from all regions (no images)
        model: model name in Ollama
    
    Returns:
        CVData dict or empty CVData if parsing fails
    """
    if not raw_text.strip():
        logger.warning("Empty assembled text")
        return CVData().model_dump()
    
    from prompt import _ASSEMBLED_TEXT_PROMPT_TEMPLATE
    prompt = _ASSEMBLED_TEXT_PROMPT_TEMPLATE.format(raw_text=raw_text)
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "format": CVData.model_json_schema(),
        "options": {"temperature": 0, "num_ctx": 16384},
    }
    
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        raw_response = result.get("message", {}).get("content", "")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return CVData().model_dump()
    
    if not raw_response.strip():
        logger.warning("Empty response from Qwen model")
        return CVData().model_dump()
    
    logger.info(f"Qwen raw response ({len(raw_response)} chars): {raw_response[:500]}")
    
    try:
        return CVData.model_validate_json(raw_response).model_dump()
    except ValidationError as e:
        logger.warning(f"Failed to parse Qwen response: {e}")
        return CVData().model_dump()



    """
    Merge data from multiple CV pages into one structure.
    
    Args:
        cv_pages: list of CVData dicts from individual pages
    
    Returns:
        Merged CVData
    """
    merged = CVData()
    
    for page_data in cv_pages:
        if not page_data:
            continue
        
        try:
            page_cv = CVData.model_validate(page_data)
            
            merged.experience.extend(page_cv.experience)
            merged.education.extend(page_cv.education)
            
            merged.skills.programming_languages.extend(page_cv.skills.programming_languages)
            merged.skills.frameworks_and_libraries.extend(page_cv.skills.frameworks_and_libraries)
            merged.skills.tools_and_platforms.extend(page_cv.skills.tools_and_platforms)
            merged.skills.other.extend(page_cv.skills.other)
            
            merged.extras.extend(page_cv.extras)
        except Exception as e:
            logger.warning(f"Failed to merge page data: {e}")
            continue
    
    # Remove duplicates
    merged.experience = list({e.title: e for e in merged.experience}.values())
    merged.education = list({e.degree: e for e in merged.education}.values())
    merged.skills.programming_languages = list(set(merged.skills.programming_languages))
    merged.skills.frameworks_and_libraries = list(set(merged.skills.frameworks_and_libraries))
    merged.skills.tools_and_platforms = list(set(merged.skills.tools_and_platforms))
    merged.skills.other = list(set(merged.skills.other))
    
    return merged.model_dump()
