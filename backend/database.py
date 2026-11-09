import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings

COLUMNS = "id, customer_name, country, category, product, amount, status, created_at"


@contextmanager
def get_conn():
    # Connexion en lecture seule : l'API ne peut jamais modifier les données
    uri = Path(settings.db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_transactions(
    country=None, category=None, status=None,
    date_from=None, date_to=None, min_amount=None, max_amount=None,
    limit: int = 1000,
) -> list[dict]:
    sql = f"SELECT {COLUMNS} FROM transactions WHERE 1=1"
    params: list = []

    # Requêtes 100 % paramétrées (pas d'injection SQL possible)
    if country:
        sql += " AND country = ?"; params.append(country)
    if category:
        sql += " AND category = ?"; params.append(category)
    if status:
        sql += " AND status = ?"; params.append(status)
    if date_from:
        sql += " AND created_at >= ?"; params.append(date_from.isoformat())
    if date_to:
        sql += " AND created_at <= ?"; params.append(date_to.isoformat())
    if min_amount is not None:
        sql += " AND amount >= ?"; params.append(min_amount)
    if max_amount is not None:
        sql += " AND amount <= ?"; params.append(max_amount)

    sql += " ORDER BY id LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]