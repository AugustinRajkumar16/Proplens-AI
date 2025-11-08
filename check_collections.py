# check_collections.py
from app.chroma.chroma_client import ChromaClient

print("Project wrapper instance:", ChromaClient())
cwrap = ChromaClient()
inner = cwrap.client
print("inner client type:", type(inner))

try:
    cols = inner.list_collections()
    print("list_collections() ->", cols)
    if cols:
        print("Collections (names):", [coll.name for coll in cols])
    else:
        print("No collections returned (empty list).")
except Exception as e:
    print("list_collections() raised:", e)

try:
    coll = inner.get_collection("brochures")
    print("get_collection('brochures') -> OK:", coll)
except Exception as e:
    print("get_collection('brochures') failed:", e)
