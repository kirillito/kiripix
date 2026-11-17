"""`kiripix extend` (ticket 0136): the canvas for the next piece, joining a piece, `undo` and `done`, on a synthetic scene
cut into overlapping pieces the way an image model's pieces overlap."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image

ROOM = "room.alley"
CANVAS = (240, 160)  # a small canvas for speed; the strips are 80 px (a third is 80 along x, 53 along y)


def scene() -> Any:
    """A blocky random scene (4 px blocks), 400 wide and 240 tall: textured everywhere, so edge patches register."""
    rng = np.random.default_rng(11)
    return np.kron(rng.integers(0, 256, (60, 100, 3), dtype=np.uint8), np.ones((4, 4, 1), dtype=np.uint8))


def save(project: Kiripix, name: str, pixels: Any) -> str:
    Image.fromarray(pixels, "RGB").save(project.cwd / name)
    return name


def room(project: Kiripix) -> Any:
    """A room whose picked Source is the scene's top-left canvas, and a small `[extend] canvas`."""
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("canvas = [1376, 768]", f"canvas = {list(CANVAS)}"),
                    encoding="utf-8")
    project.json("new", "room", "alley", "--view", "top")
    full = scene()
    variant = project.json("import", ROOM, save(project, "first.png", full[:160, :240]))["data"]["variant"]
    project.json("pick", ROOM, variant)
    return full


def canvas(project: Kiripix, side: str, *extra: str) -> dict[str, Any]:
    data: dict[str, Any] = project.json("extend", ROOM, "canvas", "--side", side, *extra)["data"]
    return data


def size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def test_canvas_keeps_the_strip_and_fills_the_rest(project: Kiripix) -> None:
    full = room(project)

    data = canvas(project, "east", "--keep", "80")

    path = project.cwd / data["canvas"]
    assert size(path) == CANVAS and data["keep"] == [80, 80] and data["sides"] == ["east"]
    pixels = np.asarray(Image.open(path).convert("RGBA"))
    assert (pixels[:, :80, :3] == full[:160, 160:240]).all()  # the base's last 80 columns
    fill = tuple(int(data["fill"][i : i + 2], 16) for i in (1, 3, 5))
    assert (pixels[:, 80:] == (*fill, 255)).all()  # the flat fill, as the result names it


def flat_room(project: Kiripix, colour: tuple[int, int, int]) -> None:
    """A room whose picked Source is one flat colour, with a little noise so it isn't exactly flat."""
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("canvas = [1376, 768]", f"canvas = {list(CANVAS)}"),
                    encoding="utf-8")
    project.json("new", "room", "alley", "--view", "top")
    noise = np.random.default_rng(3).integers(-6, 7, (160, 240, 3))
    pixels = np.clip(np.array(colour) + noise, 0, 255).astype(np.uint8)
    project.json("pick", ROOM, project.json("import", ROOM, save(project, "flat.png", pixels))["data"]["variant"])


def test_the_fill_is_red_where_the_strip_is_grey_asphalt(project: Kiripix) -> None:
    flat_room(project, (128, 126, 122))

    assert canvas(project, "east")["fill"] == "#ED1C24"


def test_the_fill_avoids_a_colour_the_strip_has(project: Kiripix) -> None:
    flat_room(project, (237, 28, 36))

    fill = canvas(project, "east")["fill"]

    assert fill != "#ED1C24" and fill in ("#FF00FF", "#00FF00", "#0000FF", "#00FFFF", "#FFFF00")


def test_the_default_strip_is_a_third_of_the_canvas(project: Kiripix) -> None:
    room(project)

    assert canvas(project, "east")["keep"] == [80, 53]
    assert canvas(project, "south")["keep"] == [80, 53]


def test_a_canvas_east_then_south_then_the_corner_makes_one_variant_of_the_expected_size(project: Kiripix) -> None:
    full = room(project)

    canvas(project, "east", "--keep", "80")
    east = project.json("extend", ROOM, "add", save(project, "east.png", full[:160, 160:400]))
    assert east["ok"] and (east["data"]["width"], east["data"]["height"]) == (400, 160)
    assert east["data"]["residual"] <= 0.5 and east["data"]["pieces"] == 1

    canvas(project, "south", "--keep", "80")
    south = project.json("extend", ROOM, "add", save(project, "south.png", full[80:240, :240]))
    assert (south["data"]["width"], south["data"]["height"]) == (400, 240) and south["data"]["pieces"] == 2

    canvas(project, "east,south", "--keep", "80")
    corner = project.json("extend", ROOM, "add", save(project, "corner.png", full[80:240, 160:400]))
    assert corner["data"]["sides"] == ["east", "south"]
    assert (corner["data"]["width"], corner["data"]["height"]) == (400, 240) and corner["data"]["pieces"] == 3

    done = project.json("extend", ROOM, "done")["data"]
    assert (done["width"], done["height"], done["transparent_pixels"]) == (400, 240, 0)
    variants = project.json("show", ROOM)["data"]
    assert done["variant"] in json.dumps(variants)
    stored = project.cwd / "assets" / "room" / "alley" / "src" / f"{done['variant']}.png"
    joined = np.asarray(Image.open(stored).convert("RGB"), dtype=np.int64)
    assert joined.shape == (240, 400, 3)
    assert np.abs(joined - full.astype(np.int64)).mean() < 2  # the scene, with seams that cut through equal pixels
    assert project.json("pick", ROOM, done["variant"])["ok"]


