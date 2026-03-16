import pymupdf
from gliner2 import GLiNER2

# TODO: ulepszyc to jak wyjmujemy inforamcje zeby latwiej (i z wieksza skutecznoscia) gliner2 je dopasowywal
# TODO: extract danych osobwych na start
# TODO: testy  duzo testow
# TODO: 

extractor = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")

def extract_text_pymupdf(pdf_path):
    doc = pymupdf.open(pdf_path)
    try:
        text = ""
        for page in doc:
            page_text = page.get_text("text")
            if not isinstance(page_text, str):
                page_text = str(page_text)
            text += page_text  # plain text
        return text
    finally:
        doc.close()


# Extract text from a PDF.
text = extract_text_pymupdf("pdfs/pdf2.pdf")
result = extractor.extract_entities(text, ["Umiejętności", "Zainteresowania", "Języki", "Wykształcenie", "Dane osobowe"])
print(result)