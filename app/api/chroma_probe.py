# app/api/chroma_probe.py
from ninja import Router
from app.chroma.chroma_client import ChromaClient, reload_client

router = Router()

@router.get("/", tags=["diagnostic"])
def probe_chroma(request):
    """
    Return list of available Chroma collections (names).
    Exposed as GET /probe_chroma/
    """
    cc = ChromaClient()
    try:
        cols = cc.list_collections() or []
        # Normalize to list of names
        names = []
        for c in cols:
            # depending on chroma version, items might be objects or dicts
            try:
                names.append(getattr(c, "name"))
            except Exception:
                try:
                    names.append(c.get("name"))
                except Exception:
                    try:
                        names.append(str(c))
                    except Exception:
                        pass
        return {"collections": names}
    except Exception as e:
        return {"error": str(e)}

@router.post("/reload/", tags=["diagnostic"])
def reload_chroma(request):
    try:
        reload_client()
        return {"ok": True, "message": "chroma client reloaded"}
    except Exception as e:
        return {"ok": False, "error": str(e)}