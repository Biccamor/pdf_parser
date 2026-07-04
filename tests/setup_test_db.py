"""
Skrypt testowy — tworzy fałszywą bazę SQLite bit_servera
z jednym rekordem CV, żebyś mógł przetestować GET /fetch-and-parse.

Użycie:
    1. python setup_test_db.py
    2. uvicorn app.main:app --port 8010
    3. curl http://localhost:8010/fetch-and-parse
"""

import os
import sys
from sqlmodel import SQLModel, Field, Relationship, Session, create_engine, select
from typing import Optional, List

# ── Te same modele co bit_server ──

class Statuses(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str
    cvs: List["DatabaseCV"] = Relationship(back_populates="statuses")


class DatabaseCV(SQLModel, table=True):
    __tablename__ = "databasecv"
    id: Optional[int] = Field(default=None, primary_key=True)
    cv_name: str
    cv: str
    position_name: Optional[str] = None
    email: str
    github_link: Optional[str] = None
    status: Optional[int] = Field(default=None, foreign_key="statuses.id")
    statuses: Optional[Statuses] = Relationship(back_populates="cvs")


DB_NAME = os.getenv("BIT_SERVER_DATABASE", "bit_server.db")
PDF_PATH = os.path.join("tests", "1.pdf")  # użyj istniejącego testowego PDF


def main():
    # Sprawdź czy testowy PDF istnieje
    if not os.path.exists(PDF_PATH):
        print(f"BŁĄD: Nie znaleziono testowego PDF: {PDF_PATH}")
        sys.exit(1)

    # Utwórz lub podłącz bazę
    engine = create_engine(f"sqlite:///{DB_NAME}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Wyczyszczenie starych danych bez usuwania pliku
        from sqlmodel import delete
        session.exec(delete(DatabaseCV))
        session.exec(delete(Statuses))
        session.commit()

        # Dodaj statusy (tak jak bit_server)
        s1 = Statuses(status="waiting")
        s2 = Statuses(status="pending")
        s3 = Statuses(status="finished")
        session.add_all([s1, s2, s3])
        session.commit()

        # Pobierz ID statusu "waiting"
        waiting = session.exec(select(Statuses).where(Statuses.status == "waiting")).first()

        # Dodaj testowe CV
        test_cv = DatabaseCV(
            cv_name="test_cv.pdf",
            cv=os.path.abspath(PDF_PATH),  # pełna ścieżka do PDF
            position_name="Backend Developer",
            email="test@example.com",
            github_link="https://github.com/test",
            status=waiting.id,
        )
        session.add(test_cv)
        session.commit()

    print(f"Baza testowa utworzona: {DB_NAME}")
    print(f"  - CV: {os.path.abspath(PDF_PATH)}")
    print(f"  - Email: test@example.com")
    print(f"  - Stanowisko: Backend Developer")
    print()
    print("Teraz odpal serwer i przetestuj:")
    print("  uvicorn app.main:app --port 8010")
    print("  curl http://localhost:8010/fetch-and-parse")


if __name__ == "__main__":
    main()
