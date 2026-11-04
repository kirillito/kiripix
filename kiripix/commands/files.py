"""The file side of the adapters: serving Project files and taking file inputs (spec §10.1, ADR 0007).

A file input sent over REST (a multipart part of the Command's own request) is stored in a temporary folder outside
the Project and handed to the Command as a path; the folder is deleted when the Command ends. Nothing lands in the
Project except what the Command itself writes. Image outputs are already paths; `served_file` is how they are fetched.
"""

import re
import shutil
import tempfile
from pathlib import Path

from kiripix.core import atomic
from kiripix.core.project import STATE_DIR, find_project

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


class FileInputs:
    """A temporary folder outside the Project holding a request's file inputs, one subfolder per field."""

    def __init__(self) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix="kiripix-files-"))

    def store(self, field: str, filename: str | None, data: bytes) -> Path:
        """Store one file under its cleaned name (the field's name when it has none); returns its path."""
        clean = re.sub(r"[^A-Za-z0-9._-]", "_", Path((filename or "").replace("\\", "/")).name).lstrip(".")
        path = self.folder / field / (clean or field)
        atomic.write_bytes(path, data)
        return path

    def remove(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)
