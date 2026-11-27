"""The sound Kind's `process` Stage (ticket 0397, ADR 0016): the kept Takes trimmed, sped up, looped and normalised to the use's
target, with per-Take `tune` Decisions that name a Take by its span.

The recordings are made here from numpy; the founder's real recordings are used when they are in the working tree."""

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from conftest import Kiripix, stage_status
from test_sound import ASSET, FOOTSTEPS, RATE, click_track, make_sound, run_slice, takes

PUDDLE = FOOTSTEPS.with_name("puddle-footsteps.wav")


def read_float_wav(path: Path) -> tuple[int, np.ndarray]:
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and struct.unpack("<H", data[20:22])[0] == 3  # float PCM
    channels, rate = struct.unpack("<HI", data[22:28])
    at = data.index(b"data") + 8
    return rate, np.frombuffer(data[at:], dtype="<f4").reshape(-1, channels)


def process_dir(project: Kiripix, asset: str = ASSET) -> Path:
    return project.cwd / "assets" / "sound" / asset.split(".", 1)[1] / "work" / "process"


def record(project: Kiripix, asset: str = ASSET) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((process_dir(project, asset) / "process.json").read_text(encoding="utf-8"))
    return loaded


def kept_and_processed(project: Kiripix, numbers: str, asset: str = ASSET, expect: int = 0) -> dict[str, Any]:
    project.json("decide", asset, "keep", "--takes", numbers)
    project.json("run", asset, "keep")
    return project.json("run", asset, "process", expect=expect)


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def test_four_kept_takes_are_processed_to_the_uses_peak_and_channels(project: Kiripix) -> None:
    make_sound(project, samples=click_track(channels=2))
    run_slice(project)

    kept_and_processed(project, "1,2,3,4")

    data = record(project)
    assert data["channels"] == 1 and data["target"] == {"peak": -3.0} and data["use"] == "sfx"
    assert [v["variation"] for v in data["variations"]] == [1, 2, 3, 4]
    assert [v["take"] for v in data["variations"]] == [1, 2, 3, 4]
    for item in data["variations"]:
        rate, samples = read_float_wav(process_dir(project) / item["file"])
        assert rate == RATE and samples.shape[1] == 1
        assert item["peak_dbfs"] == pytest.approx(-3.0, abs=0.01)
        assert 20 * np.log10(np.abs(samples).max()) == pytest.approx(-3.0, abs=0.01)
        assert item["length_ms"] == pytest.approx(len(samples) * 1000 / RATE, abs=0.01)
        assert item["loop"] is False and item["loop_offset"] is None and item["overridden"] is False


def test_the_same_inputs_give_the_same_bytes(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    kept_and_processed(project, "1,3")
    first = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in process_dir(project).iterdir() if p.suffix in (".wav", ".json") and p.name != ".stage.json"}

    project.json("run", ASSET, "process", "--force")

    again = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in process_dir(project).iterdir() if p.suffix in (".wav", ".json") and p.name != ".stage.json"}
    assert sorted(first) == ["1.wav", "2.wav", "process.json"]
    assert again == first


