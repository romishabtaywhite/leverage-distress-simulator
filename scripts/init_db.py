"""Creates db/leverage_sim.db from db/schema.sql. Run once, and again any
time you change the schema (safe to rerun - uses IF NOT EXISTS)."""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DB_PATH = ROOT / "db" / "leverage_sim.db"

if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")
