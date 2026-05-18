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
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: zmienic przed deployem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


def clean_cv_markdown(text: str) -> str:
    # --- istniejące ---
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'#{1,6}\s+\*{0,2}(.*?)\*{0,2}\s*$', r'\1', text, flags=re.MULTILINE)
    text = re.sub(r'(?:\s+#\S+)+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)

    # --- nowe ---
    # Usuń pozostałe samotne backticki
    text = re.sub(r'`+', '', text)
    # Zamień // na przecinek (separator lokalizacji z PDF)
    text = re.sub(r'\s*//\s*', ', ', text)
    # Usuń pierwsze 3-5 linii jeśli to nagłówek strony (email, URL, miasto)
    lines = text.split('\n')
    skip = 0
    for line in lines[:6]:
        stripped = line.strip()
        if re.match(r'^[\w.+-]+@[\w.-]+\.\w+$', stripped):  # email
            skip += 1
        elif re.match(r'^https?://', stripped):               # URL
            skip += 1
        elif re.match(r'^[\w.-]+\.(net|com|pl|io|dev)$', stripped):  # domena
            skip += 1
        elif re.match(r'^[A-Za-z\s,]+,\s+[A-Za-z\s]+$', stripped) and len(stripped) < 40:  # "Vancouver, Canada"
            skip += 1
        else:
            break
    text = '\n'.join(lines[skip:])
    # Maksymalnie dwie newliny z rzędu
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Wielokrotne spacje
    text = re.sub(r'[ \t]{2,}', ' ', text)

    return text.strip()

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
        md_text = clean_cv_markdown(md_text) # type: ignore

        with fitz.open(path_file) as doc:
            page_count = len(doc)

        if is_scanned_pdf(md_text, page_count):
            logger.info("Scanned PDF detected — processing with GLM OCR")
            model_name = "glm-ocr + qwen3.6:35b-a3b"
            raw_text = ""
            with fitz.open(path_file) as doc:
                for i, page in enumerate(doc): #type: ignore
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
        logger.info(raw_text)
        logger.info("Extracting CV structure")
        cv_data = extract_cv_structure(raw_text)
        logger.info("CV structure extracted successfully")

    finally:
        os.unlink(path_file)

    return {"model": model_name, "cv": cv_data}