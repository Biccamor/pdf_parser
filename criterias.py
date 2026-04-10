import re
import unicodedata

def delete_others_unicode(text: str) -> str:
    "".join(chr for chr in text if unicodedata.category(chr)[0] != "C" or chr in "\n\t") # check if character is weird char
    return text

def images(text: str):
    picture_tags = text.count("picture [") # check if there are too many images compared to text if so then it is badly foramted
    words = len(text.split())
    
    if words > 0 and (picture_tags / words) > 0.02: 
        return True
    return False

def years(text: str) -> bool:
    if re.search(r"\d{4}\s+\d{4}", text): # check if dates arent spammed if they are then it is badly formated
        return True
    return False


def is_scanned_pdf(text: str, page_count: int) -> bool:
    """
    Zwraca True jeśli PDF wygląda jak skan (mało tekstu lub głównie śmieci).
    Agreguje wszystkie heurystyki w jednym miejscu.
    """
    text_stripped = text.strip()

    # 1. Mało tekstu na stronę (< 100 znaków na stronę = podejrzane)
    if len(text_stripped) < page_count * 100:
        return True

    # 2. Za dużo tagów obrazkowych relative do słów
    if images(text_stripped):
        return True

    # 3. Zniekształcone daty (symptom złego parsowania tabel/layoutu)
    if years(text_stripped):
        return True

    # 4. Ratio liter do wszystkich znaków (< 50% = śmieci / artefakty OCR)
    alpha_ratio = sum(c.isalpha() for c in text_stripped) / max(len(text_stripped), 1)
    if alpha_ratio < 0.50:
        return True

    return False