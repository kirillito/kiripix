"""Where an export goes: the game's Godot project and the export root inside it."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from kiripix.core.errors import ExitCode, fail
from kiripix.core.project import Project
from kiripix.export.manifest import MANIFEST_DIR

RES = "res://"


@dataclass(frozen=True)
class GodotTarget:
    """The Godot project's folder, and the export root inside it as `res://...`."""

    folder: Path
    root: str

    def path(self, res: str) -> Path:
        return self.folder / res.removeprefix(RES)

    def manifest(self, asset_id: str) -> str:
        return f"{self.root}/{MANIFEST_DIR}/{asset_id}.json"


def resolve_target(project: Project) -> GodotTarget:
    godot = project.settings.export.godot
    if godot.project is None:
        raise fail("export.no_target", "no Godot project to export into",
                   owner_action="Set project under [export.godot] in kiripix.toml to the Godot project's folder.",
                   exit_code=ExitCode.NEEDS_OWNER)
    root = godot.root.rstrip("/")
    parts = PurePosixPath(root.removeprefix(RES)).parts
    if not root.startswith(RES) or not parts or ".." in parts:
        raise fail("export.bad_root", f"the export root '{godot.root}' isn't a folder inside the Godot project",
                   owner_action="Set root under [export.godot] in kiripix.toml to a folder such as res://kiripix.")
    folder = project.root / godot.project
    if not (folder / "project.godot").is_file():
        raise fail("export.no_project", f"no Godot project at '{godot.project}': it has no project.godot",
                   owner_action="Clone the game there, or fix project under [export.godot] in kiripix.toml.",
                   exit_code=ExitCode.NEEDS_OWNER)
    return GodotTarget(folder, root)
