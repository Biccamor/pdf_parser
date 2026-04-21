import re
import unicodedata

def delete_others_unicode(text: str) -> str:
    """Usuwa niedrukowane znaki kontrolne (C*) z tekstu, zachowując newline i tab."""
    return "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t")

def images(text: str):
    picture_tags = text.count("picture [") # check if there are too many images compared to text if so then it is badly foramted
    words = len(text.split())
    
    if words > 0 and (picture_tags / words) > 0.02: 
        return True
    return False

def years(text: str) -> bool:
    """Wykrywa zduplikowane lata — symptom złego parsowania tabel/layoutu.
    Normalny zakres dat (np. '2020 2023') nie triggeruje — szukamy 3+ lat z rzędu.
    """
    if re.search(r"(\d{4}\s+){2,}\d{4}", text):
        return True
    return False


def is_scanned_pdf(text: str, page_count: int) -> bool:
    """
    Zwraca True jeśli PDF wygląda jak skan (mało tekstu lub głównie śmieci).
    Agreguje wszystkie heurystyki w jednym miejscu.
    """
    text_stripped = text.strip()

    #Mało tekstu na stronę
    if len(text_stripped) < page_count * 100:
        return True

    #Za dużo tagów obrazkowych relative do słów
    if images(text_stripped):
        return True

    #Zniekształcone daty
    if years(text_stripped):
        return True

    # Ratio liter do wszystkich znaków < 50%
    alpha_ratio = sum(c.isalpha() for c in text_stripped) / max(len(text_stripped), 1)
    if alpha_ratio < 0.50:
        return True

    return False