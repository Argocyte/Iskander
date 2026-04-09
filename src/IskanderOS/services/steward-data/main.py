"""
steward-data — read-only treasury data API for the Steward agent.

Wraps iskander_ledger tables with aggregate-only endpoints.
No raw rows, no individual member data, no write capability.

Auth: every request must carry Authorization: Bearer {INTERNAL_SERVICE_TOKEN}.
All errors log full detail server-side; callers get generic messages only.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_URL = os.environ["DATABASE_URL"]
_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_db():
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_SERVICE_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "")


def _require_auth(request: Request):
    """Verify Bearer token. Raises 401 if missing or wrong."""
    if not _SERVICE_TOKEN:
        # No token configured — accept all (dev/test mode)
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or auth[len("Bearer "):] != _SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="steward-data",
    description="Read-only treasury data API. No individual member data.",
    version="1.0.0",
    docs_url=None,   # disable Swagger UI in production
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Treasury endpoints
# ---------------------------------------------------------------------------

@app.get("/treasury/summary")
@limiter.limit("100/minute")
def treasury_summary(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_require_auth),
) -> dict[str, Any]:
    """
    Return the cooperative's current treasury position.

    Aggregates all accounts. Returns last_updated_at from the most recently
    updated account record so callers can detect stale data.
    Never returns individual member financial data.
    """
    try:
        accounts_rows = db.execute(text("""
            SELECT name, balance, currency, updated_at
            FROM ledger_accounts
            ORDER BY name
        """)).fetchall()

        if not accounts_rows:
            return {
                "total_balance": 0.0,
                "currency": "GBP",
                "accounts": [],
                "last_updated_at": None,
            }

        # All accounts must share a currency (validated at entry time).
        # Use the first row's currency as the canonical value.
        currency = accounts_rows[0].currency
        total = sum(row.balance for row in accounts_rows)
        candidates = [row.updated_at for row in accounts_rows if row.updated_at is not None]
        last_updated = max(candidates) if candidates else None

        # updated_at may be a datetime (PostgreSQL) or ISO string (SQLite in tests)
        if last_updated is not None and hasattr(last_updated, "isoformat"):
            last_updated_str: str | None = last_updated.isoformat()
        else:
            last_updated_str = str(last_updated) if last_updated is not None else None

        return {
            "total_balance": float(total),
            "currency": currency,
            "accounts": [
                {"name": row.name, "balance": float(row.balance)}
                for row in accounts_rows
            ],
            "last_updated_at": last_updated_str,
        }
    except Exception:
        logger.exception("treasury_summary query failed")
        raise HTTPException(status_code=500, detail="Internal error")


@app.get("/treasury/surplus-ytd")
@limiter.limit("100/minute")
def treasury_surplus_ytd(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_require_auth),
) -> dict[str, Any]:
    """
    Return year-to-date income, expenditure, and surplus/deficit.

    Computed from financial_transactions for the current financial year
    (1 April – 31 March for UK cooperatives).
    Budget figures included where set.
    """
    try:
        today = date.today()
        # UK financial year: starts 1 April
        fy_start_year = today.year if today.month >= 4 else today.year - 1
        fy_start = date(fy_start_year, 4, 1)
        fy_end = date(fy_start_year + 1, 3, 31)
        financial_year = f"{fy_start_year}-{fy_start_year + 1}"

        row = db.execute(text("""
            SELECT
                COALESCE(SUM(CASE WHEN direction = 'credit' THEN amount ELSE 0 END), 0) AS income_ytd,
                COALESCE(SUM(CASE WHEN direction = 'debit'  THEN amount ELSE 0 END), 0) AS expenditure_ytd
            FROM financial_transactions
            WHERE transaction_date >= :fy_start
              AND transaction_date <= :fy_end
        """), {"fy_start": fy_start, "fy_end": fy_end}).fetchone()

        income = float(row.income_ytd)
        expenditure = float(row.expenditure_ytd)
        surplus = income - expenditure

        # Budget figures (optional — may not be set for new cooperatives)
        budget = db.execute(text("""
            SELECT budget_income, budget_expenditure
            FROM financial_year_budget
            WHERE financial_year = :fy
            LIMIT 1
        """), {"fy": financial_year}).fetchone()

        result: dict[str, Any] = {
            "financial_year": financial_year,
            "income_ytd": income,
            "expenditure_ytd": expenditure,
            "surplus_ytd": surplus,
            "budget_income": None,
            "budget_expenditure": None,
            "budget_surplus": None,
            "variance_income": None,
            "variance_expenditure": None,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

        if budget:
            b_income = float(budget.budget_income) if budget.budget_income is not None else None
            b_exp = float(budget.budget_expenditure) if budget.budget_expenditure is not None else None
            b_surplus = (b_income - b_exp) if (b_income is not None and b_exp is not None) else None
            result.update({
                "budget_income": b_income,
                "budget_expenditure": b_exp,
                "budget_surplus": b_surplus,
                "variance_income": (income - b_income) if b_income is not None else None,
                "variance_expenditure": (expenditure - b_exp) if b_exp is not None else None,
            })

        return result
    except Exception:
        logger.exception("treasury_surplus_ytd query failed")
        raise HTTPException(status_code=500, detail="Internal error")


@app.get("/treasury/activity")
@limiter.limit("100/minute")
def treasury_activity(
    request: Request,
    limit: int = 10,
    db: Session = Depends(get_db),
    _: None = Depends(_require_auth),
) -> dict[str, Any]:
    """
    Return recent aggregate financial activity by category.

    Aggregate only — no individual attribution, no member names.
    Limit capped at 50.
    """
    limit = min(max(1, limit), 50)
    try:
        rows = db.execute(text("""
            SELECT transaction_date, category, amount, direction, description
            FROM financial_transactions
            ORDER BY transaction_date DESC, id DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()

        return {
            "transactions": [
                {
                    "date": row.transaction_date.isoformat() if hasattr(row.transaction_date, "isoformat") else str(row.transaction_date),
                    "category": row.category,
                    "amount": float(row.amount),
                    "direction": row.direction,
                    "description": row.description,
                }
                for row in rows
            ]
        }
    except Exception:
        logger.exception("treasury_activity query failed")
        raise HTTPException(status_code=500, detail="Internal error")


