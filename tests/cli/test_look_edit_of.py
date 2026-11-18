"""`import --look <look> --of <piece|crop>` and `extend <room> crop` (ticket 0232): an edit made on one piece, or on a crop
of the Source at the image model's size, is placed on the Source and stored as an edit of the whole Source."""

from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image

ROOM = "room.alley"
CANVAS = (480, 288)
PAINT = (250, 10, 200)
LOOK = "lamp_off"


def scene() -> Any:
    """A blocky random scene (4 px blocks), 900 x 560: textured everywhere, so tiles register."""
    rng = np.random.default_rng(5)
    return np.kron(rng.integers(0, 256, (140, 225, 3), dtype=np.uint8), np.ones((4, 4, 1), dtype=np.uint8))


def save(project: Kiripix, name: str, pixels: Any) -> str:
    Image.fromarray(pixels, "RGB").save(project.cwd / name)
    return name


def room(project: Kiripix, source: Any) -> None:
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text(encoding="utf-8").replace("canvas = [1376, 768]", f"canvas = {list(CANVAS)}"),
                    encoding="utf-8")
    project.json("new", "room", "alley", "--view", "top")
    project.json("pick", ROOM, project.json("import", ROOM, save(project, "first.png", source))["data"]["variant"])


def stored(project: Kiripix, data: dict[str, Any]) -> Any:
    return np.asarray(Image.open(project.cwd / data["file"]).convert("RGB"))


def painted(image: Any, box: tuple[int, int, int, int]) -> Any:
    image = image.copy()
    image[box[1]:box[3], box[0]:box[2]] = PAINT
    return image


def only_inside(stored_image: Any, original: Any, box: tuple[int, int, int, int]) -> None:
    """Every pixel outside `box` is the room's."""
    outside = np.ones(original.shape[:2], dtype=bool)
    outside[box[1]:box[3], box[0]:box[2]] = False
    assert (stored_image[outside] == original[outside]).all()


def test_a_crop_is_written_at_the_asked_size_and_its_edit_comes_back_to_the_same_place(project: Kiripix) -> None:
    full = scene()
    source = full[:400, :700]
    room(project, source)

    written = project.json("extend", ROOM, "crop", "--box", "400,50,600,200")["data"]

    path = project.cwd / written["crop"]
    # Centred on the box, moved in: x would be 260 but the Source ends at 700; y would be -19.
    assert written["canvas_size"] == [480, 288] and written["origin"] == [220, 0]
    assert "/extend/crops/" in written["crop"] and written["crop"].endswith(".png")
    crop = np.asarray(Image.open(path).convert("RGB"))
    assert (crop == source[0:288, 220:700]).all()

    # The model hands the crop back a pixel or two shifted, with a patch redrawn.
    shifted = full[1:1 + 288, 222:222 + 480]
    edit = painted(shifted, (200, 100, 260, 140))
    data = project.json("import", ROOM, save(project, "edit.png", edit), "--look", LOOK, "--of", "crop")
    result = data["data"]

    assert result["of"] == "crop" and result["registration_residual"] < 1.0 and result["created"]
    assert result["placed_at"] == [222, 1] and result["placed_scale"] == [1.0, 1.0]
    out = stored(project, result)
    assert out.shape == source.shape
    # The painted patch lies at (200..260, 100..140) of the edit, so at (422.., 101..) of the Source.
    box = (222 + 200, 1 + 100, 222 + 260, 1 + 140)
    assert (out[box[1]:box[3], box[0]:box[2]] == PAINT).all()
    only_inside(out, source, box)
    assert project.json("pick", ROOM, result["variant"], "--look", LOOK)["ok"]


def test_an_edit_of_a_scaled_piece_gives_a_look_that_is_the_rooms_outside_the_edit(project: Kiripix) -> None:
    full = scene()
    room(project, full[:288, :480])
    project.json("extend", ROOM, "canvas", "--side", "east", "--keep", "160")
    scale = 1.01  # the model rescaled the piece: a Source px per piece px
    piece = np.asarray(Image.fromarray(full, "RGB").transform(
        CANVAS, Image.Transform.AFFINE, (scale, 0, 320, 0, scale, 0), Image.Resampling.BILINEAR))
    added = project.json("extend", ROOM, "add", save(project, "piece.png", piece))["data"]
    done = project.json("extend", ROOM, "done")["data"]
    project.json("pick", ROOM, done["variant"])
    source = np.asarray(Image.open(project.cwd / "assets" / "room" / "alley" / "src" / f"{done['variant']}.png").convert("RGB"))

    box = (180, 100, 260, 160)  # in the piece's px
    edit = painted(piece, box)
    result = project.json("import", ROOM, save(project, "edit.png", edit), "--look", LOOK, "--of", added["piece"])

    data = result["data"]
    assert result["ok"] and data["registration_residual"] < 1.0, result["findings"]
    assert abs(data["placed_scale"][0] - scale) < 0.003 and abs(data["placed_scale"][1] - scale) < 0.003
    out = stored(project, data)
    assert out.shape == source.shape
    assert (out[:, :310] == source[:, :310]).all(), "the part of the room the piece doesn't reach is the room's"
    centre_x, centre_y = round(data["placed_at"][0] + scale * 220), round(data["placed_at"][1] + scale * 130)
    assert tuple(out[centre_y, centre_x]) == PAINT
    changed = (out != source).any(axis=2)
    assert changed.sum() < 0.6 * source.shape[0] * (source.shape[1] - 310), "a bounded part of the Source is replaced"
    diff = np.abs(out.astype(int) - source.astype(int)).mean(axis=2)
    ring = diff[100:160, 330:380]  # unpainted piece area: the same picture resampled twice stays close
    assert ring.mean() < 25


