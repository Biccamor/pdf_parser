from fastapi import FastAPI, UploadFile, File
import tempfile
import shutil
from marker_test import parser
from check_types import check_type

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

        clean_text = parser(path_file)

        return clean_text