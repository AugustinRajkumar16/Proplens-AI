# index_chunked_and_embed.py
from pathlib import Path
import uuid
import pprint
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
import numpy as np
import chromadb
import requests

CODE_ROOT = Path(__file__).resolve().parent
UPLOADS_DIR = CODE_ROOT / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

print("Loading SentenceTransformer (this may take a few seconds)...")
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

def extract_text_from_pdf(path: Path) -> str:
    txt = []
    try:
        with fitz.open(str(path)) as doc:
            for page in doc:
                text = page.get_text("text")
                if text:
                    txt.append(text)
    except Exception as e:
        print("PDF read error:", e)
    return "\n\n".join(txt).strip()

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    if not text:
        return []
    chunks = []
    start = 0
    total_len = len(text)
    while start < total_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= total_len:
            break
        start = max(0, end - overlap)
    return [c for c in chunks if c]

def ensure_client():
    persist_path = Path(__file__).resolve().parent / "chroma_data"
    persist_path.mkdir(exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_path))
    print("[index] Created persistent chromadb.PersistentClient at:", persist_path)
    return client

def create_or_get_collection(client, name="brochures"):
    try:
        collection = client.get_or_create_collection(name=name)
        print("Using get_or_create_collection:", name)
        return collection
    except Exception as e:
        print("get_or_create_collection failed:", e)
        try:
            return client.get_collection(name=name)
        except Exception:
            pass
        try:
            return client.create_collection(name=name)
        except Exception as ex:
            raise RuntimeError(f"Failed to create or get collection: {ex}")

def index_all():
    client = ensure_client()
    print("Client type:", type(client))

    collection = create_or_get_collection(client, name="brochures")

    ids, docs, metas, embeddings = [], [], [], []

    for file in sorted(UPLOADS_DIR.iterdir()):
        if not file.is_file():
            continue
        if file.suffix.lower() not in (".pdf", ".txt"):
            continue

        print("Processing:", file.name)
        text = extract_text_from_pdf(file) if file.suffix.lower() == ".pdf" else file.read_text(encoding="utf8", errors="ignore")

        if not text:
            print("  -> No text, skipping")
            continue

        chunks = chunk_text(text)
        print(f"  -> {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            chunk_id = f"{file.name}__{i}__{uuid.uuid4().hex[:8]}"
            ids.append(chunk_id)
            docs.append(chunk)
            metas.append({"source": file.name, "chunk_index": i})

    if not ids:
        print("No chunks prepared; nothing to add.")
        return

    print("Computing embeddings for", len(docs), "chunks...")
    batch_size = 128
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        embs = embed_model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        for emb in embs:
            embeddings.append(emb.tolist() if isinstance(emb, (list, tuple)) else np.array(emb).tolist())

    print("Adding to collection (attempting coll.add with embeddings)...")
    try:
        collection.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        print("coll.add() with embeddings succeeded.")
    except Exception as e:
        print("coll.add() failed:", e)
        raise

    print("Attempting to persist client/collection...")
    try:
        print("client.list_collections() ->")
        pprint.pprint(client.list_collections())
    except Exception as e:
        print("list_collections failed:", e)
    
    # Notify backend to reload chroma client singleton (best-effort)
    try:
        requests.post("http://127.0.0.1:8000/probe_chroma/reload/", timeout=2)
    except Exception:
        pass

    print("Indexing done.")

if __name__ == "__main__":
    index_all()
