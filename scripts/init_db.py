import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

COUNTRIES = ["France", "Germany", "Spain", "Italy", "Belgium"]
STATUSES = ["completed", "pending", "refunded", "cancelled"]
PRODUCTS = {
    "Electronics": ["Laptop", "Smartphone", "Headphones", "Monitor"],
    "Clothing": ["Jacket", "Sneakers", "T-shirt", "Jeans"],
    "Home": ["Lamp", "Sofa", "Vacuum", "Blender"],
    "Sports": ["Bike", "Tent", "Running shoes", "Yoga mat"],
    "Books": ["Novel", "Cookbook", "Biography", "Comics"],
}

SCHEMA = """
CREATE TABLE transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    country       TEXT NOT NULL,
    category      TEXT NOT NULL,
    product       TEXT NOT NULL,
    amount        REAL NOT NULL,
    status        TEXT NOT NULL,
    created_at    TEXT NOT NULL  -- YYYY-MM-DD
);
CREATE INDEX idx_tx_country  ON transactions(country);
CREATE INDEX idx_tx_category ON transactions(category);
CREATE INDEX idx_tx_date     ON transactions(created_at);
"""


def create_and_seed(db_path: str, n: int = 5000, seed: int = 42) -> int:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(db_path).unlink(missing_ok=True)

    fake = Faker("fr_FR")
    Faker.seed(seed)
    rnd = random.Random(seed)
    today = date.today()

    rows = []
    for _ in range(n):
        category = rnd.choice(list(PRODUCTS))
        rows.append((
            fake.name(),
            rnd.choice(COUNTRIES),
            category,
            rnd.choice(PRODUCTS[category]),
            round(rnd.uniform(5, 2500), 2),
            rnd.choices(STATUSES, weights=[70, 15, 8, 7])[0],
            (today - timedelta(days=rnd.randint(0, 730))).isoformat(),
        ))

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO transactions (customer_name, country, category, product, amount, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return n


if __name__ == "__main__":
    from backend.config import settings

    count = create_and_seed(settings.db_path)
    print(f"{count} transactions simulées dans {settings.db_path}")