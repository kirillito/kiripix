"""A frame Loop's edit frames (ticket 0219): `import --loop --frame` stores an edit of the Source as a Variant of a frame,
`pick --loop --frame` chooses it with the Source it was made on, and a new Source holds the Loop. Ticket 0220 builds the frames."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_layers_stage import ROOM, SCALE, target_image
from test_loop_kit import a_frame_loop, painted, write_kit
from test_loops import LOOP, decide
from test_looks_build import UNLIT, edited


def png(project: Kiripix, name: str, image: np.ndarray) -> str:
    Image.fromarray(np.repeat(np.repeat(image, SCALE, axis=0), SCALE, axis=1), "RGBA").save(project.cwd / name)
    return name


def edit_frame(project: Kiripix, name: str, image: np.ndarray, frame: int, expect: int = 0) -> dict[str, Any]:
    return project.json("import", ROOM, png(project, name, image), "--loop", LOOP, "--frame", str(frame), expect=expect)


def pick_frame(project: Kiripix, variant: str, frame: int, expect: int = 0) -> dict[str, Any]:
    return project.json("pick", ROOM, variant, "--loop", LOOP, "--frame", str(frame), expect=expect)


def touched() -> np.ndarray:
    """An edit that redraws a corner of the lamp too."""
    image = edited()
    image[8:10, 8:10] = UNLIT
    return image


def edits_loop(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    decide(project, "frames", {"loop": LOOP, "source": "edits"})


def held(project: Kiripix) -> str:
    """The reason the Loop is held, from `check`."""
    project("run", ROOM, "loops", "--json")  # exit 2 while the Loop is held
    found = [f for f in project("check", ROOM, "--json").json["findings"] if f["code"] == "loop.held"]
    return str(found[0]["message"]) if found else ""


def stored(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in (folder / "src" / "loops").glob("**/*.png"))


def test_two_edit_frames_are_imported_and_picked_and_a_new_source_holds_them(project: Kiripix) -> None:
    edits_loop(project)
    folder = project.cwd / "assets" / "room" / "alley"
    source = next(p.stem for p in (folder / "src").glob("*.png"))

    one = edit_frame(project, "one.png", edited(), 1)["data"]
    two = edit_frame(project, "two.png", touched(), 2)["data"]

    assert one["loop"] == LOOP and one["frame"] == 1 and one["created"] and one["variants"] == [one["variant"]]
    assert stored(folder) == [f"src/loops/{LOOP}/edits/1/{one['variant']}.png",
                              f"src/loops/{LOOP}/edits/2/{two['variant']}.png"]
    assert "no picked edit" in held(project)

    pick_frame(project, one["variant"], 1)
    assert held(project) == "", "one picked frame is a whole run of frames: the Loop is built"
    picked = pick_frame(project, two["variant"], 2)["data"]
    assert picked["loop"] == LOOP and picked["frame"] == 2 and picked["stage"] == "loops"

    entries = [json.loads(line) for line in (folder / "decisions" / "loops.jsonl").read_text("utf-8").splitlines()]
    picks = [e["data"] for e in entries if e["decision"] == "pick"]
    assert picks == [{"loop": LOOP, "frame": 1, "variant": one["variant"], "source": source},
                     {"loop": LOOP, "frame": 2, "variant": two["variant"], "source": source}]
    assert "another Source" not in held(project)

    other = project.json("import", ROOM, png(project, "other.png", np.roll(target_image(), 8, axis=1)))["data"]["variant"]
    project.json("pick", ROOM, other)
    for stage in ("source", "fit", "layers", "masks", "palette", "looks"):
        project.json("run", ROOM, stage)
    assert "another Source" in held(project)


def test_frame_zero_is_never_imported_or_picked(project: Kiripix) -> None:
    edits_loop(project)

    refused = edit_frame(project, "zero.png", edited(), 0, expect=1)["findings"][0]
    assert refused["code"] == "import.frame_zero" and refused["fix"]
    assert not list((project.cwd / "assets" / "room" / "alley" / "src").glob("loops/**/*.png"))
    assert pick_frame(project, "0123456789abcdef", 0, expect=1)["findings"][0]["code"] == "pick.frame_zero"


def test_an_edit_made_from_another_edit_is_reported_and_one_from_the_source_is_not(project: Kiripix) -> None:
    edits_loop(project)

    first = edit_frame(project, "one.png", edited(), 1)
    near = edit_frame(project, "two.png", touched(), 2)
    assert not [f for f in first["findings"] + near["findings"] if f["code"] == "import.edit_of_an_edit"]

    drifted = np.clip(edited().astype(int) + 40, 0, 255).astype(np.uint8)
    far = edit_frame(project, "three.png", drifted, 3)

    [found] = [f for f in far["findings"] if f["code"] == "import.edit_of_an_edit"]
    assert found["severity"] == "info" and "from the Source, not from another edit" in found["owner_action"]
    assert found.get("fix") is None
    assert far["ok"] is True


def test_edit_frames_and_a_kit_on_one_loop_are_refused(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), "--loop", LOOP)

    refused = edit_frame(project, "one.png", edited(), 1, expect=1)["findings"][0]
    assert refused["code"] == "import.loop_source_mixed" and refused["owner_action"]

    project.json("undo", ROOM, "loops")
    decide(project, "frames", {"loop": LOOP, "source": "edits"})
    variant = edit_frame(project, "one.png", edited(), 1)["data"]["variant"]
    pick_frame(project, variant, 1)
    again = project.json("import", ROOM, painted(project, 2), "--loop", LOOP, expect=1)["findings"][0]
    assert again["code"] == "import.loop_source_mixed"


def test_the_edit_arguments_are_checked(project: Kiripix) -> None:
    edits_loop(project)
    name = png(project, "one.png", edited())

    assert project.json("import", ROOM, name, "--frame", "1", expect=1)["findings"][0]["code"] == "import.frame_needs_loop"
    two = project.json("import", ROOM, name, name, "--loop", LOOP, "--frame", "1", expect=1)["findings"][0]
    assert two["code"] == "import.edit_takes_one_image"
    assert project.json("pick", ROOM, "0123456789abcdef", "--loop", LOOP, expect=1)["findings"][0]["code"] == "pick.loop_needs_frame"
    assert pick_frame(project, "0123456789abcdef", 1, expect=1)["findings"][0]["code"] == "pick.unknown_variant"


def test_next_names_the_import_of_a_missing_edit_frame(project: Kiripix) -> None:
    edits_loop(project)
    one = edit_frame(project, "one.png", edited(), 1)["data"]["variant"]
    pick_frame(project, one, 1)
    three = edit_frame(project, "three.png", touched(), 3)["data"]["variant"]
    pick_frame(project, three, 3)

    message = held(project)

    assert "frame 2 of" in message
    [found] = [f for f in project.json("check", ROOM, expect=2)["findings"] if f["code"] == "loop.held"]  # held() ran it
    assert f"--loop {LOOP} --frame 2" in found["owner_action"] and "import" in found["owner_action"]


def test_a_renamed_edit_frame_loop_keeps_its_picks(project: Kiripix) -> None:
    edits_loop(project)
    one = edit_frame(project, "one.png", edited(), 1)["data"]["variant"]
    two = edit_frame(project, "two.png", touched(), 2)["data"]["variant"]
    pick_frame(project, one, 1)

    decide(project, "rename", {"loop": LOOP, "to": "lantern"})

    assert held(project) == "", "the pick of frame 1 follows the rename"
    project.json("pick", ROOM, two, "--loop", "lantern", "--frame", "2")
    folder = project.cwd / "assets" / "room" / "alley"
    entries = [json.loads(line)["data"] for line in (folder / "decisions" / "loops.jsonl").read_text("utf-8").splitlines()
               if json.loads(line)["decision"] == "pick"]
    assert entries[1]["loop"] == "lantern" and entries[1]["was"] == LOOP, "found under the Loop's first ID"
    assert held(project) == "", "both frames are picked, found under the old ID"
    project.json("undo", ROOM, "loops")
    project.json("undo", ROOM, "loops")
    assert held(project) == ""


def test_picked_edit_frames_under_a_frames_decision_of_another_source_hold_the_loop(project: Kiripix) -> None:
    edits_loop(project)
    variant = edit_frame(project, "one.png", edited(), 1)["data"]["variant"]
    pick_frame(project, variant, 1)
    assert held(project) == ""

    decide(project, "frames", {"loop": LOOP, "source": "op", "op": "shimmer"})

    assert "one source only" in held(project)


def test_the_fix_for_a_frame_zero_pick_names_the_variant_and_the_loop(project: Kiripix) -> None:
    edits_loop(project)
    refused = pick_frame(project, "0123456789abcdef", 0, expect=1)["findings"][0]
    assert refused["fix"] == f"kiripix pick {ROOM} 0123456789abcdef --loop {LOOP} --frame 1"
