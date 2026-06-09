import os

OLLAMA_BASE_URL  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL     = "qwen3:30b-a3b"
OCR_LANGUAGES    = ["en", "pl"]
MIN_TEXT_LENGTH  = 80  # poniżej tej liczby znaków → traktuj stronę jako skan
PDF_DATABASE_DIR = os.getenv("PDF_DATABASE_DIR", "./bazy")
