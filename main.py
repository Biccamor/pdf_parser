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

    # --- TXT: prosty odczyt, bez OCR ---
    if typ == ".txt":
        raw_text = (await cv.read()).decode("utf-8")
        raw_text = delete_others_unicode(raw_text)
        cv_data = extract_cv_structure(raw_text)
        return {"model": "llama3.2:3b", "cv": cv_data}

    # --- PDF / JPG / PNG: zapis do pliku tymczasowego ---
    # mkstemp zwraca (file_descriptor, path) — zamykamy fd od razu po zapisie,
    # żeby fitz / ollama mogły otworzyć plik (Windows nie pozwala na dwa uchwyty).
    fd, path_file = tempfile.mkstemp(suffix=typ)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await cv.read())

        # --- Obrazek: bezpośrednio GLM OCR ---
        if typ in (".jpg", ".jpeg", ".png"):
            model_name = "glm-ocr + llama3.2:3b"
            raw_text = get_text_ollama(path_file)

        # --- PDF ---
        else:
            md_text = pymupdf4llm.to_markdown(path_file)

            with fitz.open(path_file) as doc:
                page_count = len(doc)

            if is_scanned_pdf(md_text, page_count):
                # Skan: renderuj każdą stronę do JPG → GLM OCR
                model_name = "glm-ocr + llama3.2:3b"
                raw_text = ""
                with fitz.open(path_file) as doc:
                    for i, page in enumerate(doc):
                        pix = page.get_pixmap(dpi=300, alpha=False)
                        page_jpg = f"{path_file}_page_{i}.jpg"
                        pix.save(page_jpg)
                        try:
                            raw_text += get_text_ollama(page_jpg) + "\n\n"
                        finally:
                            os.unlink(page_jpg)
            else:
                # Cyfrowy PDF: pymupdf4llm wystarczy
                model_name = "pymupdf4llm + llama3.2:3b"
                raw_text = md_text

        raw_text = delete_others_unicode(raw_text)
        cv_data = extract_cv_structure(raw_text)

    finally:
        os.unlink(path_file)

    return {"model": model_name, "cv": cv_data}