def east_and_south(project: Kiripix, full: Any, east_rows: int = 160) -> None:
    canvas(project, "east", "--keep", "80")
    project.json("extend", ROOM, "add", save(project, "east.png", full[:east_rows, 160:400]))
    canvas(project, "south", "--keep", "80")
    project.json("extend", ROOM, "add", save(project, "south.png", full[80:240, :240]))


def test_a_corner_whose_east_piece_is_a_row_short_joins_and_done_crops_the_open_row(project: Kiripix) -> None:
    full = room(project)
    east_and_south(project, full, east_rows=159)  # the notch's top is a row higher than the original's bottom

    data = canvas(project, "east,south", "--keep", "80")
    record = json.loads((project.cwd / "assets" / "room" / "alley" / "extend" / "canvas.json").read_text(encoding="utf-8"))
    assert record["origin"] == [160, 79]  # the notch as it is: 79 = 159 - 80
    assert size(project.cwd / data["canvas"]) == CANVAS
    corner = project.json("extend", ROOM, "add", save(project, "corner.png", full[79:239, 160:400]))  # ends 1 row up

    assert corner["ok"] and (corner["data"]["width"], corner["data"]["height"]) == (400, 240)
    done = project.json("extend", ROOM, "done")
    assert (done["data"]["width"], done["data"]["height"], done["data"]["transparent_pixels"]) == (400, 239, 0)
    assert done["data"]["cropped"] == {"south": 1}
    assert not done["findings"]


def rescaled(full: Any, scale: float, x: int, y: int, size: tuple[int, int]) -> Any:
    """The picture from (x, y) at `scale` base px per piece px: what an image model returns when it rescales a piece."""
    image = Image.fromarray(full, "RGB")
    return np.asarray(image.transform(size, Image.Transform.AFFINE, (scale, 0, x, 0, scale, y), Image.Resampling.BILINEAR))


def test_a_corner_piece_rescaled_to_end_inside_the_image_joins_at_the_image_size(project: Kiripix) -> None:
    full = room(project)
    east_and_south(project, full)
    canvas(project, "east,south", "--keep", "80")
    piece = rescaled(full, 0.999, 160, 80, CANVAS)  # 239.76 x 159.84 base px: ends inside the image on both axes

    corner = project.json("extend", ROOM, "add", save(project, "corner.png", piece))

    assert corner["ok"], corner["findings"]
    assert (corner["data"]["width"], corner["data"]["height"]) == (400, 240)
    done = project.json("extend", ROOM, "done")["data"]
    assert done["transparent_pixels"] == 0
    assert (done["width"], done["height"]) == (400 - done["cropped"].get("east", 0), 240 - done["cropped"].get("south", 0))


def test_done_keeps_an_open_corner_and_does_not_crop_it(project: Kiripix) -> None:
    full = room(project)
    east_and_south(project, full)

    done = project.json("extend", ROOM, "done")

    assert (done["data"]["width"], done["data"]["height"]) == (400, 240) and done["data"]["cropped"] == {}
    assert done["data"]["transparent_pixels"] == 160 * 80
    assert done["findings"][0]["code"] == "extend.holes_remain"


def test_keep_per_axis_on_a_corner_writes_both_strips(project: Kiripix) -> None:
    full = room(project)
    east_and_south(project, full)

    data = canvas(project, "east,south", "--keep", "80,40")

    assert data["keep"] == [80, 40]
    record = json.loads((project.cwd / "assets" / "room" / "alley" / "extend" / "canvas.json").read_text(encoding="utf-8"))
    assert record["keep"] == [80, 40] and record["origin"] == [160, 120]
    pixels = np.asarray(Image.open(project.cwd / data["canvas"]).convert("RGBA"))
    assert (pixels[:40, :, :3] == full[120:160, 160:400]).all()  # 40 rows kept above the notch
    assert (pixels[40:120, :80, :3] == full[160:240, 160:240]).all()  # 80 columns kept beside it, to the image's end
    fill = (*(int(data["fill"][i : i + 2], 16) for i in (1, 3, 5)), 255)
    assert (pixels[40:, 80:] == fill).all() and (pixels[120:] == fill).all()


def test_keep_per_axis_on_one_side_uses_the_axis_across_the_join(project: Kiripix) -> None:
    full = room(project)

    east = canvas(project, "east", "--keep", "60,500")  # down doesn't fit, but an east canvas doesn't use it
    assert east["keep"] == [60, 500]
    pixels = np.asarray(Image.open(project.cwd / east["canvas"]).convert("RGBA"))
    assert (pixels[:, :60, :3] == full[:160, 180:240]).all()
    south = canvas(project, "south", "--keep", "500,40")
    pixels = np.asarray(Image.open(project.cwd / south["canvas"]).convert("RGBA"))
    assert (pixels[:40, :, :3] == full[120:160, :240]).all()


