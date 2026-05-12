import unicodedata


def delete_others_unicode(text: str) -> str:
    """Usuwa niedrukowane znaki kontrolne (C*) z tekstu, zachowując newline i tab."""
    return "".join(c for c in text if unicodedata.category(c)[0] != "C" or c in "\n\t")


def has_too_many_images(text: str, threshold: float = 0.1, min_words: int = 10) -> bool:
    """Sprawdza czy tekst ma zbyt dużo tagów obrazkowych relative do słów.

    Symptom: pymupdf4llm generuje tagi 'picture [' dla osadzonych obrazów.
    Jeśli ich stosunek do słów jest wysoki, PDF składa się głównie z grafik
    a nie z warstwy tekstowej.

    Args:
        text: tekst wyekstrahowany przez pymupdf4llm.
        threshold: maksymalny dopuszczalny stosunek obrazków do słów.
        min_words: minimalna liczba słów — przy mniejszej ilości check jest
                   pomijany (unikamy fałszywych alarmów na krótkim tekście).
    """
    picture_tags = text.count("picture [")
    words = len(text.split())

    if words < min_words:
        return False

    return (picture_tags / words) > threshold


def is_scanned_pdf(text: str, page_count: int, chars_per_page: int = 100) -> bool:
    """Zwraca True jeśli PDF wygląda jak skan.

    Dwa check'i:
    1. Mało tekstu na stronę (< chars_per_page znaków) — główny sygnał.
    2. Za dużo tagów obrazkowych relative do słów — dodatkowe zabezpieczenie.
    """
    text_stripped = text.strip()

    if len(text_stripped) < page_count * chars_per_page:
        return True

    if has_too_many_images(text_stripped):
        return True

    return False