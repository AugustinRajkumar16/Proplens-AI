# app/api/campaigns.py
from ninja import Router
from typing import Optional
from pathlib import Path
import sqlite3

router = Router()

DB_PATH = Path(__file__).resolve().parents[1].parent / "db.sqlite3"

@router.get("/analytics")
def analytics(request, project: Optional[str] = None):
    """
    Return simple analytics for the given project name (project is optional).
    Currently computes:
      - leads_shortlisted: number of leads with shortlisted=1
      - messages_sent: 0 (placeholder)
      - unique_responses: 0 (placeholder)
      - goals_achieved: 0 (placeholder)

    You can extend this to compute metrics scoped by project by storing
    project references in the leads table and filtering here.
    """
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS leads (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, phone TEXT, shortlisted INTEGER)')
    # Basic metric: count shortlisted leads (global for now)
    try:
        cur.execute("SELECT COUNT(*) FROM leads WHERE shortlisted=1")
        leads_shortlisted = cur.fetchone()[0] or 0
    except Exception:
        leads_shortlisted = 0

    # placeholders (extend to real values if you store these)
    messages_sent = 0
    unique_responses = 0
    goals_achieved = 0

    conn.close()

    return {
        "project": project,
        "leads_shortlisted": leads_shortlisted,
        "messages_sent": messages_sent,
        "unique_responses": unique_responses,
        "goals_achieved": goals_achieved,
    }
