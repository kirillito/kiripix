"""The Project on disk (spec §4): finding it, and creating it with `init`."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from kiripix.core import atomic
from kiripix.core.errors import fail
from kiripix.core.settings import ProjectSettings, load_project_settings

PROJECT_FILE = "kiripix.toml"
STATE_DIR = ".kiripix"


@dataclass(frozen=True)
class Project:
    root: Path
    settings: ProjectSettings

    @property
    def state_dir(self) -> Path:
        """The git-ignored cache: hashes, failures, locks. Deleting it loses nothing."""
        return self.root / STATE_DIR

    def relative(self, path: Path) -> str:
        try:
            if path.is_absolute() and ".." not in path.parts:  # the usual case: no filesystem walk (`resolve` is slow)
                text, root = str(path), str(self.root)
                if text.startswith(root + os.sep):
                    return text[len(root) + 1:].replace(os.sep, "/")
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()


def find_root(start: Path) -> Path | None:
    for directory in (start.resolve(), *start.resolve().parents):
        if (directory / PROJECT_FILE).is_file():
            return directory
    return None


def find_project(start: Path) -> Project:
    """The Project containing `start`, with its settings read (and migrated in memory)."""
    root = find_root(start)
    if root is None:
        raise fail(
            "project.not_found",
            f"no {PROJECT_FILE} in {start.resolve()} or any folder above it",
            fix="kiripix init",
        )
    return Project(root, load_project_settings(root / PROJECT_FILE))


PROJECT_TEMPLATE = """schema_version = 4

[project]
name = "{name}"
resolution = [640, 360]        # internal resolution
tile = 16
palette = "style/palette.gpl"

[body]                         # the stand-in player for walkable, reachability and walk tests
size = [12, 8]                 # feet footprint in px
dash = 0                       # the widest pit it can dash over, px (0: none)

[masks.top]                    # Masks for top-down rooms; colours are for display and import only
solid      = {{ colour = "#FF0000", meaning = "blocks movement" }}
pit        = {{ colour = "#0000FF", meaning = "no walking on it, but the Body can dash over it" }}
walkable   = {{ derived = true }}   # where the Body's footprint fits without touching solid or a pit
foreground = {{ derived = true }}   # the union of the foreground Layers' alpha

[masks.top.import]             # extra colours accepted from a single painted image
"#FFFF00" = ["solid"]

[masks.side]                   # Masks for side-view rooms
solid      = {{ colour = "#FF0000" }}
oneway     = {{ colour = "#00FFFF", meaning = "platform passable from below" }}
ladder     = {{ colour = "#00FF00" }}
foreground = {{ derived = true }}

[export.godot]
# project = "C:/Workspace/my-game"   # the Godot project to export into
root = "res://kiripix"         # everything Kiripix writes goes under here, Manifest included
version = "4.7"                # the pinned Godot version (docs/versions.md in Kiripix)

[character]
height = 52                    # target height in px; a character's own `height` parameter overrides it
# blender = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"   # otherwise found on PATH

[character.camera.top34_8]     # a camera preset, picked by name by a character's `camera` parameter
elevation = 30                 # degrees above the ground plane
directions = 8
light_angle = -45              # the toon key light: degrees round the view from the top, -45 = upper left
light_tilt = 35                # and toward the camera

# The ramp table: the same part names, ramp lengths and ramps.png rows on every character. Add rows with `kiripix ramps-add`.
# [[character.ramps]]
# name = "skin"                # a part name, lower-case snake_case
# length = 3                   # steps, at least 2
# rgb = [[171, 82, 54], [255, 163, 0], [255, 241, 232]]   # optional: shared colours, dark to light, of the Project palette

[providers]
default = "import"             # import | openai | gemini | pixellab | local-sd
budget_usd_month = 20          # hard cap; calls fail beyond it
"""

DEFAULT_PALETTE = """GIMP Palette
Name: Kiripix default
#
  0   0   0\tblack
 29  43  83\tnight
 95  87  79\tstone
131 118 156\tdusk
194 195 199\tmist
255 241 232\tpaper
126  37  83\twine
255   0  77\tred
171  82  54\trust
255 163   0\tamber
255 236  39\tyellow
  0 135  81\tleaf
  0 228  54\tlime
 41 173 255\tsky
255 119 168\tpink
255 204 170\tskin
"""

STYLE_BIBLE = """# Style bible

Style notes for this project. Prompt templates read this file.
"""

GITATTRIBUTES = [
    "*.png filter=lfs diff=lfs merge=lfs -text",
    "*.glb filter=lfs diff=lfs merge=lfs -text",
    "*.fbx filter=lfs diff=lfs merge=lfs -text",
    "*.blend filter=lfs diff=lfs merge=lfs -text",
    "history.jsonl merge=union text eol=lf",
    "**/decisions/*.jsonl merge=union text eol=lf",
    "imported.jsonl merge=union text eol=lf",
]

GITIGNORE = ["work/", ".kiripix/", ".env"]


def _merge_lines(path: Path, lines: list[str]) -> bool:
    """Add the missing lines to a text file, keeping what is there. True if the file changed."""
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [line for line in lines if line not in existing]
    if not missing:
        return False
    atomic.write_text(path, "\n".join([*existing, *missing]) + "\n")
    return True


def _project_name(directory: Path) -> str:
    name = re.sub(r"[^a-z0-9_-]+", "-", directory.name.lower()).strip("-")
    return name or "kiripix-project"


def init_project(directory: Path) -> list[str]:
    """Create the documented layout in `directory`. Refuses a folder that already holds a Project."""
    directory = directory.resolve()
    if (directory / PROJECT_FILE).exists():
        raise fail(
            "project.exists",
            f"{directory} already has a {PROJECT_FILE}; init never overwrites a Project",
            fix="kiripix status",
        )
    created: list[str] = []

    def write(relative: str, text: str) -> None:
        atomic.write_text(directory / relative, text)
        created.append(relative)

    write(PROJECT_FILE, PROJECT_TEMPLATE.format(name=_project_name(directory)))
    for relative, text in [("style/palette.gpl", DEFAULT_PALETTE), ("style/bible.md", STYLE_BIBLE)]:
        if not (directory / relative).exists():
            write(relative, text)
    for keep in ["style/refs/.gitkeep", "style/prompts/.gitkeep", "assets/.gitkeep"]:
        if not (directory / keep).parent.exists():
            write(keep, "")
    for relative, lines in [(".gitattributes", GITATTRIBUTES), (".gitignore", GITIGNORE)]:
        if _merge_lines(directory / relative, lines):
            created.append(relative)
    return created
