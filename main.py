import re
import tempfile
import logging
import os

import fitz
import pymupdf4llm
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ocr import get_text_ollama
from cv_extractor import extract_cv_structure
from criterias import delete_others_unicode, is_scanned_pdf

logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: zmienic przed deployem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def clean_cv_markdown(text: str) -> str:
    """Czyści artefakty markdown powstałe przy parsowaniu PDF."""
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'#{1,6}\s*\*{0,2}(.*?)\*{0,2}\s*$', r'\1', text, flags=re.MULTILINE)
    return text


@app.post("/parser")
async def parse_cv(cv: UploadFile = File(...)):
    header = await cv.read(4)
    if header != b"%PDF":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    await cv.seek(0)

    fd, path_file = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await cv.read())

        md_text = pymupdf4llm.to_markdown(path_file)
        md_text = clean_cv_markdown(md_text)

        with fitz.open(path_file) as doc:
            page_count = len(doc)

        if is_scanned_pdf(md_text, page_count):
            logger.info("Scanned PDF detected — processing with GLM OCR")
            model_name = "glm-ocr + qwen3.6:35b-a3b"
            raw_text = ""
            with fitz.open(path_file) as doc:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300, alpha=False)
                    page_jpg = f"{path_file}_page_{i}.jpg"
                    pix.save(page_jpg)
                    try:
                        raw_text += get_text_ollama(page_jpg) + "\n\n"
                        logger.info("Page %d processed", i)
                    finally:
                        os.unlink(page_jpg)
        else:
            logger.info("Digital PDF detected — processing with pymupdf4llm")
            model_name = "pymupdf4llm + qwen3.6:35b-a3b"
            raw_text = md_text

        raw_text = delete_others_unicode(raw_text)
        logger.info("Extracting CV structure")
        cv_data = extract_cv_structure(raw_text)
        logger.info("CV structure extracted successfully")

    finally:
        os.unlink(path_file)

    return {"model": model_name, "cv": cv_data}