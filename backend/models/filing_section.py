from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.filing import Filing


class FilingSection(Base):
    __tablename__ = "filing_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "risk_factors"
    section_title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g. "ITEM 1A. RISK FACTORS"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    filing: Mapped["Filing"] = relationship(back_populates="sections")  # type: ignore[name-defined]
