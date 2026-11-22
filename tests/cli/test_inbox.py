"""`kiripix inbox` (ticket 0350): the images the Owner made, filed by their file names."""

from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image

ALLEY = "room.alley"
CANVAS = (240, 160)  # a small `[extend] canvas`, for speed


def scene() -> Any:
    """A blocky random scene, 400 wide and 240 tall: textured everywhere, so a piece registers."""
    rng = np.random.default_rng(11)
    return np.kron(rng.integers(0, 256, (60, 100, 3), dtype=np.uint8), np.ones((4, 4, 1), dtype=np.uint8))


def save(path: Path, pixels: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels, "RGB").save(path)
    return path


def alley(project: Kiripix) -> Any:
    """room.alley, picked on the scene's top-left canvas: mid-`extend`, with no canvas written."""
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("canvas = [1376, 768]", f"canvas = {list(CANVAS)}"),
                    encoding="utf-8")
    project.json("new", "room", "alley", "--view", "top")
    full = scene()
    variant = project.json("import", ALLEY, save(project.cwd / "first.png", full[:160, :240]))["data"]["variant"]
    project.json("pick", ALLEY, variant)
    return full


def by_file(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {Path(f["file"]).name: f for f in data["files"]}


def test_an_inbox_of_a_room_a_side_piece_an_unmatched_and_an_ambiguous_file(project: Kiripix) -> None:
    full = alley(project)
    project.json("new", "room", "cellar", "--view", "top")
    project.json("new", "room", "crate", "--view", "top")
    project.json("new", "prop", "crate")
    inbox = project.cwd / "inbox"
    save(inbox / "alley.east.png", full[:160, 160:400])
    save(inbox / "cellar.png", full[:100, :100])
    save(inbox / "crate.png", full[:50, :50])
    save(inbox / "nothing.png", full[:50, :60])

    first = project.json("inbox")

    files = by_file(first["data"])
    assert first["ok"] and first["data"]["imported"] == 2 and first["data"]["left"] == 2
    assert files["alley.east.png"]["outcome"] == "imported" and files["alley.east.png"]["action"] == "extend"
    assert files["alley.east.png"]["asset"] == ALLEY and files["alley.east.png"]["sides"] == ["east"]
    assert files["cellar.png"]["asset"] == "room.cellar" and files["cellar.png"]["variant"]
    assert files["nothing.png"]["outcome"] == "unmatched" and files["crate.png"]["outcome"] == "ambiguous"
    assert sorted(files["crate.png"]["candidates"]) == ["prop.crate", "room.crate"]
    assert sorted(f["code"] for f in first["findings"]) == ["inbox.ambiguous", "inbox.unmatched"]
    assert all(f["owner_action"] and not f.get("fix") for f in first["findings"])
    assert sorted(p.name for p in inbox.glob("*.png")) == ["crate.png", "nothing.png"]  # the two imports moved
    moved = list((inbox / "imported").glob("*/*.png"))
    assert sorted(p.name for p in moved) == ["alley.east.png", "cellar.png"]
    assert (project.json("extend", ALLEY, "undo")["data"]["pieces"]) == 0  # the piece was live: one, now none

    second = project.json("inbox")

    assert second["data"]["imported"] == 0 and second["data"]["left"] == 2


def test_no_pick_is_made_and_a_lone_variant_is_named_with_its_pick_command(project: Kiripix) -> None:
    full = alley(project)
    project.json("new", "room", "cellar", "--view", "top")
    save(project.cwd / "inbox" / "room.cellar-take2.jpg", full[:100, :100])
    project.json("new", "room", "attic", "--view", "top")
    save(project.cwd / "inbox" / "attic.png", full[:100, :100])
    save(project.cwd / "inbox" / "attic-b.png", full[:90, :90])

    data = project.json("inbox")["data"]

    assert data["imported"] == 3
    lone = {entry["asset"]: entry for entry in data["lone_variants"]}
    assert set(lone) == {"room.cellar"}  # two Variants are no lone one
    variant = lone["room.cellar"]["variant"]
    assert lone["room.cellar"]["pick"] == f"kiripix pick room.cellar {variant}"
    assert project.json("pick", "room.cellar", variant)["ok"]
    shown = project.json("show", "room.attic")["data"]
    assert [s["status"] for s in shown["stages"] if s["stage"] == "source"] != ["done"]


def test_dry_run_lists_what_would_happen_and_changes_nothing(project: Kiripix) -> None:
    full = alley(project)
    inbox = project.cwd / "inbox"
    save(inbox / "alley.east.png", full[:160, 160:400])
    save(inbox / "nothing.png", full[:50, :60])

    data = project.json("inbox", "--dry-run")["data"]

    files = by_file(data)
    assert data["dry_run"] and data["imported"] == 1 and files["alley.east.png"]["outcome"] == "would_import"
    assert files["nothing.png"]["outcome"] == "unmatched"
    assert sorted(p.name for p in inbox.glob("*.png")) == ["alley.east.png", "nothing.png"]
    assert not (inbox / "imported").exists()
    assert project.json("extend", ALLEY, "canvas", "--side", "east")["data"]["pieces"] == 0  # no piece was joined


def test_a_piece_that_does_not_register_stays_in_the_folder_with_the_commands_finding(project: Kiripix) -> None:
    alley(project)
    flat = np.full((160, 240, 3), 90, dtype=np.uint8)
    save(project.cwd / "inbox" / "alley.east.png", flat)

    result = project.json("inbox", expect=2)

    assert not result["ok"] and by_file(result["data"])["alley.east.png"]["outcome"] == "failed"
    assert "extend.registration_missed" in [f["code"] for f in result["findings"]]
    assert (project.cwd / "inbox" / "alley.east.png").is_file()


def test_the_folder_is_the_settings_or_the_flag(project: Kiripix) -> None:
    full = alley(project)
    project.json("new", "room", "cellar", "--view", "top")
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('folder = "inbox"', 'folder = "from-the-model"'), encoding="utf-8")
    save(project.cwd / "from-the-model" / "cellar.png", full[:100, :100])
    save(project.cwd / "elsewhere" / "alley.png", full[:100, :100])

    assert project.json("inbox")["data"]["imported"] == 1
    assert project.json("inbox", "--folder", "elsewhere")["data"]["imported"] == 1
    assert project.json("inbox")["data"]["files"] == []  # an empty or missing folder is nothing to do