def test_speed_shortens_a_take_and_a_tune_names_one_take_by_its_span(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    kept_and_processed(project, "1,2")
    plain = record(project)["variations"]
    second = takes(project)[1]

    project.json("set", ASSET, "process", "speed=1.5", "fade_out=0")
    project.json("decide", ASSET, "process", "--decision", json.dumps({"decision": "tune", "data": {
        "start_ms": second["start_ms"], "end_ms": second["end_ms"], "speed": 1.0}}))
    result = project.json("run", ASSET, "process")

    assert "process.override_unmatched" not in codes(result)
    fast = record(project)["variations"]
    assert fast[0]["length_ms"] == pytest.approx(plain[0]["length_ms"] / 1.5, abs=0.5)
    assert fast[0]["overridden"] is False and fast[0]["settings"]["speed"] == 1.5
    assert fast[1]["length_ms"] == pytest.approx(plain[1]["length_ms"], abs=0.5)
    assert fast[1]["overridden"] is True and fast[1]["settings"]["speed"] == 1.0
    assert all(v["peak_dbfs"] == pytest.approx(-3.0, abs=0.01) for v in fast)


def test_a_tune_that_names_no_kept_take_is_a_finding_and_a_bad_span_is_refused(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    kept_and_processed(project, "1")
    nothing = json.dumps({"decision": "tune", "data": {"start_ms": 123.0, "end_ms": 456.0, "speed": 2.0}})
    bad = json.dumps({"decision": "tune", "data": {"start_ms": 500.0, "end_ms": 400.0}})

    project.json("decide", ASSET, "process", "--decision", nothing)
    result = project.json("run", ASSET, "process")

    found = [f for f in result["findings"] if f["code"] == "process.override_unmatched"]
    assert len(found) == 1 and found[0]["fix"] and found[0]["owner_action"] is None
    assert project.json("decide", ASSET, "process", "--decision", bad, expect=1)["ok"] is False


def test_a_parameter_out_of_range_is_refused(project: Kiripix) -> None:
    make_sound(project)

    assert project.json("set", ASSET, "process", "speed=9", expect=1)["ok"] is False
    assert project.json("set", ASSET, "process", "loop=sideways", expect=1)["ok"] is False


def test_pitch_alone_keeps_the_length_and_filters_run(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    kept_and_processed(project, "1")
    plain = record(project)["variations"][0]["length_ms"]

    project.json("set", ASSET, "process", "pitch=4", "highpass=200", "lowpass=8000", "denoise=6")
    project.json("run", ASSET, "process")

    item = record(project)["variations"][0]
    assert item["length_ms"] == pytest.approx(plain, abs=30)  # rubberband's own latency, not a speed change
    assert item["peak_dbfs"] == pytest.approx(-3.0, abs=0.01)
    assert item["settings"]["pitch"] == 4.0


def ambience(seconds: float = 6.0) -> np.ndarray:
    """A hum (three tones) under faint noise: a bed that matches itself a whole period later."""
    t = np.arange(int(seconds * RATE)) / RATE
    rng = np.random.default_rng(3)
    mono = 0.2 * np.sin(2 * np.pi * 110 * t) + 0.1 * np.sin(2 * np.pi * 331 * t) + 0.05 * np.sin(2 * np.pi * 947 * t)
    mono = mono + 0.01 * rng.standard_normal(len(t))
    return np.stack([mono, 0.8 * mono], axis=1)


def seam_step(loop: np.ndarray) -> float:
    """The jump from the last sample to the first, against the typical step between neighbours."""
    mono = loop.mean(axis=1)
    return float(abs(mono[0] - mono[-1]) / np.sqrt(np.mean(np.diff(mono[:441]) ** 2)))


def test_an_ambience_window_is_looped_with_no_click_at_the_seam_and_the_lufs_target(project: Kiripix) -> None:
    make_sound(project, name="hum", use="ambience", samples=ambience())
    asset = "sound.hum"
    run_slice(project, asset)
    project.json("set", asset, "process", "loop_start=500", "loop_end=4000", "loop_crossfade=80")

    kept_and_processed(project, "1", asset)

    item = record(project, asset)["variations"][0]
    _, samples = read_float_wav(process_dir(project, asset) / "1.wav")
    assert item["loop"] is True and item["loop_offset"] == 0.0
    assert item["loop_match"] > 0.9
    assert samples.shape[1] == 2  # the use's row: ambience is stereo
    assert 2.5 < len(samples) / RATE < 3.6  # the window, its end moved a little to match its start
    assert seam_step(samples) < 3.0
    assert item["lufs"] == pytest.approx(-40.0, abs=1.0)
    assert "process.loop_seam" not in [f["code"] for f in project.json("check", asset)["findings"]]


def test_a_loop_end_that_does_not_match_is_a_loop_seam_finding_with_a_fix(project: Kiripix) -> None:
    rng = np.random.default_rng(11)
    noise = 0.1 * rng.standard_normal((4 * RATE, 1))
    make_sound(project, name="hiss", use="ambience", samples=noise)
    asset = "sound.hiss"
    run_slice(project, asset)
    project.json("set", asset, "process", "loop_min_match=0.5")

    result = kept_and_processed(project, "1", asset)

    found = [f for f in result["findings"] if f["code"] == "process.loop_seam"]
    assert len(found) == 1
    assert found[0]["fix"] == f"kiripix set {asset} process loop_crossfade=100"
    assert found[0]["owner_action"] is None and found[0]["data"]["variation"] == 1
    _, samples = read_float_wav(process_dir(project, asset) / "1.wav")
    assert seam_step(samples) < 3.0  # still no click: the crossfade joins it


def test_a_variation_far_from_its_siblings_is_odd_one_out(project: Kiripix) -> None:
    track = click_track(times=(0.5, 1.2, 2.0, 2.7), seconds=4.5, decay_ms=25.0)
    long_burst = click_track(times=(3.4,), seconds=4.5, decay_ms=300.0)
    make_sound(project, samples=track + long_burst)
    run_slice(project)
    rows = takes(project)
    assert len(rows) == 5, rows

    result = kept_and_processed(project, "1,2,3,4,5")

    odd = [f for f in result["findings"] if f["code"] == "process.odd_one_out"]
    assert [f["data"]["variation"] for f in odd] == [5]
    assert odd[0]["fix"] and odd[0]["owner_action"] is None


def test_a_changed_parameter_makes_process_stale(project: Kiripix) -> None:
    make_sound(project)
    run_slice(project)
    kept_and_processed(project, "1")
    assert stage_status(project, ASSET)["process"] == "done"

    project.json("set", ASSET, "process", "fade_in=20")

    stages = stage_status(project, ASSET)
    assert stages["process"] == "stale" and stages["keep"] == "done"


@pytest.mark.skipif(not FOOTSTEPS.is_file(), reason="the founder's footsteps recording is not in the working tree")
def test_the_asphalt_recording_gives_four_takes_at_minus_3_dbfs_mono(project: Kiripix) -> None:
    project.json("new", "sound", "asphalt", "--use", "sfx")
    variant = str(project.json("import", "sound.asphalt", str(FOOTSTEPS))["data"]["variant"])
    project.json("pick", "sound.asphalt", variant)
    run_slice(project, "sound.asphalt")
    rows = takes(project, "sound.asphalt")
    best = sorted(rows, key=lambda r: int(str(r["clean_rank"])))[:4]  # the four cleanest, in rank order

    kept_and_processed(project, ",".join(str(r["number"]) for r in best), "sound.asphalt")

    data = record(project, "sound.asphalt")
    assert len(data["variations"]) == 4
    for item in data["variations"]:
        _, samples = read_float_wav(process_dir(project, "sound.asphalt") / item["file"])
        assert samples.shape[1] == 1
        assert item["peak_dbfs"] == pytest.approx(-3.0, abs=0.01)


@pytest.mark.skipif(not PUDDLE.is_file(), reason="the founder's puddle recording is not in the working tree")
def test_the_puddle_recording_splashes_are_sped_up_1_5x_and_normalised(project: Kiripix) -> None:
    project.json("new", "sound", "puddle", "--use", "sfx")
    variant = str(project.json("import", "sound.puddle", str(PUDDLE))["data"]["variant"])
    project.json("pick", "sound.puddle", variant)
    run_slice(project, "sound.puddle")
    rows = takes(project, "sound.puddle")
    one = max(rows, key=lambda r: float(str(r["end_ms"])) - float(str(r["start_ms"])))
    project.json("set", "sound.puddle", "process", "speed=1.5")

    kept_and_processed(project, str(one["number"]), "sound.puddle")

    item = record(project, "sound.puddle")["variations"][0]
    assert item["length_ms"] == pytest.approx((float(str(one["end_ms"])) - float(str(one["start_ms"]))) / 1.5, abs=1.0)
    assert item["peak_dbfs"] == pytest.approx(-3.0, abs=0.01)
