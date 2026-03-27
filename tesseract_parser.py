import fitz
import pytesseract
from PIL import Image

# WSKAZUJEMY ŚCIEŻKĘ DO ZAINSTALOWANEGO TESSERACTA
# Upewnij się, że ścieżka poniżej zgadza się z tym, gdzie go zainstalowałeś
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
def get_text_tesseract(path: str):
    with fitz.open(path) as doc:
        text = ""
        for page in doc:

            pix = page.get_pixmap(dpi=300, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples) #type: ignore
            text += pytesseract.image_to_string(img, lang="eng+pol")
            text += "\n\n"
        
    return text.strip()