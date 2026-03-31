import magic
from fastapi import HTTPException

DOZWOLONE_FORMATY = {
    'application/pdf': '.pdf',
    'text/plain': '.txt',
    'image/jpeg': '.jpg',
    'image/png': '.png',
 #   'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
}

def check_type(bytes):
    
    typ = magic.from_buffer(bytes, mime=True)
    print(typ)
    if typ not in DOZWOLONE_FORMATY:

        raise HTTPException(415, detail=f"{typ} is not allowed, allowed types: PDF, TXT, JPG, PNG, DOCX")

    return DOZWOLONE_FORMATY[typ]    

if __name__ == "__main__":

    with open(file="pdfs/cv_lukasz.pdf", mode ="rb") as cv:
        bytes =  cv.read(2048)
        cv.seek(0)
        typ = check_type(bytes)