def test_an_old_settings_file_migrates_in_memory_and_gains_the_inbox_section(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    assert "schema_version = 12" in text and '[inbox]' in text
    block = text[text.index("[inbox]"):].split("\n\n", 1)[0]
    old = text.replace("schema_version = 12", "schema_version = 9").replace(block + "\n\n", "")
    assert "[inbox]" not in old
    path.write_text(old, encoding="utf-8")

    assert project.json("status")["ok"]
    assert project.json("inbox")["ok"]
    assert path.read_text(encoding="utf-8") == old  # migrated in memory only

    path.write_text(old.replace("schema_version = 9", "schema_version = 12") + '[inbox]\nfolder = "x"\nextra = 1\n', encoding="utf-8")
    assert project.json("status", expect=1)["findings"]  # an unknown key is an error


def test_one_file_is_filed_into_the_named_asset_whatever_its_name(project: Kiripix) -> None:  # the UI's drop (0351)
    full = alley(project)
    project.json("new", "room", "cellar", "--view", "top")
    piece = save(project.cwd / "dropped" / "whatever.png", full[:160, 160:400])
    image = save(project.cwd / "dropped" / "other.png", full[:100, :100])

    joined = project.json("inbox", "--file", str(piece), "--asset", ALLEY, "--sides", "east")["data"]
    imported = project.json("inbox", "--file", str(image), "--asset", "room.cellar")["data"]

    [filed] = joined["files"]
    assert filed["action"] == "extend" and filed["sides"] == ["east"] and filed["outcome"] == "imported"
    assert (imported["files"][0]["action"], imported["files"][0]["asset"]) == ("import", "room.cellar")
    assert [lone["asset"] for lone in imported["lone_variants"]] == ["room.cellar"]
    assert piece.is_file() and image.is_file()  # the file is the Owner's: it isn't moved
    assert project.json("extend", ALLEY, "undo")["data"]["pieces"] == 0
    project.json("inbox", "--asset", ALLEY, expect=1)  # --asset goes with --file
