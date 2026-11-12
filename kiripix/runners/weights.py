"""A Runner's weights on disk: `.kiripix/weights/<runner>/`, git-ignored, downloaded on first use.

Each file is verified against its declared hash before it is renamed into place, so a cancelled or failed download
leaves nothing that looks pulled. `weights.json` records the hash and licence beside the files.
"""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from kiripix.runners.base import CheckCancel, Runner, RunnerError

_CHUNK = 1 << 20
_TIMEOUT_SECONDS = 60
RECORD = "weights.json"


def weights_dir(state_dir: Path, runner: Runner) -> Path:
    return state_dir / "weights" / runner.id


def missing_weights(directory: Path, runner: Runner) -> list[str]:
    """The weight files not on disk (their hashes were verified when they were pulled)."""
    return [weight.name for weight in runner.weights if not (directory / weight.name).is_file()]


def _download(url: str, target: Path, expected: str, check_cancel: CheckCancel) -> None:
    import urllib.error  # loaded here: urllib.request pulls in ssl, which `kiripix --help` doesn't need
    import urllib.request

    fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    temporary = Path(name)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as handle, urllib.request.urlopen(url, timeout=_TIMEOUT_SECONDS) as response:
            while chunk := response.read(_CHUNK):
                check_cancel()
                handle.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RunnerError(f"{target.name} from {url} has the hash {digest.hexdigest()}, expected {expected}; "
                              "nothing was kept")
        os.replace(temporary, target)
    except (OSError, urllib.error.URLError) as error:
        raise RunnerError(f"can't download {target.name} from {url}: {error}") from None
    finally:
        temporary.unlink(missing_ok=True)


def pull(directory: Path, runner: Runner, check_cancel: CheckCancel) -> list[str]:
    """Download the weight files that are missing, and return their names."""
    directory.mkdir(parents=True, exist_ok=True)
    missing = missing_weights(directory, runner)
    for weight in runner.weights:
        if weight.name in missing:
            check_cancel()
            _download(weight.url, directory / weight.name, weight.sha256, check_cancel)
    record = {"runner": runner.id, "licence": runner.licence, "weights_hash": runner.weights_hash,
              "files": {weight.name: weight.sha256 for weight in runner.weights}}
    fd, name = tempfile.mkstemp(dir=directory, prefix=f".{RECORD}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, indent=2) + "\n")
    os.replace(name, directory / RECORD)
    return missing


def remove(directory: Path) -> bool:
    """Delete a Runner's weights. False when there were none."""
    if not directory.exists():
        return False
    shutil.rmtree(directory)
    return True
