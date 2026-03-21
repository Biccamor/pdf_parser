import pymupdf
from gliner2 import GLiNER2

# TODO: ulepszyc to jak wyjmujemy inforamcje zeby latwiej (i z wieksza skutecznoscia) gliner2 je dopasowywal
# TODO: testy  duzo testow
# TODO!: co z OCR?

extractor = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")

def extract_text_pymupdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    try:
        text = ""
        for page in doc:
            page_text = page.get_text("text")
            if not isinstance(page_text, str):
                page_text = str(page_text)
            text += page_text 
        return text
    finally:
        doc.close()

def get_clean_text(pdf: str): 

    text = extract_text_pymupdf(f"pdfs/{pdf}.pdf")
    labels_en = ["Experience", "Skills", "Education", "Full Name", "Email", "date and location of birth",
                "phone number", "adress"]
    result = extractor.extract_entities(text, labels_en)
    return result

text = extract_text_pymupdf("pdfs/pdf2.pdf")
print(text)
print(get_clean_text("pdf2"))