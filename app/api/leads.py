# app/api/leads.py
from ninja import Router, Schema
from pydantic import Field
from typing import List
import sqlite3
from pathlib import Path

router = Router()
DB_PATH = Path(__file__).resolve().parents[1] / '..' / 'db.sqlite3'

class LeadIn(Schema):
    name: str
    email: str
    phone: str | None = None
    shortlisted: bool | None = False

class LeadOut(LeadIn):
    id: int

@router.post('/', response=LeadOut)
def create_lead(request, payload: LeadIn):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, shortlisted INTEGER)')
    cur.execute('INSERT INTO leads (name, email, phone, shortlisted) VALUES (?, ?, ?, ?)', (payload.name, payload.email, payload.phone, int(payload.shortlisted)))
    conn.commit()
    lid = cur.lastrowid
    conn.close()
    return {**payload.dict(), 'id': lid}

@router.get('/', response=List[LeadOut])
def list_leads(request):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, shortlisted INTEGER)')
    rows = cur.execute('SELECT id, name, email, phone, shortlisted FROM leads').fetchall()
    conn.close()
    return [{'id': r[0], 'name': r[1], 'email': r[2], 'phone': r[3], 'shortlisted': bool(r[4])} for r in rows]
