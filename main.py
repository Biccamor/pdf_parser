from fastapi import FastAPI, UploadFile, File
import tempfile
import shutil
from parser import parser
from check_types import check_type
import pymupdf4llm

app = FastAPI()

@app.post("/parser")
async def main(cv: UploadFile = File(...)):

    bytes = await cv.read(2048)
    await cv.seek(0)
    typ = check_type(bytes)

    if typ == ".txt": 
        read = await cv.read()
        return read.decode("utf-8")

    with tempfile.NamedTemporaryFile(suffix=typ, delete=True) as file:
        
        shutil.copyfileobj(cv.file, file)
        file.flush()
        path_file = file.name

        clean_text = pymupdf4llm.to_markdown(path_file)

        if len(clean_text) < 20:
            
            clean_text = parser(path_file)

        return clean_text