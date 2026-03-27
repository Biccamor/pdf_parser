from fastapi import FastAPI, UploadFile, File, Request
import tempfile
import pymupdf.layout
from check_types import check_type
import pymupdf4llm
from tesseract_parser import get_text_tesseract
from fastapi.middleware.cors import CORSMiddleware
from criterias import delete_others_unicode, images, years
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
import asyncio
import os


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #TODO: zmienic przed deployem ale do testow zostawic
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parser")
async def main(cv: UploadFile = File(...)):

    bytes = await cv.read(2048)
    await cv.seek(0)
    typ = check_type(bytes)
    brutal = False
    if typ == ".txt": 
        read = await cv.read()
        return {"text": f"{read.decode('utf-8')}"}
    model_name = "pymupdf4llm"
    with tempfile.NamedTemporaryFile(suffix=typ, delete=True) as file:
        
        content = await cv.read()
        file.write(content)
        file.flush()
        path_file = file.name

        try: 
            clean_text = pymupdf4llm.to_markdown(path_file)
            delete_others_unicode(clean_text)
            
            if len(clean_text) < 20: 
                clean_text = get_text_tesseract(path_file)


        finally:
            os.unlink(path_file)

        return {"model": model_name, "text": f"{clean_text}"}