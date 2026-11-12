"""The naming rule that places a ZIP's PNG in a clip, a direction and a frame (spec §6.4, tickets 0174 and 0179).

PROVISIONAL, pending ticket 0175 (the trial on a real PixelLab export). The rule is kept in this one module so that what the
trial finds changes only here:

- a path names a direction by a PixelLab word (`south`, `south-east`, ...) or by ours (`s`, `se`, ...), as a folder
  (`walk/south/frame_003.png`) or as the file's name (`rotations/south.png`, `idle/south-east_003.png`), in any case;
- the frame number is the last number of the file's name (`frame_003.png` is 3); a file with none is frame 0;
- the clip is the folder above the direction (or above the file, for a direction in the file's name), made snake_case; a
  folder that only holds clips (`animations`) or rotations (`rotations`) is not a clip, and a direction with no clip is a
  rotation, which is the clip `idle` of one frame.
"""

import re
from dataclasses import dataclass

from kiripix.recipes.clips import DIRECTIONS

# PixelLab's words for the 8 directions, as they read on the screen (its `south` faces the camera, as our `s` does).
PIXELLAB_WORDS = {"south": "s", "south-west": "sw", "west": "w", "north-west": "nw", "north": "n", "north-east": "ne",
                  "east": "e", "south-east": "se"}
WORDS = {**PIXELLAB_WORDS, **{d: d for d in DIRECTIONS}}
CONTAINERS = frozenset({"animations", "animation", "rotations", "rotation", "frames", "images", "sprites", "sprite"})
ROTATION_CLIP = "idle"  # the clip a direction with no animation joins

_SEPARATORS = re.compile(r"[\s_\-]+")
_WORD_THEN_NUMBER = re.compile(r"^(?P<word>[a-z]+(?:[-_ ][a-z]+)?)(?:[-_ ]?(?P<number>\d+))?$")
_LAST_NUMBER = re.compile(r"(\d+)(?!.*\d)")


@dataclass(frozen=True)
class Placed:
    """Where a ZIP entry goes: `animation` is the folder's own name (None for a rotation), `frame` the number it carries."""

    direction: str
    animation: str | None
    frame: int


def snake_case(name: str) -> str:
    """`Breathing Idle` and `breathing-idle` as `breathing_idle`."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "clip"


def direction_word(text: str) -> str | None:
    """Our direction for a PixelLab or Kiripix direction word, or None."""
    return WORDS.get(_SEPARATORS.sub("-", text.strip().lower()))


def _animation(folders: list[str]) -> str | None:
    """The animation a path belongs to: its innermost folder, unless that only holds clips or rotations."""
    if folders and folders[-1].strip().lower() not in CONTAINERS:
        return folders[-1]
    return None


def place(path: str) -> Placed | None:
    """Where the PNG at `path` in a ZIP goes, or None when the rule can't tell its direction."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if not parts:
        return None
    stem = re.sub(r"\.png$", "", parts[-1], flags=re.IGNORECASE)
    folders = parts[:-1]
    for depth in range(len(folders) - 1, -1, -1):  # a folder that names the direction, the innermost first
        direction = direction_word(folders[depth])
        if direction is not None:
            number = _LAST_NUMBER.search(stem)
            return Placed(direction, _animation(folders[:depth]), int(number.group(1)) if number else 0)
    found = _WORD_THEN_NUMBER.match(stem.lower())  # else the file's own name: `south`, `south-east_003`, `se3`
    if found is not None and (direction := direction_word(found.group("word"))) is not None:
        number_text = found.group("number")
        return Placed(direction, _animation(folders), int(number_text) if number_text else 0)
    return None
