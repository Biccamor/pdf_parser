import fitz
import pytesseract
from PIL import Image
import os

if os.name == 'nt':  # tylko Windows
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def get_text_tesseract(path: str) -> str:
    """Obsługuje zarówno PDF jak i obrazki (jpg/png) przez Tesseract OCR."""
    ext = os.path.splitext(path)[1].lower()

    # Obrazek — otwieramy bezpośrednio przez PIL
    if ext in (".jpg", ".jpeg", ".png"):
        img = Image.open(path)
        return pytesseract.image_to_string(img, lang="eng+pol").strip()

    # PDF — konwertujemy każdą stronę na pikselmapę
    with fitz.open(path) as doc:
        text = ""
        for page in doc:
            pix = page.get_pixmap(dpi=300, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)  # type: ignore
            text += pytesseract.image_to_string(img, lang="eng+pol")
            text += "\n\n"

    return text.strip()