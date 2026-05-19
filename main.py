# -*- coding: utf-8 -*-
import re
import tempfile
import logging
import os
import asyncio

import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from vision_extractor import extract_cv_with_vision, merge_cv_data
from criterias import delete_others_unicode
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


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

        with fitz.open(path_file) as doc:
            page_count = len(doc)
            
        logger.info(f"Processing PDF with {page_count} page(s) using Qwen2.5-VL")
        
        cv_pages = []
        with fitz.open(path_file) as doc:
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=300, alpha=False)
                page_jpg = f"{path_file}_page_{i}.jpg"
                pix.save(page_jpg)
                
                try:
                    logger.info(f"Processing page {i + 1}/{page_count}")
                    page_data = await extract_cv_with_vision(page_jpg)
                    cv_pages.append(page_data)
                    logger.info(f"Page {i + 1} processed successfully")
                except Exception as e:
                    logger.error(f"Error processing page {i + 1}: {e}")
                finally:
                    os.unlink(page_jpg)
        
        logger.info("Merging data from all pages")
        cv_data = await merge_cv_data(cv_pages)
        logger.info("CV structure extracted successfully")

    finally:
        os.unlink(path_file)

    return {"model": "qwen2.5-vl-7b", "cv": cv_data}