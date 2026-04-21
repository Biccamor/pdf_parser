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


@app.post("/parser")
async def main(cv: UploadFile = File(...)):

    header = await cv.read(2048)
    await cv.seek(0)
    typ = check_type(header)
    logger.info("File type: %s", typ)

    # --- TXT: prosty odczyt, bez OCR ---
    if typ == ".txt":
        raw_text = (await cv.read()).decode("utf-8")
        raw_text = delete_others_unicode(raw_text)
        cv_data = extract_cv_structure(raw_text)
        return {"model": "llama3.1", "cv": cv_data}

    # --- PDF / JPG / PNG: zapis do pliku tymczasowego ---
    # mkstemp zwraca (file_descriptor, path) — zamykamy fd od razu po zapisie,
    # żeby fitz / ollama mogły otworzyć plik (Windows nie pozwala na dwa uchwyty).
    fd, path_file = tempfile.mkstemp(suffix=typ)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await cv.read())

        # --- Obrazek: bezpośrednio GLM OCR ---
        if typ in (".jpg", ".jpeg", ".png"):
            model_name = "glm-ocr + qwen3:4b"
            logger.info("Processing image with GLM OCR")
            raw_text = get_text_ollama(path_file)
            logger.info("Image processed successfully")

        # --- PDF ---
        else:
            md_text = pymupdf4llm.to_markdown(path_file)

            with fitz.open(path_file) as doc:
                page_count = len(doc)

            if is_scanned_pdf(md_text, page_count):
                logger.info("Processing scanned PDF with GLM OCR")
                # Skan: renderuj każdą stronę do JPG → GLM OCR
                model_name = "glm-ocr + llama3.1"
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
                model_name = "pymupdf4llm + llama3.1"
                raw_text = md_text

        raw_text = delete_others_unicode(raw_text)
        logger.info("Extracting CV structure with llama3.1")
        cv_data = extract_cv_structure(raw_text)
        logger.info("CV structure extracted successfully")

    finally:
        os.unlink(path_file)

    return {"model": model_name, "cv": cv_data}