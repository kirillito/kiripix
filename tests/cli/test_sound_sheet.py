"""`kiripix sound-sheet` (ticket 0396): the contact sheet of a sound's Takes, checked through the JSON it returns and the PNG."""

import hashlib
import struct
from pathlib import Path

import pytest

from conftest import Kiripix
from test_sound import ASSET, CLICKS, FOOTSTEPS, make_sound, run_slice
from test_sound_process import kept_and_processed


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def sheet(project: Kiripix, *args: str, out: str = "sheet.png", expect: int = 0) -> dict[str, object]:
    result = project.json("sound-sheet", ASSET, out, *args, expect=expect)
    data: dict[str, object] = result["data"]
    return data


def test_five_clicks_give_five_boxes_at_their_places(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)

    data = sheet(project)

    assert png_size(project.cwd / "sheet.png") == (data["width"], data["height"])
    assert data["width"] < 1600 and data["process_status"] is None
    overview = data["overview"]
    boxes = data["boxes"]
    assert [b["take"] for b in boxes] == [1, 2, 3, 4, 5]
    for box, second in zip(boxes, CLICKS, strict=True):
        column = overview["x"] + second * 1000.0 / data["duration_ms"] * overview["width"]
        assert box["x"] <= column <= box["x"] + box["width"], (box, column)
        assert box["y"] == overview["y"] and box["height"] == overview["height"]
        assert box["kept"] is None and box["listed"] is True
    assert [r["take"] for r in data["rows"]] == [1, 2, 3, 4, 5]
    assert all(r["processed"] is None for r in data["rows"])
    row = data["rows"][0]
    assert row["wave"]["width"] == row["spectrogram"]["width"] and row["clean_rank"] >= 1


def test_the_same_inputs_give_the_same_bytes(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    sheet(project, out="a.png")
    sheet(project, out="b.png")
    assert hashlib.sha256((project.cwd / "a.png").read_bytes()).digest() == hashlib.sha256((project.cwd / "b.png").read_bytes()).digest()


def test_takes_limit_the_rows_and_kept_takes_are_marked(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    project.json("decide", ASSET, "keep", "--takes", "2,4")

    data = sheet(project, "--takes", "2-3,5")

    assert [r["take"] for r in data["rows"]] == [2, 3, 5]
    assert [b["listed"] for b in data["boxes"]] == [False, True, True, False, True]
    assert [b["kept"] for b in data["boxes"]] == [None, 1, None, 2, None]
    assert png_size(project.cwd / "sheet.png")[1] < sheet(project)["height"]


def test_a_processed_take_shows_its_speed_and_loudness_change(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    project.json("set", ASSET, "process", "speed=1.5", "fade_out=0")
    kept_and_processed(project, "1,2")

    data = sheet(project)

    assert data["process_status"] == "done"
    first, second = data["rows"][0], data["rows"][1]
    assert first["processed"]["variation"] == 1 and second["processed"]["variation"] == 2
    p = first["processed"]
    assert p["speed"] == 1.5 and p["length_ratio"] == pytest.approx(1 / 1.5, abs=0.01)
    assert p["settings_changed"]["speed"] == 1.5
    assert p["peak_dbfs"] == pytest.approx(-3.0, abs=0.05)
    assert p["peak_change_db"] == pytest.approx(p["peak_dbfs"] - first["peak_dbfs"], abs=0.01) and p["peak_change_db"] != 0
    assert p["lufs_change"] == pytest.approx(p["lufs"] - first["lufs"], abs=0.01)
    assert p["wave"]["y"] > first["wave"]["y"] and p["wave"]["width"] < first["wave"]["width"]
    assert p["loop"] is False and p["seam_step"] is None
    assert data["rows"][2]["processed"] is None


def test_a_loop_shows_its_seam(project: Kiripix) -> None:
    from test_sound_process import ambience
    from test_sound import write_wav

    write_wav(project.cwd / "bed.wav", ambience())
    make_sound(project, "bed", "ambience", "bed.wav")
    project.json("run", "sound.bed", "source")
    project.json("run", "sound.bed", "slice")
    project.json("decide", "sound.bed", "keep", "--takes", "1")
    project.json("run", "sound.bed", "keep")
    project.json("run", "sound.bed", "process")

    data = project.json("sound-sheet", "sound.bed", "bed.png")["data"]

    p = data["rows"][0]["processed"]
    assert p["loop"] is True and p["loop_match"] is not None and p["seam_step"] is not None and p["seam_step"] < 5


def test_the_real_recording_is_one_sheet(project: Kiripix) -> None:
    if not FOOTSTEPS.is_file():
        pytest.skip("the asphalt recording isn't here")
    make_sound(project, "steps", "sfx", str(FOOTSTEPS))
    project.json("run", "sound.steps", "source")
    project.json("run", "sound.steps", "slice")

    data = project.json("sound-sheet", "sound.steps", "steps.png")["data"]

    assert len(data["boxes"]) >= 4 and png_size(project.cwd / "steps.png")[0] == data["width"] < 1600


def test_a_sheet_is_refused_before_slice_and_for_bad_arguments(project: Kiripix) -> None:
    make_sound(project)
    assert project.json("sound-sheet", ASSET, "x.png", expect=1)["findings"][0]["code"] == "slice.not_built"
    run_slice(project)
    assert project.json("sound-sheet", ASSET, "x.txt", expect=1)["findings"][0]["code"] == "input.invalid"
    assert project.json("sound-sheet", ASSET, "x.png", "--takes", "9", expect=1)["findings"][0]["code"] == "sheet.take_unknown"
    assert project.json("sound-sheet", ASSET, "x.png", "--takes", "a", expect=1)["findings"][0]["code"] == "input.invalid"
    project.json("new", "prop", "bench")
    assert project.json("sound-sheet", "prop.bench", "x.png", expect=1)["findings"][0]["code"] == "sound.not_a_sound"
    assert not (project.cwd / "x.png").exists() # nothing is written for a refusal
