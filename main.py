from fastapi import FastAPI, UploadFile, File
import tempfile
import logging
import os
from check_types import check_type
import pymupdf4llm
import fitz
from ollama_ocr import get_text_ollama, extract_cv_structure
from fastapi.middleware.cors import CORSMiddleware
from criterias import delete_others_unicode, is_scanned_pdf
import os
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: zmienic przed deployem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import re

def clean_cv_markdown(text: str) -> str:
    # zamień `wartość` na samą wartość — usuń inline backticki
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # usuń nadmiarowe nagłówki markdown (## **)
    text = re.sub(r'#{1,6}\s*\*{0,2}(.*?)\*{0,2}\s*$', r'\1', text, flags=re.MULTILINE)
    return text


@app.post("/parser")
async def main(cv: UploadFile = File(...)):

    header = await cv.read(2048)
    await cv.seek(0)
    typ = check_type(header)
    logger.info("File type: %s", typ)

    # --- PDF / JPG / PNG: zapis do pliku tymczasowego ---
    # mkstemp zwraca (file_descriptor, path) — zamykamy fd od razu po zapisie,
    # żeby fitz / ollama mogły otworzyć plik (Windows nie pozwala na dwa uchwyty).
    fd, path_file = tempfile.mkstemp(suffix=typ)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await cv.read())

        # # --- Obrazek: bezpośrednio GLM OCR ---
        # if typ in (".jpg", ".jpeg", ".png"):
        #     model_name = "glm-ocr + mistral:7b"
        #     logger.info("Processing image with GLM OCR")
        #     raw_text = get_text_ollama(path_file)
        #     logger.info("Image processed successfully")

        # # --- PDF ---
        # else:
        md_text = pymupdf4llm.to_markdown(path_file)
        md_text = clean_cv_markdown(md_text)
        with fitz.open(path_file) as doc:
            page_count = len(doc)

        if is_scanned_pdf(md_text, page_count):
            logger.info("Processing scanned PDF with GLM OCR")
            # Skan: renderuj każdą stronę do JPG → GLM OCR
            model_name = "glm-ocr + mistral:7b"
            raw_text = ""
            with fitz.open(path_file) as doc:
                for i, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=300, alpha=False)
                    page_jpg = f"{path_file}_page_{i}.jpg"
                    pix.save(page_jpg)
                    logger.info("Page saved successfully")
                    try:
                        raw_text += get_text_ollama(page_jpg) + "\n\n"
                    finally:
                        os.unlink(page_jpg)
                    logger.info("Page processed successfully")
        else:
            # Cyfrowy PDF: pymupdf4llm wystarczy
            logger.info("Processing digital PDF with pymupdf4llm")
            model_name = "pymupdf4llm + mistral:7b"
            raw_text = md_text

        raw_text = delete_others_unicode(raw_text)
        logger.info("Extracting CV structure with mistral:7b")
        cv_data = extract_cv_structure(raw_text)
        logger.info("CV structure extracted successfully")

    finally:
        os.unlink(path_file)

    return {"model": model_name, "cv": cv_data}