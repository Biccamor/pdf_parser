# Parser for CV

App takes one CV file at the time (txt, png, jpg, pdf) and outputs it as a markdown or txt file, optimized for LLM processing.
The parser works on endpoint `/parser` (POST).

## 🛠 Wymagania
* [Docker](https://docs.docker.com/get-docker/)
* [Docker Compose](https://docs.docker.com/compose/install/)

## 🏃‍♂️ Jak uruchomić projekt lokalnie?

1. **Sklonuj repozytorium:**
   ```bash
   git clone <link-do-repo>
   cd <nazwa-folderu>
Skonfiguruj środowisko (opcjonalnie):
Jeśli projekt wymaga zmiennych środowiskowych (np. kluczy API do OCR), skopiuj plik z przykładową konfiguracją:

Bash
cp .env.example .env
Uruchom kontenery:

Bash
docker compose up -d --build
 Porty i Dostęp
Gdy kontenery wstaną, serwis jest dostępny pod adresem:

API url: http://localhost:8000 (Zmień port na właściwy, jeśli aplikacja używa innego)

Jak używać API?
Endpoint: POST /parser
Wysyła plik z CV i zwraca jego zawartość przetworzoną na tekst/markdown. Obsługiwane formaty: .txt, .png, .jpg, .pdf.

Przykład użycia (cURL):

```
curl -X POST http://localhost:8000/parser \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/sciezka/do/twojego/pliku/cv_jan_kowalski.pdf"
```

Przydatne komendy

Zatrzymanie aplikacji:

```
docker compose down
```

Podejrzenie logów parsera (przydatne przy debugowaniu wrzucanych plików):

```
docker compose logs -f
```