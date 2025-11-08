import chromadb
from chromadb.config import Settings
from pathlib import Path
import pprint

pd = Path('./chroma_data').resolve()
print("Checking persist dir:", pd, "exists?", pd.exists())

settings = Settings(persist_directory=str(pd))
client = chromadb.Client(settings=settings)
print("Client created with Settings; list_collections():")
pprint.pprint(client.list_collections())
