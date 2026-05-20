import logging
import base64
from pydantic import ValidationError
import requests
from cv_schema import CVData
from prompt import _VISION_SYSTEM_PROMPT, _VISION_USER_PROMPT

logger = logging.getLogger(__name__)

async def extract_cv_with_vision(image_path: str, model: str = "internvl2.5:26b-q4_K_M") -> dict:
    try:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        logger.error(f"Image file not found: {image_path}")
        return CVData().model_dump()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _VISION_SYSTEM_PROMPT},
            {"role": "user", "content": _VISION_USER_PROMPT, "images": [image_base64]},
        ],
        "stream": False,
        "format": CVData.model_json_schema(),
        "options": {"temperature": 0, "num_ctx": 8192},
    }

    try:
        response = requests.post("http://localhost:11434/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        raw_response = response.json().get("message", {}).get("content", "")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return CVData().model_dump()

    if not raw_response.strip():
        logger.warning("Empty response from Qwen")
        return CVData().model_dump()

    try:
        return CVData.model_validate_json(raw_response).model_dump()
    except ValidationError as e:
        logger.warning(f"Failed to parse Qwen response: {e}")
        return CVData().model_dump()