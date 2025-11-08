# app/chroma/chroma_client.py
from pathlib import Path
from typing import Optional, Callable, Any
import traceback

# Module-level placeholders that will be set by _try_imports()
_chromadb = None
_Settings = None
_embedding_functions = None

# Project persist dir
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CHROMA_PERSIST_DIR = (PROJECT_ROOT / "chroma_data").resolve()
_CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)


def _try_imports():
    """
    Lazy import chromadb and related helpers. This keeps import-time failures
    non-fatal for the rest of the app; callers should handle client==None.
    """
    global _chromadb, _Settings, _embedding_functions
    if _chromadb is not None:
        return

    try:
        import chromadb as chromadb_mod  # type: ignore
        _chromadb = chromadb_mod
    except Exception as e:
        print("[chroma_client] WARNING: 'chromadb' import failed:", e)
        traceback.print_exc()
        _chromadb = None
        _Settings = None
        _embedding_functions = None
        return

    # Try to import Settings and embedding utilities if available
    try:
        from chromadb.config import Settings as SettingsCls  # type: ignore
        _Settings = SettingsCls
    except Exception:
        _Settings = None

    try:
        from chromadb.utils import embedding_functions as emb_funcs  # type: ignore
        _embedding_functions = emb_funcs
    except Exception:
        _embedding_functions = None

def get_embedding_function(model_name: str = "all-MiniLM-L6-v2") -> Optional[Callable[[list], list]]:
    """
    Return a chromadb-compatible embedding function wrapper (SentenceTransformer)
    if chromadb.utils.embedding_functions is available. Return None otherwise.
    """
    _try_imports()
    if _embedding_functions is None:
        return None
    try:
        return _embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    except Exception:
        # If building the embedding fn fails, return None
        return None

# Internal cached client
_client = None

def _make_client(persist_path: Optional[Path] = None):
    _try_imports()
    if _chromadb is None:
        print("[chroma_client] chromadb not available; returning None.")
        return None

    persist = Path(persist_path or _CHROMA_PERSIST_DIR).resolve()
    persist.mkdir(parents=True, exist_ok=True)
    print(f"[chroma_client] Using persist directory: {persist}")

    try:
        client = _chromadb.PersistentClient(path=str(persist))
        print("[chroma_client] Created chromadb.PersistentClient")
        return client
    except Exception as e:
        print("[chroma_client] PersistentClient creation failed:", e)
        return None


def get_client():
    """
    Return a singleton client for the process (or None if chromadb missing).
    """
    global _client
    if _client is None:
        _client = _make_client()
    return _client

def reload_client():
    """
    Force creation of a new underlying chroma client on next get_client() call.
    Call this after external processes modify the persist dir (e.g., background index).
    """
    global _client
    _client = None

class ChromaClient:
    """
    Thin wrapper used by the rest of the project. Methods handle client==None gracefully.
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        # If persist_dir provided, create a dedicated client for that path.
        self.client = get_client() if persist_dir is None else _make_client(persist_dir)

    def list_collections(self):
        if not self.client:
            return []
        try:
            return self.client.list_collections()
        except Exception:
            try:
                # older API sometimes provides get_collections
                return getattr(self.client, "get_collections", lambda: [])()
            except Exception:
                return []

    def get_collection(self, name: str):
        if not self.client:
            raise RuntimeError("Chroma client not available")
        if hasattr(self.client, "get_collection"):
            try:
                return self.client.get_collection(name=name)
            except TypeError:
                return self.client.get_collection(name)
        raise RuntimeError("Underlying client doesn't expose get_collection")

    def create_collection(self, name: str, embedding_function: Any = None):
        if not self.client:
            raise RuntimeError("Chroma client not available")
        try:
            if embedding_function is not None:
                return self.client.create_collection(name=name, embedding_function=embedding_function)
            return self.client.create_collection(name=name)
        except TypeError:
            # fallback for older signature
            return self.client.create_collection(name)

    def semantic_search(self, collection_name: str, query: str, top_k: int = None, n_results: int = None):
        """
        Compatibility wrapper for various chroma client versions.
        Accepts either top_k or n_results as the requested number of matches.
        """
        if top_k is None and n_results is not None:
            top_k = n_results
        if top_k is None:
            top_k = 3
        if not self.client:
            raise RuntimeError("Chroma client not available")
        coll = self.get_collection(collection_name)
        # Newer chroma returns a dict-like response for query()
        if hasattr(coll, "query"):
            try:
                # try the most explicit form first (query_texts + n_results)
                return coll.query(query_texts=[query], n_results=top_k)
            except TypeError:
                try:
                    # older variant expects (query_list, top_k)
                    return coll.query([query], top_k)
                except Exception as e:
                    raise RuntimeError(f"coll.query signature attempts failed: {e}")
        if hasattr(coll, "similarity_search"):
            try:
                return coll.similarity_search(query, k=top_k)
            except Exception as e:
                raise RuntimeError(f"similarity_search failed: {e}")
        raise RuntimeError("Collection does not support known query APIs")
    
    # inside class ChromaClient (append methods)
    def upsert_documents(self, collection_name: str, docs: list, metadata: dict | None = None, ids: list | None = None, embeddings: list | None = None):
        """
        Add/upsert documents into a collection. Accepts:
         - docs: list[dict] of {'page': int, 'text': str} or list[str]
         - metadata: dict to attach to all docs, or list[dict] per-doc
         - ids: optional list of ids (if not provided, safe placeholders will be generated)
         - embeddings: optional embeddings list
        This wraps different chromadb collection APIs and is defensive about different signatures.
        """
        if not self.client:
            raise RuntimeError("Chroma client not available")
        # Ensure collection exists
        try:
            coll = self.get_collection(collection_name)
        except Exception:
            coll = self.create_collection(collection_name)

        # Normalize docs -> texts and metas
        texts = []
        metas = []
        if docs and isinstance(docs[0], dict) and 'text' in docs[0]:
            for d in docs:
                texts.append(d.get('text'))
                m = d.copy()
                m.pop('text', None)
                metas.append({**(metadata or {}), **m} if metadata else m)
        else:
            texts = list(docs)
            if metadata:
                metas = [metadata] * len(texts)
            else:
                metas = [{}] * len(texts)

        # Ensure we have ids (some versions require it)
        if ids is None:
            # create placeholder ids (unique-ish)
            ids = [f"doc_{i}" for i in range(len(texts))]

        # Build payloads carefully and try preferred APIs first
        # Try upsert (newer), else try add with explicit ids
        try:
            if hasattr(coll, "upsert"):
                payload = {"ids": ids, "documents": texts, "metadatas": metas}
                if embeddings:
                    payload["embeddings"] = embeddings
                return coll.upsert(**payload)
            else:
                # prefer coll.add with explicit ids
                kwargs = {"ids": ids, "documents": texts, "metadatas": metas}
                if embeddings:
                    kwargs["embeddings"] = embeddings
                return coll.add(**kwargs)
        except TypeError as te:
            # signature mismatch on upsert/add — try minimal call forms
            try:
                # Some older variants expect (documents, metadatas, ids)
                return coll.add(ids, texts, metas)  # positional fallback
            except Exception:
                try:
                    # Another fallback: pass documents/metadatas but ensure ids present as positional first arg
                    return coll.add(ids, documents=texts, metadatas=metas)
                except Exception as e:
                    # Give a clear error to caller
                    raise RuntimeError(f"chroma collection add/upsert signature incompatible: {e} (original TypeError: {te})")
        except Exception as exc:
            # Bubble other exceptions up
            raise
