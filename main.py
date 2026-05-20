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
        header = await cv.read(4)
        if header != b"%PDF":
            raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
        await cv.seek(0)

        fd, path_file = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(await cv.read())

            with fitz.open(path_file) as doc:
                page_count = len(doc)

            all_pages = []
            for page_num in range(page_count):
                image_path = render_page_as_image(path_file, page_num)
                try:
                    cv_data = await extract_cv_with_vision(image_path)
                    all_pages.append(cv_data)
                finally:
                    os.unlink(image_path)

            final = merge_cv_pages(all_pages)

        finally:
            os.unlink(path_file)

        return {"model": "qwen2.5-vl-7b", "cv": final}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unhandled error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))