import sys
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import PDF_DATABASE_DIR
from app.services.cv_parser import parse_cv
from app.schemas.cv_schema import CVData, ParseRequest, ParseResponse

# ── Logging ──

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# ── App ──

app = FastAPI(
    title="CV Parser API",
    description="Parsowanie CV z PDF → JSON przez LLM",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=600,
)


# ── Endpoints ──


@app.post("/parse", response_model=ParseResponse)
async def parse_cv_endpoint(req: ParseRequest):
    """
    Parsuj CV z pliku PDF w folderze /bazy.

    Przyjmuje nazwę pliku + metadane rekrutacyjne (email, stanowisko, github).
    Zwraca sparsowane dane CV wraz z metadanymi.
    """
    pdf_dir = Path(PDF_DATABASE_DIR)
    pdf_path = pdf_dir / req.filename

    # Walidacja: czy folder istnieje
    if not pdf_dir.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Folder bazy danych '{PDF_DATABASE_DIR}' nie istnieje.",
        )

    # Walidacja: czy plik istnieje
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Plik '{req.filename}' nie istnieje w folderze bazy danych.",
        )

    # Walidacja: czy to PDF
    if pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail=f"Plik '{req.filename}' nie jest plikiem PDF.",
        )

    # Parsowanie CV
    logger.info("Parsowanie CV: %s", req.filename)
    try:
        cv_data = parse_cv(str(pdf_path))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Błąd parsowania CV: %s", req.filename)
        raise HTTPException(status_code=500, detail=f"Błąd parsowania: {e}")

    # Walidacja przez Pydantic
    cv = CVData(**cv_data)

    return ParseResponse(
        filename=req.filename,
        email=req.email,
        position=req.position,
        github_url=req.github_url,
        cv=cv,
    )
