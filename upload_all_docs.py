# upload_all_docs.py
import os, requests

# Get the project folder from the current script location
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))   # Points to Project_CRM
folder = os.path.join(PROJECT_ROOT, 'Dataset_brochure')


url = "http://127.0.0.1:8000/documents/upload/"
# Read the JWT token from environment variable 'JWT_TOKEN'
token = os.environ.get("JWT_TOKEN")  # Note: use exact env var name set in your cmd

if not token:
    print("Set JWT_TOKEN environment variable first (in cmd prompt: set JWT_TOKEN=<your token>)")
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {token}"}

if not os.path.isdir(folder):
    print(f"Folder not found: {folder}")
    raise SystemExit(1)

for fname in os.listdir(folder):
    if not fname.lower().endswith(".pdf"):
        continue
    path = os.path.join(folder, fname)
    print("Uploading:", path)
    with open(path, "rb") as f:
        files = {"file": (fname, f, "application/pdf")}
        r = requests.post(url, headers=headers, files=files, timeout=120)
    print("->", r.status_code, r.text)
