"""
LoanSphere — file_utils.py
Upload validation and temporary file cleanup helpers
"""
import os
import time

ALLOWED_EXTENSIONS = {'pdf', 'docx'}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def allowed_file(filename: str) -> bool:
    """Return True if the file extension is allowed."""
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def validate_file_size(file_storage) -> tuple[bool, str]:
    """
    Check that a werkzeug FileStorage object does not exceed the max size.
    Returns (ok: bool, error_message: str).
    """
    file_storage.seek(0, 2)          # seek to end
    size = file_storage.tell()
    file_storage.seek(0)             # rewind
    if size > MAX_FILE_SIZE_BYTES:
        mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        return False, f"File is too large. Maximum allowed size is {mb} MB."
    return True, ""


def cleanup_old_files(folder: str, max_age_seconds: int = 3600) -> int:
    """
    Delete files in *folder* that are older than *max_age_seconds*.
    Returns the number of files deleted.
    """
    deleted = 0
    if not os.path.isdir(folder):
        return deleted
    now = time.time()
    for fname in os.listdir(folder):
        fpath = os.path.join(folder, fname)
        if os.path.isfile(fpath):
            age = now - os.path.getmtime(fpath)
            if age > max_age_seconds:
                try:
                    os.remove(fpath)
                    deleted += 1
                except OSError as e:
                    print(f"[file_utils] Could not delete {fpath}: {e}")
    return deleted


def safe_filename(original: str, prefix: str = "") -> str:
    """
    Return a sanitized filename by stripping dangerous characters.
    Optionally prepend a *prefix* (e.g. a UUID).
    """
    from werkzeug.utils import secure_filename
    safe = secure_filename(original)
    if prefix:
        ext = safe.rsplit('.', 1)[-1] if '.' in safe else ''
        return f"{prefix}.{ext}" if ext else prefix
    return safe
