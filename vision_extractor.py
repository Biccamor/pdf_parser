import logging
import base64
from pydantic import ValidationError
import httpx
from cv_schema import CVData
from prompt import _VISION_SYSTEM_PROMPT, _VISION_USER_PROMPT

logger = logging.getLogger(__name__)

async def extract_cv_with_vision(image_path: str, model: str = "qwen3-vl:8b") -> dict:
    logger.info(f"[VISION] Starting extraction from: {image_path}, model={model}")
    
    try:
        logger.info(f"[VISION] Reading image file")
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        logger.info(f"[VISION] Image read: {len(image_bytes)} bytes")
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    except FileNotFoundError:
        logger.error(f"[VISION] Image file not found: {image_path}")
        return CVData().model_dump()
    except Exception as e:
        logger.error(f"[VISION] Error reading image: {e}", exc_info=True)
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
    logger.info(f"[VISION] Payload ready, model={model}")

    try:
        logger.info(f"[VISION] Posting to http://ollama:11434/api/chat (timeout=120s)")
        async with httpx.AsyncClient() as client:
            response = await client.post("http://ollama:11434/api/chat", json=payload, timeout=120)
        logger.info(f"[VISION] Response status: {response.status_code}")
        response.raise_for_status()
        raw_response = response.json().get("message", {}).get("content", "")
        logger.info(f"[VISION] Response received: {len(raw_response)} chars")
    except httpx.ConnectError as e:
        logger.error(f"[VISION] Connection error to Ollama (is it running on ollama:11434?): {e}")
        return CVData().model_dump()
    except httpx.TimeoutException as e:
        logger.error(f"[VISION] Timeout waiting for Ollama (model running on {model}?): {e}")
        return CVData().model_dump()
    except httpx.HTTPStatusError as e:
        logger.error(f"[VISION] HTTP error from Ollama: {e.response.status_code} - {e}")
        return CVData().model_dump()
    except Exception as e:
        logger.error(f"[VISION] Ollama request failed: {e}", exc_info=True)
        return CVData().model_dump()

    if not raw_response.strip():
        logger.warning("[VISION] Empty response from model")
        return CVData().model_dump()

    try:
        logger.info(f"[VISION] Parsing response JSON")
        result = CVData.model_validate_json(raw_response).model_dump()
        logger.info(f"[VISION] Successfully parsed CV data")
        return result
    except ValidationError as e:
        logger.warning(f"[VISION] Failed to parse response: {e}")
        logger.debug(f"[VISION] Raw response was: {raw_response[:500]}")
        return CVData().model_dump()
    except Exception as e:
        logger.error(f"[VISION] Unexpected error parsing response: {e}", exc_info=True)
        return CVData().model_dump()