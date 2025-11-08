# probe_chroma.py
import chromadb
from pathlib import Path

print("Connecting to Chroma client...")
persist_path = Path(__file__).resolve().parent / "chroma_data"
client = chromadb.PersistentClient(path=str(persist_path))

try:
    collections = client.list_collections()
    print("\n✅ Available collections:")
    for coll in collections:
        print(" -", coll.name)
except Exception as e:
    print("❌ Failed to list collections:", e)

try:
    coll = client.get_collection("brochures")
    print("\n✅ Collection 'brochures' found:", coll)
except Exception as e:
    print("\n⚠️  get_collection('brochures') failed:", e)