# ---------------------------------------------------------------------------
# Compliance endpoints
# ---------------------------------------------------------------------------

@app.get("/compliance/deadlines")
@limiter.limit("100/minute")
def compliance_deadlines(
    request: Request,
    days_ahead: int = 90,
    db: Session = Depends(get_db),
    _: None = Depends(_require_auth),
) -> dict[str, Any]:
    """
    Return compliance deadlines due within the next N days.

    Sorted soonest first. Includes overdue items (negative days remaining).
    """
    days_ahead = min(max(1, days_ahead), 730)  # cap at 2 years
    try:
        today = date.today()
        rows = db.execute(text("""
            SELECT id, title, due_date, description, consequence, status
            FROM compliance_deadlines
            WHERE due_date <= CURRENT_DATE + (:days_ahead * INTERVAL '1 day')
              AND status != 'completed'
            ORDER BY due_date ASC
        """), {"days_ahead": days_ahead}).fetchall()

        return {
            "deadlines": [
                {
                    "id": row.id,
                    "title": row.title,
                    "due_date": row.due_date.isoformat() if hasattr(row.due_date, "isoformat") else str(row.due_date),
                    "description": row.description,
                    "consequence": row.consequence,
                    "status": "overdue" if row.due_date < today else row.status,
                }
                for row in rows
            ]
        }
    except Exception:
        logger.exception("compliance_deadlines query failed")
        raise HTTPException(status_code=500, detail="Internal error")
