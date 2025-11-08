# app/chroma/indexer.py
from pathlib import Path
import fitz  # PyMuPDF
import uuid
from typing import List, Dict
from app.chroma.chroma_client import ChromaClient

# Where uploaded files live relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_DIR = (PROJECT_ROOT / "uploads").resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def extract_text_by_page(path: Path) -> List[Dict]:
    """
    Return list of {'page': int, 'text': str} for the given PDF or [] for unsupported.
    """
    path = Path(path)
    if not path.exists():
        return []
    if path.suffix.lower() != ".pdf":
        # treat as single text chunk for txt files
        try:
            return [{"page": 1, "text": path.read_text(encoding="utf8", errors="ignore")}]
        except Exception:
            return []

    chunks = []
    try:
        with fitz.open(str(path)) as doc:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                # skip empty pages
                if text.strip():
                    chunks.append({"page": i, "text": text.strip()})
    except Exception as e:
        print("[indexer] PDF read error:", e)
    return chunks

def index_file(path: Path, source_filename: str | None = None):
    """
    Read file, chunk (per-page), and upsert into Chroma collection 'brochures'.
    Returns dict with {'added': n, 'skipped': m} or raises on serious error.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    docs = extract_text_by_page(path)
    if not docs:
        return {"added": 0, "skipped": 0}

    # Prepare docs for ChromaClient.upsert_documents
    chroma = ChromaClient()
    # Add source_filename metadata if provided
    meta = {"source_filename": source_filename or path.name}
    chroma.upsert_documents(collection_name="brochures", docs=docs, metadata=meta)
    return {"added": len(docs), "skipped": 0}
