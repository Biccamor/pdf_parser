"""
Odczyt CV z bazy SQLite bit_servera.

Bit_server zapisuje CV (ścieżka PDF + email + stanowisko + github) do SQLite.
Ten moduł czyta z tej samej bazy — bez modyfikowania schematu.
"""

from sqlmodel import Session, create_engine, select, update, SQLModel, Field, Relationship
from typing import Optional, List

from app.config import BIT_SERVER_DATABASE


# ── Modele SQLModel (lustro tego co ma bit_server) ──


class Statuses(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str
    cvs: List["DatabaseCV"] = Relationship(back_populates="statuses")


class DatabaseCV(SQLModel, table=True):
    __tablename__ = "databasecv"

    id: Optional[int] = Field(default=None, primary_key=True)
    cv_name: str
    cv: str           # ścieżka do pliku PDF
    position_name: Optional[str] = None
    email: str
    github_link: Optional[str] = None
    status: Optional[int] = Field(default=None, foreign_key="statuses.id")

    statuses: Optional[Statuses] = Relationship(back_populates="cvs")


# ── Engine ──

engine = create_engine(f"sqlite:///{BIT_SERVER_DATABASE}")


# ── Funkcje ──


def get_next_waiting_cv() -> dict | None:
    """Pobierz najstarszy rekord ze statusem 'waiting'. Zwraca dict lub None."""
    with Session(engine) as session:
        waiting_status = session.exec(
            select(Statuses).where(Statuses.status == "waiting")
        ).first()

        if not waiting_status:
            return None

        cv = session.exec(
            select(DatabaseCV)
            .where(DatabaseCV.status == waiting_status.id)
            .order_by(DatabaseCV.id)
        ).first()

        if not cv:
            return None

        return cv.model_dump()


def mark_as_pending(cv_id: int) -> None:
    """Zmień status CV na 'pending'."""
    with Session(engine) as session:
        pending_status = session.exec(
            select(Statuses).where(Statuses.status == "pending")
        ).first()

        if not pending_status:
            return

        session.exec(
            update(DatabaseCV)
            .where(DatabaseCV.id == cv_id)
            .values(status=pending_status.id)
        )
        session.commit()
