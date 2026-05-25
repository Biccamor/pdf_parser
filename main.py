import os
import sys
import tempfile
import logging
from contextlib import asynccontextmanager

import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from cv_schema import CVData
from vision_extractor import extract_cv_with_vision

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


def render_page_as_image(pdf_path: str, page_num: int, dpi: int = 200) -> str:
    with fitz.open(pdf_path) as doc:
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        pix.save(path, jpg_quality=95)
        return path


def merge_cv_pages(cv_pages: list[dict]) -> dict:
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
            logger.warning(f"Failed to merge page: {e}")

    # deduplikacja
    merged.experience = list({(e.title, e.company, e.start): e for e in merged.experience}.values())
    merged.education = list({(e.degree, e.institution): e for e in merged.education}.values())
    merged.skills.programming_languages = list(set(merged.skills.programming_languages))
    merged.skills.frameworks_and_libraries = list(set(merged.skills.frameworks_and_libraries))
    merged.skills.tools_and_platforms = list(set(merged.skills.tools_and_platforms))
    merged.skills.other = list(set(merged.skills.other))

    return merged.model_dump()


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


import traceback

@app.post("/parser")
async def parse_cv(cv: UploadFile = File(...)):
    try:
        logger.info(f"[PARSER] Starting PDF upload: {cv.filename}")
        
        header = await cv.read(4)
        if header != b"%PDF":
            logger.warning(f"[PARSER] Invalid PDF header: {header[:4]}")
            raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
        await cv.seek(0)
        logger.info("[PARSER] PDF header validated")

        fd, path_file = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                pdf_data = await cv.read()
                logger.info(f"[PARSER] PDF data read: {len(pdf_data)} bytes")
                f.write(pdf_data)

            logger.info(f"[PARSER] Opening PDF: {path_file}")
            with fitz.open(path_file) as doc:
                page_count = len(doc)
            logger.info(f"[PARSER] PDF has {page_count} page(s)")

            all_pages = []
            for page_num in range(page_count):
                logger.info(f"[PARSER] Rendering page {page_num} to image")
                image_path = render_page_as_image(path_file, page_num)
                logger.info(f"[PARSER] Image saved to: {image_path}")
                try:
                    logger.info(f"[PARSER] Calling extract_cv_with_vision for page {page_num}")
                    cv_data = await extract_cv_with_vision(image_path)
                    logger.info(f"[PARSER] Extraction complete for page {page_num}")
                    all_pages.append(cv_data)
                except Exception as page_err:
                    logger.error(f"[PARSER] Error on page {page_num}: {page_err}", exc_info=True)
                    all_pages.append({})
                finally:
                    if os.path.exists(image_path):
                        os.unlink(image_path)
                        logger.info(f"[PARSER] Cleaned up image: {image_path}")

            logger.info(f"[PARSER] Merging {len(all_pages)} pages")
            final = merge_cv_pages(all_pages)
            logger.info(f"[PARSER] Merge complete")

        finally:
            if os.path.exists(path_file):
                os.unlink(path_file)
                logger.info(f"[PARSER] Cleaned up PDF: {path_file}")

        logger.info("[PARSER] Success!")
        return {"model": "qwen2.5-vl-7b", "cv": final}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PARSER] Unhandled error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))