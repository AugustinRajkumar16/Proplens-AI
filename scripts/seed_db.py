# scripts/seed_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / 'db.sqlite3'
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, shortlisted INTEGER)')
cur.execute("INSERT INTO leads (name, email, phone, shortlisted) VALUES ('Alice', 'alice@example.com', '1234567890', 1)")
cur.execute("INSERT INTO leads (name, email, phone, shortlisted) VALUES ('Bob', 'bob@example.com', '2345678901', 0)")
conn.commit()
conn.close()
print('Seeded DB at', DB_PATH)
