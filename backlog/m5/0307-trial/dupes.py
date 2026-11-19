"""0307 trial, lever D: identical frames (colour and normal both), per clip and over the atlas. Writes dupes.json."""
import json, sys
from common import *
from lib import *

res = {}
suffixes = sys.argv[1:] or [""]
for a in BODIES:
    for suf in suffixes:
        name = a + suf
        asset, cell, _ = load_asset(PROJ / "assets/character" / name)
        seen_global = {}
        clips = {}
        total = 0
        for clip, c in asset.items():
            n = len(c["frames"]["s"])
            within = 0
            shared_other_clip = 0
            for d in EIGHT:
                keys = [frame_key(*f) for f in c["frames"][d]]
                within += len(keys) - len(set(keys))
                for k in set(keys):
                    if k in seen_global and seen_global[k] != clip:
                        shared_other_clip += 1
                    seen_global.setdefault(k, clip)
            clips[clip] = {"frames": n, "cells": n * 8, "duplicate_within_clip_direction": within, "also_in_an_earlier_clip": shared_other_clip}
            total += n * 8
        res[name] = {"cells": total, "unique": len(seen_global), "duplicates": total - len(seen_global), "clips": clips}
        print(name, total, len(seen_global), {k: (v["cells"], v["duplicate_within_clip_direction"], v["also_in_an_earlier_clip"]) for k, v in clips.items() if v["duplicate_within_clip_direction"] or v["also_in_an_earlier_clip"]})
(HERE / "dupes.json").write_text(json.dumps(res, indent=1))
