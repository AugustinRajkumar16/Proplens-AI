# app/api/ingestion.py
from ninja import Router, Schema, File, UploadedFile
from ninja.errors import ValidationError
from pathlib import Path
from typing import Optional
import uuid
import threading
import subprocess
import sys
import os

from app.api.auth import JWTBearer
from app.chroma.indexer import index_file, UPLOADS_DIR

router = Router()
auth = JWTBearer()

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

class UploadResp(Schema):
    job_id: str
    stored_path: str
    background: bool

class IndexOneIn(Schema):
    filename: str
    background: Optional[bool] = True

class IndexOneOut(Schema):
    job_id: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None
    message: Optional[str] = None

# helper to spawn index script in background using current Python interpreter
def _spawn_index_subprocess(target_path: Path, log_dir: Path) -> subprocess.Popen:
    """
    Spawn `index_uploads.py --file <target_path>` as background process.
    Returns subprocess.Popen (already started).
    """
    # Ensure index script is referenced relative to project root
    project_root = Path(__file__).resolve().parents[2]
    index_script = project_root / "index_uploads.py"
    if not index_script.exists():
        raise FileNotFoundError(f"Index script not found: {index_script}")

    # Prepare log file
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_name = target_path.name.replace(" ", "_").replace("/", "_")
    log_file = log_dir / f"index_{safe_name}.log"

    cmd = [sys.executable, str(index_script), "--file", str(target_path)]
    # start process; do not wait here
    with open(log_file, "ab") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, cwd=str(project_root))
    return proc

def _index_in_thread(target_path: Path, job_id: str):
    """
    Thread wrapper to spawn subprocess (keeps thread alive only to detach).
    This thread simply spawns the subprocess; the subprocess does the heavy work.
    """
    try:
        logs = Path(__file__).resolve().parents[2] / "logs"
        _spawn_index_subprocess(target_path, logs)
    except Exception as e:
        # Best-effort logging; do not raise from background thread
        print(f"[ingestion] background indexing failed for {target_path}: {e}")

@router.post("/upload/", auth=auth, response=UploadResp)
def upload_document(request, file: UploadedFile = File(...), background: Optional[bool] = True):
    """
    Upload a file and either index it in background (default) or block and index immediately.
    Robustly handle both Starlette UploadFile and Django UploadedFile objects.
    """
    # Determine original filename in a robust way
    original_name = None
    # Starlette UploadFile usually has `.filename`
    original_name = getattr(file, "filename", None)
    # Django UploadedFile often has `.name`
    if not original_name:
        original_name = getattr(file, "name", None)
    # Sometimes underlying file-like has a .name attribute (file.file)
    if not original_name and getattr(file, "file", None) is not None:
        original_name = getattr(getattr(file, "file"), "name", None)
    if not original_name:
        original_name = "uploaded"

    # Save file with UUID prefix to avoid collisions
    safe_name = f"{uuid.uuid4().hex}_{Path(original_name).name}"
    dest_path = UPLOADS_DIR / safe_name

    # Write file robustly
    try:
        # Django UploadedFile supports .chunks()
        if hasattr(file, "chunks") and callable(getattr(file, "chunks")):
            with open(dest_path, "wb") as dest:
                for chunk in file.chunks():
                    dest.write(chunk)
        else:
            # Starlette UploadFile has .file (a SpooledTemporaryFile / file-like)
            # file.file.read() works synchronously in this sync endpoint
            raw = None
            try:
                # If it's a Starlette UploadFile, this will work
                raw = file.file.read()
            except Exception:
                # As a last resort, try .read() on the object itself
                try:
                    raw = file.read()
                except Exception as e:
                    raise ValidationError(f"Failed to read uploaded file bytes: {e}")
            with open(dest_path, "wb") as dest:
                dest.write(raw)
    except Exception as e:
        raise ValidationError(f"Failed to save uploaded file: {e}")

    job_id = uuid.uuid4().hex

    if background:
        # spawn a small thread that will start the subprocess (detached)
        t = threading.Thread(target=_index_in_thread, args=(dest_path, job_id), daemon=True)
        t.start()
        return {"job_id": job_id, "stored_path": dest_path.name, "background": True}
    else:
        # blocking (call index_file directly)
        try:
            idx_res = index_file(dest_path, source_filename=original_name)
            return {"job_id": job_id, "stored_path": dest_path.name, "background": False}
        except Exception as e:
            raise ValidationError(f"Indexing failed: {e}")


@router.post("/index_one/", auth=auth, response=IndexOneOut)
def index_one(request, payload: IndexOneIn):
    """
    Index an existing uploaded file by filename (the stored filename, i.e. UUID_prefixed name).
    payload.filename should be the stored filename as listed by /probe_projects/.
    payload.background controls whether indexing is background (True) or blocking (False).
    """
    target = UPLOADS_DIR / payload.filename
    if not target.exists():
        return IndexOneOut(message=f"File not found: {payload.filename}")

    job_id = uuid.uuid4().hex

    if payload.background:
        t = threading.Thread(target=_index_in_thread, args=(target, job_id), daemon=True)
        t.start()
        return IndexOneOut(job_id=job_id, message="Indexing started (background)")
    else:
        # Blocking: either call index_file() directly or call index script and capture output.
        # We'll call index_file() for correctness (it uses the same indexer).
        try:
            res = index_file(target, source_filename=target.name)
            return IndexOneOut(job_id=job_id, message="Indexing completed (blocking)")
        except Exception as e:
            return IndexOneOut(message=f"Indexing failed: {e}")
