# app/api/probe.py
from ninja import Router, Schema
from pathlib import Path
from typing import List, Optional
from app.api.auth import JWTBearer
from app.chroma.indexer import index_file, UPLOADS_DIR

router = Router()
auth = JWTBearer()

class ProjectsOut(Schema):
    projects: List[str]

@router.get("/", response=ProjectsOut)
def probe_projects(request):
    """
    Return list of uploaded filenames (basename only) discovered under uploads/.
    Registered under prefix '/probe_projects/' so this handler will be available at:
      GET /probe_projects/
    """
    projects = []
    uploads = UPLOADS_DIR
    if uploads.exists():
        for p in sorted(uploads.iterdir()):
            if p.is_file() and p.suffix.lower() in (".pdf", ".txt"):
                projects.append(p.name)
    return {"projects": projects}


class IndexOneIn(Schema):
    filename: str

class IndexOneOut(Schema):
    ok: bool
    added: Optional[int] = None
    message: Optional[str] = None

@router.post("/documents/index_one/", auth=auth, response=IndexOneOut)
def index_one(request, payload: IndexOneIn):
    """
    Index a single named file that already exists under uploads/.
    Registered as POST /probe_projects/documents/index_one/
    """
    target = (UPLOADS_DIR / payload.filename)
    if not target.exists():
        return {"ok": False, "message": f"File not found: {payload.filename}"}

    try:
        res = index_file(target, source_filename=payload.filename)
        return {"ok": True, "added": res.get("added", 0), "message": "Indexed"}
    except Exception as e:
        return {"ok": False, "message": f"Indexing failed: {e}"}
