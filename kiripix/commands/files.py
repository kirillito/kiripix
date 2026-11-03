"""The file side of the adapters: serving Project files and taking uploads (spec §10.1).

An upload is stored in `.kiripix/uploads/` and answered with its Project-relative path, which the caller then passes
to the Command as an ordinary file path (`override`, `import`). Image outputs are already paths; `served_file` is how
they are fetched.
"""

import hashlib
import re
from pathlib import Path

from kiripix.core import atomic
from kiripix.core.errors import fail
from kiripix.core.project import STATE_DIR, find_project

UPLOAD_DIR = f"{STATE_DIR}/uploads"
_HIDDEN = {".git"}
_SERVED_STATE = {"previews"}  # of `.kiripix/`, only the previews are for the UI; locks and caches are not


def project_root(cwd: Path) -> Path:
    return find_project(cwd).root


def served_file(root: Path, relative: str) -> Path | None:
    """The file `relative` names inside the Project, or None when it doesn't exist or reaches outside the Project."""
    target = (root / relative).resolve()
    try:
        parts = target.relative_to(root.resolve()).parts
    except ValueError:
        return None
    if not parts or parts[0] in _HIDDEN or not target.is_file():
        return None
    if parts[0] == STATE_DIR and (len(parts) < 3 or parts[1] not in _SERVED_STATE):
        return None
    return target


def save_upload(root: Path, name: str, data: bytes) -> str:
    """Store the bytes under a name made of their hash and the cleaned file name; returns the Project-relative path."""
    if not data:
        raise fail("upload.empty", "the upload has no content",
                   owner_action="Choose a file that has content, and upload it again.")
    clean = re.sub(r"[^A-Za-z0-9._-]", "_", Path(name.replace("\\", "/")).name).lstrip(".") or "upload"
    relative = f"{UPLOAD_DIR}/{hashlib.sha256(data).hexdigest()[:12]}-{clean}"
    atomic.write_bytes(root / relative, data)
    return relative
