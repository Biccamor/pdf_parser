# PDF Parser — CV Extractor

Mikroserwis FastAPI do ekstrakcji strukturyzowanych danych z plików CV. Używa **Qwen2.5-VL 7B** (multimodal vision-language model) do konwersji PDF → zdjęcia → JSON z cv_schema.

---

## 📐 Architektura

```
PDF
  │
  ├─ Konwersja na zdjęcia (300 DPI)
  │
  ├─ Qwen2.5-VL (per stronę)
  │   ├─ Vision analysis
  │   └─ Extrakacja struktury CV → JSON
  │
  └─ Scalenie danych (merge_cv_data)
      └─ Usunięcie duplikatów
      └─ Ustrukturyzowany JSON (CVData)
```

---

## 🛠 Wymagania

- Python 3.11+
- [Ollama](https://ollama.ai/) z zainstalowanym **qwen2.5-vl-7b**
- Paczki z `requirements.txt`

### Setup Ollama (lokalnie)

```bash
# Zainstaluj Ollama
ollama pull qwen2.5-vl-7b

# Uruchom serwer (default: http://localhost:11434)
ollama serve
```

---

## 🚀 Uruchomienie

### Lokalnie (bez Docker)

```bash
# Zainstaluj zależności
pip install -r requirements.txt

# Uruchom FastAPI
uvicorn main:app --reload
```

Serwis będzie dostępny pod: **http://localhost:8000**

### Docker (jeśli potrzebujesz)

```bash
# Build i uruchomienie
docker compose up -d --build
```

---

## 📡 API

### `POST /parser`

Przyjmuje plik CV (PDF) i zwraca strukturyzowane dane.

**Obsługiwane formaty:** `.pdf`

**Przykład (cURL):**
```bash
curl -X POST http://localhost:8000/parser \
  -F "cv=@/path/to/cv.pdf"
```

**Odpowiedź (200 OK):**
```json
{
  "model": "qwen2.5-vl-7b",
  "cv": {
    "experience": [
      {
        "title": "Software Engineer",
        "company": "Tech Corp",
        "description": ["Developed REST APIs", "Managed databases"],
        "technologies": ["Python", "FastAPI", "PostgreSQL"]
      }
    ],
    "education": [
      {
        "degree": "BSc",
        "field": "Computer Science",
        "institution": "University",
        "notes": null
      }
    ],
    "skills": {
      "programming_languages": ["Python", "SQL"],
      "frameworks_and_libraries": ["FastAPI"],
      "tools_and_platforms": ["Docker", "PostgreSQL"],
      "other": ["Agile"]
    },
    "extras": []
  }
}
```

---

## 📁 Struktura projektu

```
pdf_parser/
├── main.py              # Endpoint FastAPI + PDF → Qwen pipeline
├── vision_extractor.py  # Qwen2.5-VL integration + merge_cv_data()
├── cv_schema.py         # Pydantic schema (CVData)
├── cv_extractor.py      # (stary, nie używany) Text → JSON
├── prompt.py            # Prompty dla Qwen + CV parser
├── criterias.py         # Unicode cleaning
├── requirements.txt     # Zależności
└── tests/               # Testy
```

---

## 🔧 Konfiguracja

### Zmienne środowiskowe

Brak wymaganych zmiennych. Opcjonalnie:

- `OLLAMA_HOST`: URL serwera Ollama (domyślnie: `http://localhost:11434`)
- `QWEN_MODEL`: Nazwa modelu (domyślnie: `qwen2.5-vl-7b`)

### CORS (przed deployem prod)

Edytuj `main.py` - linia `allow_origins=["*"]`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Zmień tutaj
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📝 cv_schema

Dostępne pola w odpowiedzi:

```python
class CVData:
    experience: List[ExperienceEntry]
    education: List[EducationEntry]
    skills: Skills
    extras: List[ExtraCategory]
```

Szczegóły w `cv_schema.py`.