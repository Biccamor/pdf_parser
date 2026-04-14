# PDF Parser — CV Extractor

Mikroserwis FastAPI do ekstrakcji tekstu z plików CV. Obsługuje PDF, TXT, JPG i PNG. Automatycznie wykrywa zeskanowane (image-based) PDF-y i przełącza się na OCR przez Tesseract.

---

## 📐 Architektura

```
Plik wejściowy
    │
    ├─ TXT ──────────────────────── zwróć jako tekst
    ├─ JPG / PNG ────────────────── Tesseract OCR
    └─ PDF ──── pymupdf4llm ──► sprawdź jakość tekstu
                                    │
                                    ├─ OK ──────────── zwróć markdown
                                    └─ SKAN ─────────── Tesseract OCR
```

Heurystyki wykrywania skanu (`is_scanned_pdf`):
- < 100 znaków na stronę
- zbyt wysoki stosunek tagów obrazkowych do słów
- 3+ kolejne lata z rzędu (artefakt złego parsowania tabel)
- < 50% znaków alfabetycznych (śmieci / artefakty OCR)

---

## 🛠 Wymagania

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

Do działania lokalnego (poza Dockerem) dodatkowo:
- Python 3.11+
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) zainstalowany w systemie
  - Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`
  - Linux/macOS: `apt install tesseract-ocr` / `brew install tesseract`
- Paczki językowe Tesseract: `eng`, `pol`

---

## 🚀 Uruchomienie przez Docker (zalecane)

```bash
git clone <link-do-repo>
cd <nazwa-folderu>
docker compose up -d --build
```

Serwis będzie dostępny pod: **http://localhost:8000**

Zatrzymanie:
```bash
docker compose down
```

Logi (przydatne przy debugowaniu):
```bash
docker compose logs -f
```

---

## 📡 API

### `POST /parser`

Przyjmuje jeden plik CV i zwraca jego zawartość jako tekst/markdown.

**Obsługiwane formaty:** `.pdf`, `.txt`, `.jpg`, `.png`

**Przykład (cURL):**
```bash
curl -X POST http://localhost:8000/parser \
  -F "cv=@/sciezka/do/cv_jan_kowalski.pdf"
```

**Odpowiedź (200 OK):**
```json
{
  "model": "pymupdf4llm",
  "text": "# Jan Kowalski\n\n..."
}
```

Pole `model` przyjmuje wartości: `pymupdf4llm` (standardowy parser) lub `tesseract` (OCR fallback).

**Błąd — nieobsługiwany format (415):**
```json
{
  "detail": "application/msword is not allowed, allowed types: PDF, TXT, JPG, PNG, DOCX"
}
```

---

## 📁 Struktura projektu

```
pdf_parser/
├── main.py              # Endpoint FastAPI + logika routingu
├── criterias.py         # Heurystyki detekcji skanów + czyszczenie tekstu
├── check_types.py       # Walidacja MIME type pliku wejściowego
├── tesseract_parser.py  # OCR przez Tesseract (PDF i obrazki)
├── ollama_ocr.py        # (Eksperymentalny) OCR przez lokalny model Ollama
├── requirements.txt     # Zależności Pythona
├── Dockerfile
└── docker-compose.yaml
```

---

## ⚙️ Zmienne środowiskowe

Projekt nie wymaga konfiguracji do basic usage. Jeśli chcesz zmienić port lub ustawienia CORS przed deployem produkcyjnym, edytuj `docker-compose.yaml` oraz `main.py` (sekcja `CORSMiddleware`).