def test_a_look_edit_stays_one_of_the_whole_source_for_the_looks_listing(project: Kiripix) -> None:
    full = scene()
    room(project, full[:400, :700])
    project.json("extend", ROOM, "crop", "--box", "100,100,300,300")
    data = project.json("import", ROOM, save(project, "edit.png", painted(full[56:344, :480], (10, 10, 50, 50))),
                        "--look", LOOK, "--of", "crop")["data"]

    assert data["look"] == LOOK and data["variants"] == [data["variant"]]
    assert (data["placed_at"][0], data["placed_at"][1]) == (0, 56)  # centred on the box, moved in
    folder = project.cwd / "assets" / "room" / "alley"
    assert (folder / "src" / "looks" / LOOK / f"{data['variant']}.png").is_file()
    imported = (folder / "imported.jsonl").read_text(encoding="utf-8")
    assert "edit.png" in imported


def test_a_loop_edit_frame_can_be_an_edit_of_a_crop(project: Kiripix) -> None:
    from test_layers_stage import ROOM as LOOP_ROOM
    from test_loop_edit_frames import edits_loop
    from test_loops import LOOP

    edits_loop(project)
    folder = project.cwd / "assets" / "room" / "alley"
    source = np.asarray(Image.open(next((folder / "src").glob("*.png"))).convert("RGBA"))
    height, width = source.shape[:2]
    project.json("extend", LOOP_ROOM, "crop", "--box", f"0,0,{width},{height}", "--size", f"{width}x{height}")
    edit = source.copy()
    edit[10:20, 10:20] = (255, 0, 255, 255)
    Image.fromarray(edit, "RGBA").save(project.cwd / "frame.png")

    result = project.json("import", LOOP_ROOM, "frame.png", "--loop", LOOP, "--frame", "1", "--of", "crop")

    stored_frame = np.asarray(Image.open(project.cwd / result["data"]["file"]).convert("RGBA"))
    assert (stored_frame == edit).all() and result["data"]["of"] == "crop"


def test_bad_of_is_a_finding_with_a_remedy(project: Kiripix) -> None:
    full = scene()
    room(project, full[:400, :700])
    save(project, "edit.png", full[:288, :480])

    no_crop = project.json("import", ROOM, "edit.png", "--look", LOOK, "--of", "crop", expect=1)["findings"][0]
    assert no_crop["code"] == "import.crop_needed" and no_crop["fix"]
    unknown = project.json("import", ROOM, "edit.png", "--look", LOOK, "--of", "ffffffff", expect=1)["findings"][0]
    assert unknown["code"] == "import.of_unknown" and unknown["owner_action"]
    alone = project.json("import", ROOM, "edit.png", "--of", "crop", expect=1)["findings"][0]
    assert alone["code"] == "import.of_needs_look" and alone["fix"]
    big = project.json("extend", ROOM, "crop", "--box", "0,0,100,100", "--size", "800x300", expect=1)["findings"][0]
    assert big["code"] == "extend.crop_too_big"
    small = project.json("extend", ROOM, "crop", "--box", "0,0,600,100", expect=1)["findings"][0]
    assert small["code"] == "extend.crop_too_small"
    assert not list((project.cwd / "assets" / "room" / "alley" / "src").glob("looks/**/*.png"))


def test_a_crop_whose_png_isnt_the_one_its_record_names_is_refused(project: Kiripix) -> None:
    """`crop.png` and `crop.json` are two atomic writes, not one: a crop stopped between them is refused, never placed at the
    old crop's origin."""
    source = scene()[:400, :700]
    room(project, source)
    written = project.json("extend", ROOM, "crop", "--box", "100,100,300,300")["data"]
    save(project, "edit.png", painted(source[0:288, 0:480], (10, 10, 60, 60)))
    Image.fromarray(source[100:388, 200:680], "RGB").save(project.cwd / written["crop"])  # a new crop, its record not yet

    stale = project.json("import", ROOM, "edit.png", "--look", LOOK, "--of", "crop", expect=1)["findings"][0]

    assert stale["code"] == "import.crop_stale" and "extend" in stale["fix"]


