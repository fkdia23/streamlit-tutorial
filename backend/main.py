import logging
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, Request

from .audit import canonical_json, read_last, sha256_hex, write_audit
from .database import query_transactions
from .security import User, client_ctx, get_current_user, require_roles

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Secure Data API", version="1.0.0")

ANALYST_ROLES = ("Data-Analyst", "Admin")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/me")
def me(user: User = Depends(get_current_user)):
    """Identité telle que vue par l'API (tout utilisateur authentifié)."""
    return user.identity()


@app.get("/extract")
def extract(
    request: Request,
    country: str | None = None,
    category: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    user: User = Depends(require_roles(*ANALYST_ROLES)),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(400, "date_from doit être <= date_to")

    filters = {
        "country": country, "category": category, "status": status,
        "date_from": date_from, "date_to": date_to,
        "min_amount": min_amount, "max_amount": max_amount, "limit": limit,
    }
    rows = query_transactions(**filters)

    payload = canonical_json(rows)
    audit = write_audit({
        "event": "DATA_EXTRACTION",
        "user": user.identity(),
        "filters": {k: v for k, v in filters.items() if v is not None},
        "row_count": len(rows),
        "size_bytes": len(payload),
        "hash_algorithm": "SHA-256",
        "sha256": sha256_hex(payload),
        "hash_scope": "JSON canonique du tableau `data` (sort_keys, separators=(',',':'), UTF-8)",
        "token_azp": user.azp,
        **client_ctx(request),
    })

    return {
        "audit": {k: audit[k] for k in
                  ("audit_id", "timestamp_utc", "row_count", "size_bytes", "sha256", "hash_algorithm")},
        "data": rows,
    }


@app.get("/audit/logs")
def audit_logs(limit: int = Query(50, ge=1, le=500), _: User = Depends(require_roles("Admin"))):
    return read_last(limit)