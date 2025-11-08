# main.py
"""
Cross-platform launcher for the Proplens project.

Usage (from project root, inside the project's Python environment):
    python run_all.py

What it does (in order):
 1. ensures env vars are available (reads .env if present)
 2. seeds the sqlite DB (scripts/seed_db.py)
 3. if uploads/ contains PDFs/TXT, runs the index script (index_uploads.py) to create Chroma vectors
 4. starts backend uvicorn server (app.asgi:app) on port 8000
 5. starts streamlit frontend (frontend_app.py) on port 8501
 6. relays child stdout/stderr to this console
 7. on Ctrl+C, terminates child processes cleanly
"""
import os
import sys
import subprocess
import time
import signal
import shutil
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")  # optional; safe if .env missing

PY = sys.executable or "python"

# Commands (use explicit module paths where possible)
SEED_CMD = [PY, str(ROOT / "scripts" / "seed_db.py")]
INDEX_CMD = [PY, str(ROOT / "index_uploads.py")]
# fallback index script name if you prefer index_chunked_and_embed.py
ALT_INDEX_CMD = [PY, str(ROOT / "index_chunked_and_embed.py")]

# backend uvicorn: use asgi (Django) or standalone ninja as needed
USE_DJANGO_ASGI = True  # set False to run standalone Ninja
if USE_DJANGO_ASGI:
    UVICORN_CMD = [PY, "-m", "uvicorn", "app.asgi:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
else:
    UVICORN_CMD = [PY, "-m", "uvicorn", "app.standalone_asgi:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]

# streamlit
STREAMLIT_CMD = [PY, "-m", "streamlit", "run", str(ROOT / "frontend_app.py"), "--server.port", "8501", "--server.headless", "true"]

CHILDREN = []

def run_and_wait(cmd, name, wait_startup_seconds=0.5, env=None):
    print(f"[launcher] Starting {name}: {' '.join(cmd)}")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT))
    CHILDREN.append((name, p))
    # stream startup logs asynchronously
    def _stream_out(proc, label):
        try:
            for line in proc.stdout:
                if not line:
                    break
                sys.stdout.buffer.write(f"[{label}] ".encode("utf-8") + line)
                sys.stdout.flush()
        except Exception:
            pass

    import threading
    t = threading.Thread(target=_stream_out, args=(p, name), daemon=True)
    t.start()
    if wait_startup_seconds:
        time.sleep(wait_startup_seconds)
    return p

def run_once_script(cmd):
    try:
        print(f"[launcher] Running one-off: {' '.join(cmd)}")
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(ROOT), env=os.environ, check=False)
        out = r.stdout.decode("utf-8", errors="ignore")
        print(out)
        return r.returncode == 0
    except Exception as e:
        print("[launcher] One-off script failed:", e)
        return False

def has_uploads():
    uploads = (ROOT / "uploads")
    if not uploads.exists():
        return False
    for f in uploads.iterdir():
        if f.is_file() and f.suffix.lower() in (".pdf", ".txt", ".docx"):
            return True
    return False

def prepare_uploads_from_dataset():
    """
    Ensure uploads/ exists and copy brochure files from Dataset_brochure/ into it
    if uploads/ is empty. This keeps the run_all experience consistent for local runs.
    """
    uploads = ROOT / "uploads"
    dataset = ROOT / "Dataset_brochure"

    try:
        uploads.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print("[launcher] Warning: could not create uploads/ directory:", e)
        return

    # If uploads already contains PDFs/TXT/DOCX, don't overwrite
    for f in uploads.iterdir():
        if f.is_file() and f.suffix.lower() in (".pdf", ".txt", ".docx"):
            print("[launcher] uploads/ already contains files — skipping copy from Dataset_brochure/")
            return

    # If no Dataset_brochure dir present, nothing to copy
    if not dataset.exists() or not dataset.is_dir():
        print("[launcher] No Dataset_brochure/ directory found — leaving uploads/ empty.")
        return

    # Copy matching files
    copied = 0
    for p in sorted(dataset.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() in (".pdf", ".txt", ".docx"):
            dest = uploads / p.name
            try:
                shutil.copy2(str(p), str(dest))
                copied += 1
            except Exception as e:
                print(f"[launcher] Failed to copy {p} -> {dest}: {e}")

    print(f"[launcher] Copied {copied} file(s) from Dataset_brochure/ to uploads/ (if any).")

def terminate_children():
    print("[launcher] Terminating children...")
    for name, p in CHILDREN:
        try:
            print(f"[launcher] Terminating {name} (pid={p.pid})")
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)
                p.kill()
            else:
                p.terminate()
        except Exception as e:
            print("  ->", e)
    # allow a moment
    time.sleep(1)
    for name, p in CHILDREN:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass

def main():
    try:
        # 0. ensure important env vars have defaults (useful for other machines)
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
        os.environ.setdefault("DJANGO_SECRET", "dev-secret")
        os.environ.setdefault("JWT_SECRET", "supersecret")
        print("[launcher] Ensured default env vars.")

        # Prepare uploads/ (create and copy dataset brochures if uploads is empty)
        prepare_uploads_from_dataset()

        # 1. seed DB
        print("[launcher] Seeding DB (scripts/seed_db.py)...")
        run_once_script(SEED_CMD)

        # 2. index uploads if present
        if has_uploads():
            print("[launcher] uploads/ contains files — running index script to create embeddings (index_uploads.py).")
            ok = run_once_script(INDEX_CMD)
            if not ok:
                print("[launcher] index_uploads.py returned non-zero; trying alt index script.")
                run_once_script(ALT_INDEX_CMD)
        else:
            print("[launcher] uploads/ empty — skipping indexing (will run on-demand via /documents/upload/ endpoint).")

        # 3. start backend
        backend_proc = run_and_wait(UVICORN_CMD, "backend", wait_startup_seconds=1.0)

        # 4. start frontend
        frontend_proc = run_and_wait(STREAMLIT_CMD, "streamlit", wait_startup_seconds=1.0)

        print("[launcher] Backend available at http://127.0.0.1:8000")
        print("[launcher] Frontend available at http://127.0.0.1:8501")
        print("[launcher] Press Ctrl+C to stop everything.")

        # Keep main thread alive while children run
        while True:
            # poll processes
            for name, p in list(CHILDREN):
                if p.poll() is not None:
                    print(f"[launcher] Child {name} exited with code {p.returncode}")
                    CHILDREN.remove((name, p))
            time.sleep(0.5)
            if not CHILDREN:
                print("[launcher] All children exited; shutting down.")
                break

    except KeyboardInterrupt:
        print("\n[launcher] KeyboardInterrupt received.")
    finally:
        terminate_children()
        print("[launcher] Done. Bye.")

if __name__ == "__main__":
    main()