def test_two_crops_each_edit_comes_back_to_its_own_crop(project: Kiripix) -> None:
    full = scene()
    source = full[:400, :700]
    room(project, source)
    first = project.json("extend", ROOM, "crop", "--box", "20,20,120,120")["data"]
    second = project.json("extend", ROOM, "crop", "--box", "600,300,690,390")["data"]

    assert first["origin"] == [0, 0] and second["origin"] == [220, 112]
    assert first["crop"] != second["crop"] and (project.cwd / first["crop"]).is_file() and (project.cwd / second["crop"]).is_file()
    assert second["crops"] == [Path(first["crop"]).stem, Path(second["crop"]).stem]
    first_name, second_name = second["crops"]

    first_edit = painted(source[0:288, 0:480], (50, 50, 90, 90))
    one = project.json("import", ROOM, save(project, "one.png", first_edit), "--look", LOOK, "--of", first_name[:8])["data"]
    second_edit = painted(source[112:400, 220:700], (100, 100, 140, 140))
    two = project.json("import", ROOM, save(project, "two.png", second_edit), "--look", "lamp_on", "--of", second_name)["data"]

    assert one["placed_at"] == [0, 0] and two["placed_at"] == [220, 112]
    assert (stored(project, one)[50:90, 50:90] == PAINT).all()
    assert (stored(project, two)[212:252, 320:360] == PAINT).all()


def test_of_crop_is_the_latest_crop(project: Kiripix) -> None:
    full = scene()
    source = full[:400, :700]
    room(project, source)
    project.json("extend", ROOM, "crop", "--box", "20,20,120,120")
    project.json("extend", ROOM, "crop", "--box", "600,300,690,390")
    project.json("extend", ROOM, "crop", "--box", "20,20,120,120")  # the first again: now the latest

    data = project.json("import", ROOM, save(project, "e.png", painted(source[0:288, 0:480], (50, 50, 90, 90))),
                        "--look", LOOK, "--of", "crop")["data"]

    assert data["placed_at"] == [0, 0]
    listed = project.json("extend", ROOM, "crop", "--box", "20,20,120,120")["data"]["crops"]
    assert len(listed) == 2, "the same crop is one crop"


def test_a_crop_of_a_source_no_longer_picked_is_refused_by_name(project: Kiripix) -> None:
    full = scene()
    room(project, full[:400, :700])
    name = Path(project.json("extend", ROOM, "crop", "--box", "20,20,120,120")["data"]["crop"]).stem
    other = project.json("import", ROOM, save(project, "other.png", full[:400, 100:800]))["data"]["variant"]
    project.json("pick", ROOM, other)
    save(project, "e.png", full[0:288, 0:480])

    named = project.json("import", ROOM, "e.png", "--look", LOOK, "--of", name, expect=1)["findings"][0]
    latest = project.json("import", ROOM, "e.png", "--look", LOOK, "--of", "crop", expect=1)["findings"][0]

    assert named["code"] == latest["code"] == "import.crop_stale" and named["fix"]


def test_a_project_with_the_old_single_crop_keeps_working(project: Kiripix) -> None:
    """Before 0287 a crop was `extend/crop.png` and `crop.json` (schema_version 1): still read, and moved into `crops/`
    by the next `extend crop`."""
    import json

    full = scene()
    source = full[:400, :700]
    room(project, source)
    written = project.json("extend", ROOM, "crop", "--box", "20,20,120,120")["data"]
    folder = project.cwd / "assets" / "room" / "alley" / "extend"
    crop_png = project.cwd / written["crop"]
    record = json.loads(crop_png.with_suffix(".json").read_text(encoding="utf-8"))
    del record["number"]
    record["schema_version"] = 1
    (folder / "crop.png").write_bytes(crop_png.read_bytes())
    (folder / "crop.json").write_text(json.dumps(record), encoding="utf-8")
    for path in (folder / "crops").iterdir():
        path.unlink()
    (folder / "crops").rmdir()

    old = project.json("import", ROOM, save(project, "e.png", painted(source[0:288, 0:480], (50, 50, 90, 90))),
                       "--look", LOOK, "--of", "crop")["data"]
    assert old["placed_at"] == [0, 0]

    new = project.json("extend", ROOM, "crop", "--box", "600,300,690,390")["data"]

    assert len(new["crops"]) == 2 and not (folder / "crop.png").exists() and not (folder / "crop.json").exists()
    again = project.json("import", ROOM, "e.png", "--look", "lamp_on", "--of", Path(written["crop"]).stem)["data"]
    assert again["placed_at"] == [0, 0]