def test_a_keep_that_does_not_fit_names_its_axis(project: Kiripix) -> None:
    room(project)

    down = project.json("extend", ROOM, "canvas", "--side", "east,south", "--keep", "80,160", expect=1)["findings"][0]
    assert down["code"] == "extend.keep_invalid" and "down" in down["message"] and "across" not in down["message"]
    across = project.json("extend", ROOM, "canvas", "--side", "east", "--keep", "240,10", expect=1)["findings"][0]
    assert across["code"] == "extend.keep_invalid" and "across" in across["message"]
    for text in ("80,", "a", "1,2,3", "0", "0,10"):
        finding = project.json("extend", ROOM, "canvas", "--side", "east", "--keep", text, expect=1)["findings"][0]
        assert finding["code"] == "extend.keep_invalid", text


def test_undo_drops_the_last_piece(project: Kiripix) -> None:
    full = room(project)
    canvas(project, "east", "--keep", "80")
    project.json("extend", ROOM, "add", save(project, "east.png", full[:160, 160:400]))
    canvas(project, "south", "--keep", "80")
    project.json("extend", ROOM, "add", save(project, "south.png", full[80:240, :240]))

    undone = project.json("extend", ROOM, "undo")["data"]

    assert undone["pieces"] == 1
    again = canvas(project, "south", "--keep", "80")  # the canvas is of the east-joined image again
    assert size(project.cwd / again["canvas"]) == CANVAS
    done = project.json("extend", ROOM, "done")["data"]
    assert (done["width"], done["height"]) == (400, 160)
    lines = (project.cwd / "assets" / "room" / "alley" / "extend" / "journal.jsonl").read_text(encoding="utf-8")
    assert [json.loads(line)["action"] for line in lines.splitlines()] == ["add", "add", "undo", "done"]
    assert "\r" not in lines


def test_undo_with_no_piece_is_a_finding(project: Kiripix) -> None:
    room(project)

    finding = project.json("extend", ROOM, "undo", expect=1)["findings"][0]

    assert finding["code"] == "extend.nothing_to_undo" and finding["owner_action"] and not finding["fix"]


def test_a_piece_that_does_not_register_records_nothing_and_gives_a_variant_of_nothing(project: Kiripix) -> None:
    room(project)
    canvas(project, "east", "--keep", "80")
    noise = np.random.default_rng(99).integers(0, 256, (160, 240, 3), dtype=np.uint8)

    result = project.json("extend", ROOM, "add", save(project, "noise.png", noise), expect=2)

    finding = result["findings"][0]
    assert finding["code"] == "extend.registration_missed"
    assert "wider strip" in finding["owner_action"] and not finding["fix"]
    assert not (project.cwd / "assets" / "room" / "alley" / "extend" / "journal.jsonl").exists()
    done = project.json("extend", ROOM, "done", expect=1)["findings"][0]
    assert done["code"] == "extend.nothing_to_join"
    assert len(project.json("show", ROOM)["data"]["variants"]) == 1


def test_add_needs_a_canvas_that_matches(project: Kiripix) -> None:
    full = room(project)
    piece = save(project, "east.png", full[:160, 160:400])

    assert project.json("extend", ROOM, "add", piece, expect=1)["findings"][0]["code"] == "extend.canvas_needed"
    canvas(project, "east", "--keep", "80")
    mismatch = project.json("extend", ROOM, "add", piece, "--side", "south", expect=1)["findings"][0]
    assert mismatch["code"] == "extend.canvas_mismatch" and mismatch["fix"].endswith("--side south")
    project.json("extend", ROOM, "add", piece)
    stale = project.json("extend", ROOM, "add", piece, expect=1)["findings"][0]
    assert stale["code"] == "extend.canvas_stale"


def test_bad_arguments_are_findings(project: Kiripix) -> None:
    room(project)

    assert project.json("extend", ROOM, "canvas", "--side", "up", expect=1)["findings"][0]["code"] == "extend.side_invalid"
    assert project.json("extend", ROOM, "canvas", "--side", "east,west", expect=1)["findings"][0]["code"] == "extend.side_invalid"
    assert project.json("extend", ROOM, "canvas", expect=1)["findings"][0]["code"] == "extend.side_needed"
    assert project.json("extend", ROOM, "canvas", "--side", "east", "--keep", "240", expect=1)["findings"][0]["code"] == "extend.keep_invalid"
    assert project.json("extend", ROOM, "add", expect=1)["findings"][0]["code"] == "extend.piece_needed"


def test_the_first_canvas_needs_a_picked_source(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")

    first = project.json("extend", ROOM, "canvas", "--side", "east", expect=1)["findings"][0]
    assert first["code"] == "extend.no_source" and first["owner_action"] and not first["fix"]
    variant = project.json("import", ROOM, save(project, "a.png", scene()[:160, :240]))["data"]["variant"]
    second = project.json("extend", ROOM, "canvas", "--side", "east", expect=1)["findings"][0]
    assert second["code"] == "extend.no_source" and second["fix"] == f"kiripix pick {ROOM} {variant}"
