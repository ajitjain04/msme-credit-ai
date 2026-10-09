"""
Step 10 — ORM models: Company (static profile) and Assessment (one scoring
event, repeatable over time). See backend/database.py for the engine/
session setup these models plug into.

ONE-TO-MANY RELATIONSHIP, IN PLAIN TERMS
----------------------------------------------------------------------------
One Company row can have MANY Assessment rows, but each Assessment row
belongs to exactly one Company. Think of Company as a business's folder in
a filing cabinet (its name, age, sector, state -- things that don't change
day to day), and each Assessment as one dated report slipped into that
folder (today's bank numbers, GST numbers, the score and risk band they
produced). A business can be re-assessed next month with fresh data -- that
just adds ANOTHER report to the same folder, it never erases the old one.
That is exactly why `GET /api/v1/company/{company_id}` (Step 11) can serve
a full assessment HISTORY for one company, not just its latest score: it's
reading every report out of that one folder.

Mechanically, this is wired up with a foreign key: every Assessment row
stores the `company_id` of the Company folder it belongs to
(`Assessment.company_id`, pointing at `Company.company_id`). SQLAlchemy's
`relationship()` calls below just make that link easy to walk in Python
(`some_company.assessments` gives the list of its Assessment rows, and
`some_assessment.company` gives its one parent Company) instead of writing
the join by hand every time.
"""

from __future__ import annotations

import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Company(Base):
    """A business's static profile: who they are, not their current
    financial behaviour (that lives on Assessment instead, since bank/GST/
    digital data changes over time and a company can be re-scored later)."""

    __tablename__ = "companies"

    # Matches the synthetic dataset's ID format, e.g. "MSME000001" (see
    # docs/data_dictionary.md section 1).
    company_id: Mapped[str] = mapped_column(String, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)

    # Firmographics -- docs/data_dictionary.md section 1. Treated as this
    # company's static profile: the things an assessment doesn't re-measure
    # each time.
    age_of_business_years: Mapped[float] = mapped_column(Float, nullable=False)
    business_category: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    employee_count: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # One Company -> many Assessments (its scoring history over time).
    # cascade="all, delete-orphan": deleting a Company also deletes its
    # Assessment rows, rather than leaving orphaned rows with a dangling
    # company_id behind.
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment", back_populates="company", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience only
        return f"<Company {self.company_id} ({self.company_name})>"


class Assessment(Base):
    """ONE scoring event for ONE company: a snapshot of that company's
    banking/GST/digital data at the moment it was scored, plus the result
    (probability, score, risk band) and the SHAP drivers behind it.

    A company re-assessed later gets a NEW row here, never an overwrite of
    an old one -- that is what preserves its full history (see this
    module's docstring above)."""

    __tablename__ = "assessments"

    assessment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(
        String, ForeignKey("companies.company_id"), nullable=False, index=True
    )
    assessed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # --- Feature snapshot: banking / GST / digital data AT THE TIME of
    # this assessment (docs/data_dictionary.md sections 2-4, plus the 3
    # derived ratios added by model/preprocessing.py). Firmographics
    # (age/category/state/employee_count) live on Company instead -- see
    # that class's docstring.
    avg_monthly_inflow: Mapped[float] = mapped_column(Float, nullable=False)
    avg_monthly_outflow: Mapped[float] = mapped_column(Float, nullable=False)
    min_ending_balance_avg: Mapped[float] = mapped_column(Float, nullable=False)
    bounce_count_last_6m: Mapped[int] = mapped_column(Integer, nullable=False)
    account_vintage_months: Mapped[int] = mapped_column(Integer, nullable=False)
    cash_flow_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    has_gst_registration: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable: NaN for unregistered firms, same intentional-missingness
    # convention as the source data (docs/data_dictionary.md section 3) --
    # NOT 0.
    gst_filing_regularity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    annual_turnover_gst: Mapped[float | None] = mapped_column(Float, nullable=True)
    gst_filing_delay_days_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    upi_transaction_volume_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    pos_terminal_active_status: Mapped[int] = mapped_column(Integer, nullable=False)
    digital_payment_adoption_score: Mapped[float] = mapped_column(Float, nullable=False)
    net_cash_margin: Mapped[float] = mapped_column(Float, nullable=False)
    cash_buffer_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    gst_to_bank_turnover_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Result of this assessment (Step 8's score_company() +
    # Step 9's explain_company()) ---
    default_probability: Mapped[float] = mapped_column(Float, nullable=False)
    credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_band: Mapped[str] = mapped_column(String, nullable=False)

    # Top 5 positive + top 5 negative SHAP contributors (Step 9's
    # explain_company() output: {"feature", "value", "shap_value"} per
    # entry), stored as JSON. SQLite's JSON type stores this as text under
    # the hood; SQLAlchemy handles (de)serializing it to/from a plain dict
    # automatically, so no separate table is needed just to hold this.
    shap_top_drivers: Mapped[dict] = mapped_column(JSON, nullable=False)

    company: Mapped["Company"] = relationship("Company", back_populates="assessments")

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience only
        return (
            f"<Assessment {self.assessment_id} for {self.company_id}: "
            f"score={self.credit_score} ({self.risk_band})>"
        )
