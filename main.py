# -*- coding: utf-8 -*-
import re
import tempfile
import logging
import os
from contextlib import asynccontextmanager

import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from vision_extractor import extract_text_from_assembled
from docling_processor import initialize_docling_converter, process_pdf_with_docling
import sys

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager: initialize Docling at startup."""
    logger.info("Starting FastAPI app")
    try:
        initialize_docling_converter()
        logger.info("Docling initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Docling: {e}")
        raise
    
    yield
    
    logger.info("Shutting down FastAPI app")


app = FastAPI(lifespan=lifespan)

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
    """
    Parse CV using Docling layout detection + Qwen region-aware extraction.
    
    Flow:
    1. Validate PDF header
    2. Save to temp file
    3. Extract layout with Docling
    4. Crop regions and send to Qwen (region-appropriate prompts)
    5. Assemble region texts
    6. Send assembled text to Qwen for final structured extraction
    7. Return CVData JSON
    """
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
            
        logger.info(f"Processing PDF with {page_count} page(s) using Docling + Qwen2.5-VL")
        
        assembled_text = await process_pdf_with_docling(path_file, model="qwen2.5-vl-7b")
        
        if not assembled_text.strip():
            logger.warning("No text extracted from Docling regions")
            from cv_schema import CVData
            return {"model": "qwen2.5-vl-7b (docling)", "cv": CVData().model_dump()}
        
        logger.info(f"Extracted {len(assembled_text)} chars from regions")
        logger.info("Sending assembled text to Qwen for final parsing")
        
        cv_data = await extract_text_from_assembled(assembled_text, model="qwen2.5-vl-7b")
        logger.info("CV structure extracted successfully")

    finally:
        os.unlink(path_file)

    return {"model": "qwen2.5-vl-7b (docling)", "cv": cv_data}