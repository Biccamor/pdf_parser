from fastapi import FastAPI, UploadFile, File, Request
import tempfile
import shutil
from parser import parse_pdf
from check_types import check_type
import pymupdf4llm
from fastapi.middleware.cors import CORSMiddleware
from criterias import delete_others_unicode, images, years
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
import asyncio
from contextlib import asynccontextmanager
import os
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ładuje model raz przy starcie
    app.state.converter = await asyncio.to_thread(
        lambda: PdfConverter(artifact_dict=create_model_dict())
    )
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #TODO: zmienic przed deployem ale do testow zostawic
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parser")
async def main(cv: UploadFile = File(...)):
    converter = app.state.converter
    use_marker = False
    bytes = await cv.read(2048)
    await cv.seek(0)
    typ = check_type(bytes)

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

            if len(clean_text) < 20:
                use_marker = True 
            if images(clean_text)==True:
                use_marker = True
            if years(clean_text)==True:
                use_marker=True

            if use_marker:
                model_name = "marker"
                clean_text = await  asyncio.to_thread(parse_pdf, path_file, converter)

            delete_others_unicode(clean_text)
        finally:
            os.unlink(path_file)

        return {"model": model_name, "text": f"{clean_text}"}