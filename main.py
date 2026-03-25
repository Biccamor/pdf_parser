from fastapi import FastAPI, UploadFile, File
import tempfile
import shutil
from parser import parse_pdf
from check_types import check_type
import pymupdf4llm
from fastapi.middleware.cors import CORSMiddleware
from criterias import delete_others_unicode, images, years
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], #TODO: zmienic przed deployem ale do testow zostawic
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

converter = PdfConverter(
    artifact_dict=create_model_dict(),  
)

@app.post("/parser")
async def main(cv: UploadFile = File(...)):

    use_marker = False
    bytes = await cv.read(2048)
    await cv.seek(0)
    typ = check_type(bytes)

    if typ == ".txt": 
        read = await cv.read()
        return {"text": f"{read.decode('utf-8')}"}
    model_name = "pymupdf4llm"
    with tempfile.NamedTemporaryFile(suffix=typ, delete=True) as file:
        
        shutil.copyfileobj(cv.file, file)
        file.flush()
        path_file = file.name

        clean_text = pymupdf4llm.to_markdown(path_file)

        if len(clean_text) < 20:
            use_marker = True 
        if images(clean_text)==True:
            use_marker = True
        if years(clean_text)==True:
            use_marker=True

        if use_marker:
            model_name = "marker"
            clean_text = parse_pdf(path_file, converter=converter)

        delete_others_unicode(clean_text)

        return {"model": model_name, "text": f"{clean_text}"}