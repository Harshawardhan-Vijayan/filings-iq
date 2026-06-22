from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.company import Company
    from backend.models.filing import Filing


class FinancialFact(Base):
    __tablename__ = "financial_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    filing_id: Mapped[int | None] = mapped_column(ForeignKey("filings.id"))

    metric_name: Mapped[str] = mapped_column(String(60), nullable=False)  # e.g. "revenue"
    xbrl_tag: Mapped[str] = mapped_column(
        String(120), nullable=False
    )  # e.g. "RevenueFromContract..."
    value: Mapped[float] = mapped_column(Numeric(24, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "USD"

    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column()
    fiscal_quarter: Mapped[int | None] = mapped_column()
    fiscal_period: Mapped[str | None] = mapped_column(String(10))  # "Q1", "Q2", "FY"
    form_type: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    company: Mapped["Company"] = relationship()  # type: ignore[name-defined]
    filing: Mapped["Filing | None"] = relationship()  # type: ignore[name-defined]

    __table_args__ = (
        Index("ix_ff_company_metric_period", "company_id", "metric_name", "period_end"),
    )
