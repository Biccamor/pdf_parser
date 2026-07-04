# CV Parser API

Mikroserwis do parsowania CV z plików PDF na ustrukturyzowany JSON.
Wyciąga tekst z PDF (text-layer lub OCR skanów) i przepuszcza przez LLM (Ollama).

## Struktura projektu

```
app/
├── main.py                  # Endpointy FastAPI
├── config.py                # Konfiguracja (zmienne środowiskowe, model LLM) < UWAGA OBECNIE USTAWIONY FOLDER Z PDFAMI NA TESTS W PRZYSZLOSCI ZMIENIC NA FOLDER BAZY
├── prompts/
│   └── prompt.py            # System + user prompt dla LLM
├── schemas/
│   └── cv_schema.py         # Modele Pydantic (request / response / CV)
└── services/
    ├── cv_parser.py         # Pipeline: PDF → tekst → LLM → JSON + postprocessing
    ├── cv_fetcher.py        # Odczyt / update CV z bazy SQLite bit_servera
    ├── extraction.py        # Ekstrakcja tekstu (PyMuPDF + OCR przez Ollama)
    └── pdf_conversion.py    # Konwersja base64 → PDF
```

## Uruchomienie

Dev (CPU): lepiej nie używać

```bash
docker compose -f docker-compose.dev.yaml up --build
```

Prod (GPU NVIDIA):

```bash
docker compose -f docker-compose.prod.yaml up --build
```

Pobranie modeli Ollama (jednorazowo, po pierwszym uruchomieniu):

```bash
docker exec -it ollama ollama pull qwen3:30b-a3b
docker exec -it ollama ollama pull glm-ocr:latest
```

Serwis będzie dostępny pod `http://localhost:8010`.
Dokumentacja API (Swagger): `http://localhost:8010/docs`.

## Zmienne środowiskowe

| Zmienna | Domyślna | Opis |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://localhost:11434` | Adres instancji Ollama |
| `PDF_DATABASE_DIR` | `./bazy` | Folder z plikami PDF dla endpointu `/parse` |
| `BIT_SERVER_DATABASE` | `bit_server.db` | Ścieżka do bazy SQLite bit_servera |

W kontenerach zmienne są ustawiane przez `docker-compose.*.yaml`.

## Endpointy

### POST /parse

Parsuje podany plik PDF z folderu `PDF_DATABASE_DIR`.

Request:

```json
{
  "filename": "cv_kowalski.pdf",
  "email": "jan@example.com",
  "position": "Backend Developer",
  "github_url": "https://github.com/jankowalski"
}
```

Response:

```json
{
  "filename": "cv_kowalski.pdf",
  "email": "jan@example.com",
  "position": "Backend Developer",
  "github_url": "https://github.com/jankowalski",
  "cv": {
    "experience": [],
    "education": [],
    "skills": {
      "programming_languages": [],
      "frameworks_and_libraries": [],
      "tools_and_platforms": [],
      "other": []
    },
    "languages": [],
    "extras": []
  }
}
```

Użycie na serwerze:

```bash
curl -X POST http://localhost:8010/parse \
  -H "Content-Type: application/json" \
  -d '{"filename": "10.pdf", "email": "test@example.com", "position": "Developer"}'
``` 

### GET /fetch-and-parse

Pobiera najstarsze CV ze statusem `waiting` z bazy bit_servera, parsuje je i zmienia status na `pending`.

Przebieg:

1. Odczytuje najstarszy rekord ze statusem `waiting` z tabeli `databasecv`.
2. Pobiera ścieżkę do PDF z kolumny `cv`.
3. Parsuje PDF przez LLM.
4. Ustawia status rekordu na `pending`.
5. Zwraca sparsowane CV z metadanymi (email, stanowisko, github).

Format odpowiedzi jest identyczny jak w `/parse`.

Użycie na serwerze:

```bash
curl -X GET http://localhost:8010/fetch-and-parse
```

## Integracja z bit_serverem

Parser korzysta z tej samej bazy SQLite co bit_server (read + update statusu).

### Tabela `statuses`

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `status` | TEXT | `waiting` / `pending` / `finished` |

### Tabela `databasecv`

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `id` | INTEGER | PK |
| `cv_name` | TEXT | Nazwa pliku PDF |
| `cv` | TEXT | Absolutna ścieżka do pliku PDF na dysku |
| `position_name` | TEXT | Stanowisko (opcjonalne) |
| `email` | TEXT | Email kandydata |
| `github_link` | TEXT | Link do GitHuba (opcjonalny) |
| `status` | INTEGER | FK → `statuses.id` |

Kolumna `cv` musi zawierać pełną ścieżkę do pliku — nie base64, nie URL.

## Schemat wyjściowego JSON

```json
{
  "experience": [
    {
      "title": "string",
      "company": "string",
      "start": "string | null",
      "end": "string | null",
      "location": "string | null",
      "description": ["string"],
      "technologies": ["string"]
    }
  ],
  "education": [
    {
      "degree": "string",
      "field": "string",
      "institution": "string",
      "start": "string | null",
      "end": "string | null",
      "notes": "string | null"
    }
  ],
  "skills": {
    "programming_languages": ["string"],
    "frameworks_and_libraries": ["string"],
    "tools_and_platforms": ["string"],
    "other": ["string"]
  },
  "languages": [
    {
      "name": "string",
      "level": "string | null"
    }
  ],
  "extras": [
    {
      "category": "string",
      "items": [
        {
          "title": "string",
          "date": "string | null",
          "description": "string | null",
          "details": ["string"]
        }
      ]
    }
  ]
}
```

## Porty

| Serwis | Port |
| --- | --- |
| PDF Parser | `8010` |
| Ollama | `11434` (dev) / `11435` (prod, host mapping) |
