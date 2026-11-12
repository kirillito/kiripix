"""Pinned Runner calls (ADR 0002, spec §5): `pinned/<key>.png` and `pinned/<key>.json`, committed with the Asset.

The key covers everything that decides a call's result: the input image's hash, the Decisions and parameters, and the
Runner's ID with a hash of its weights. The device isn't part of it. The record beside the result says what made it. The
PNG is written last, so a result that exists is a whole one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.core import atomic
from kiripix.core.hashing import hash_json
from kiripix.core.images import save_mask_png, save_png
from kiripix.recipes.base import RunnerCall
from kiripix.runners import runners

PINNED_DIR = "pinned"
# 2 adds `result_hash` (ticket 0095). A version 1 record has none, and reads as a result not known to be as made,
# so its key is reviewed once more: nothing to migrate.
RECORD_SCHEMA_VERSION = 2


def key(call: RunnerCall, image_hash: str) -> str:
    return hash_json({"runner": call.runner, "weights": runners()[call.runner].weights_hash, "image": image_hash,
                      "params": call.params, "decisions": call.decisions})


def result_path(asset_dir: Path, pin: str) -> Path:
    return asset_dir / PINNED_DIR / f"{pin}.png"


def was_made_before(asset_dir: Path, stage: str, call: RunnerCall) -> bool:
    """Whether a record shows the same Decisions pinned on other inputs, or by another Runner: so the call's input
    changed. It chooses only between two reasons, so a record a merge broke counts for nothing."""
    for path in (asset_dir / PINNED_DIR).glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and (record.get("stage"), record.get("decisions")) == (stage, call.decisions):
            return True
    return False


def store(asset_dir: Path, stage: str, call: RunnerCall, pin: str, image_hash: str, result: np.ndarray, *, device: str,
          licence: str, time: str) -> None:
    """Pin a call's result: a Mask as a 1-bit PNG, or else an RGBA image."""
    record: dict[str, Any] = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "key": pin,
        "stage": stage,
        "runner": call.runner,
        "weights_hash": runners()[call.runner].weights_hash,
        "licence": licence,
        "image_hash": image_hash,
        "params": call.params,
        "decisions": call.decisions,
        "device": device,
        "time": time,
    }
    atomic.write_json(asset_dir / PINNED_DIR / f"{pin}.json", record)
    if result.dtype == np.bool_:
        save_mask_png(result_path(asset_dir, pin), result)
    else:
        save_png(result_path(asset_dir, pin), result)
    # Written after the PNG, so a record with it says the PNG is whole and as the Runner made it (see `is_as_made`).
    record["result_hash"] = hashlib.sha256(result_path(asset_dir, pin).read_bytes()).hexdigest()
    atomic.write_json(asset_dir / PINNED_DIR / f"{pin}.json", record)


def is_as_made(asset_dir: Path, pin: str, png_hash: str) -> bool:
    """Whether the pinned PNG, whose sha256 is `png_hash`, is still the bytes the Runner made for this key: its record's
    `result_hash` matches it. A record without one (older, or cut short between the two writes) says nothing, so it is
    not."""
    try:
        record = json.loads((asset_dir / PINNED_DIR / f"{pin}.json").read_text(encoding="utf-8"))
        made = record.get("result_hash") if isinstance(record, dict) else None
        return isinstance(made, str) and made == png_hash
    except (OSError, ValueError):
        return False
