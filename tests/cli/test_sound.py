"""The sound Kind's import and slice (ticket 0395, ADR 0016): a recording imported with its Provenance, cut into Takes, and
the `keep` Decision that names the kept ones by their span.

The recordings are made here, from numpy (clicks at known times) and encoded with the ffmpeg the Project itself uses; nothing
is committed but the founder's footsteps recording, which a test uses when it is there."""

import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from conftest import Kiripix, stage_status

RATE = 44100
CLICKS = (0.5, 1.2, 2.0, 2.7, 3.4)  # seconds
ASSET = "sound.clicks"
FOOTSTEPS = Path(__file__).parent.parent.parent / "backlog" / "m6" / "0398-trial" / "shoes-walk-road-asphalt-hard.flac"


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return str(imageio_ffmpeg.get_ffmpeg_exe())


def click_track(times: tuple[float, ...] = CLICKS, seconds: float = 4.0, amp: float = 0.5, decay_ms: float = 25.0,
                channels: int = 1) -> np.ndarray:
    """Faint noise with a burst of noise, decaying over `decay_ms`, at each of `times`: (frames, channels) in [-1, 1]."""
    rng = np.random.default_rng(7)
    out = 1e-4 * rng.standard_normal(int(seconds * RATE))
    for time in times:
        length = int(0.4 * RATE)
        burst = rng.standard_normal(length) * np.exp(-np.arange(length) / RATE / (decay_ms / 1000.0))
        burst *= amp / np.abs(burst).max()
        start = int(time * RATE)
        out[start:start + length] += burst[:len(out) - start]
    return np.stack([out] * channels, axis=1)


def write_wav(path: Path, samples: np.ndarray) -> Path:
    """A 16-bit PCM WAV of `samples` (frames, channels) in [-1, 1]."""
    data = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(data.shape[1])
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(data.tobytes())
    return path


def encode(source: Path, suffix: str) -> Path:
    """The WAV `source` as a FLAC, MP3 or OGG next to it."""
    codec = {".flac": "flac", ".mp3": "libmp3lame", ".ogg": "libvorbis"}[suffix]
    target = source.with_suffix(suffix)
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(source), "-c:a", codec, str(target)], check=True)
    return target


def make_sound(project: Kiripix, name: str = "clicks", use: str = "sfx", file: str = "clicks.wav",
               samples: np.ndarray | None = None, *flags: str) -> str:
    """A sound Asset with a recording imported and picked. Returns the Variant's name."""
    path = project.cwd / file
    if not path.exists():
        write_wav(path, click_track() if samples is None else samples)
    project.json("new", "sound", name, "--use", use)
    variant = str(project.json("import", f"sound.{name}", file, *flags)["data"]["variant"])
    project.json("pick", f"sound.{name}", variant)
    return variant


def run_slice(project: Kiripix, asset: str = ASSET, expect: int = 0) -> dict[str, object]:
    """Decode the recording, then slice it (`run <id> slice` wants its upstream done)."""
    project.json("run", asset, "source")
    return project.json("run", asset, "slice", expect=expect)


def sliced(project: Kiripix, **kwargs: object) -> str:
    variant = make_sound(project, **kwargs)  # type: ignore[arg-type]
    run_slice(project)
    return variant


def takes(project: Kiripix, asset: str = ASSET) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = project.json("sound-takes", asset)["data"]["takes"]
    return rows


# the Kind


def test_a_sound_is_made_with_its_use_and_game_id(project: Kiripix) -> None:
    made = project.json("new", "sound", "footstep_asphalt", "--use", "sfx", "--sound-id", "sfx.footstep.asphalt")

    assert made["data"]["asset"] == "sound.footstep_asphalt"
    text = (project.cwd / "assets" / "sound" / "footstep_asphalt" / "asset.toml").read_text(encoding="utf-8")
    assert 'use = "sfx"' in text and 'sound_id = "sfx.footstep.asphalt"' in text
    assert list(stage_status(project, "sound.footstep_asphalt")) == ["source", "slice", "keep", "process", "export"]


def test_a_sound_needs_its_use_and_refuses_an_unknown_one(project: Kiripix) -> None:
    missing = project.json("new", "sound", "a", expect=1)
    unknown = project.json("new", "sound", "b", "--use", "foley", expect=1)

    assert [f["code"] for f in missing["findings"]] == ["asset.param_required"]
    assert [f["code"] for f in unknown["findings"]] == ["asset.param_invalid"]
    assert not (project.cwd / "assets" / "sound").exists()
    assert project.json("new", "prop", "bench", "--use", "sfx", expect=1)["findings"][0]["code"] == "asset.param_unknown"


def test_a_sound_id_with_the_wrong_prefix_is_a_project_finding(project: Kiripix) -> None:
    project.json("new", "sound", "good", "--use", "sfx")  # sfx.good
    project.json("new", "sound", "wind", "--use", "ambience", "--sound-id", "amb.outside.wind")
    project.json("new", "sound", "bad", "--use", "ui", "--sound-id", "sfx.click")

    result = project.json("check", "--all", expect=2)

    found = [f for f in result["findings"] if f["code"] == "sound.id_prefix"]
    assert [f["position"]["asset"] for f in found] == ["sound.bad"]
    assert found[0]["owner_action"] and found[0]["fix"] is None


# settings


def test_the_default_use_rows_are_the_games_and_an_old_file_migrates(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    assert "schema_version = 15" in text and "[sound.use.ambience]" in text
    old = text.replace("schema_version = 15", "schema_version = 14")
    old = old[:old.index("[sound]")] + old[old.index("[inbox]"):]
    assert "[sound" not in old
    path.write_text(old, encoding="utf-8")

    assert project.json("status")["ok"]
    assert project.json("new", "sound", "a", "--use", "ambience")["ok"]
    assert "[sound" not in path.read_text(encoding="utf-8")  # the defaults are read, written nowhere
    assert "schema_version = 14" in path.read_text(encoding="utf-8")  # a migration is written only by a writing Command of it


def test_a_use_row_needs_one_target_and_an_unknown_key_is_an_error(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")

    path.write_text(text.replace('prefix = "ui"\nchannels = 1\npeak = -3.0', 'prefix = "ui"\nchannels = 1\npeak = -3.0\nlufs = -20.0'),
                    encoding="utf-8")
    both = project.json("status", expect=1)
    path.write_text(text.replace('prefix = "ui"\nchannels = 1\npeak = -3.0\n', 'prefix = "ui"\nchannels = 1\n'), encoding="utf-8")
    neither = project.json("status", expect=1)
    path.write_text(text.replace("quality = 5", "quality = 5\nloudness = 1"), encoding="utf-8")
    unknown = project.json("status", expect=1)

    assert [f["code"] for f in both["findings"]] == ["settings.sound_target"]
    assert [f["code"] for f in neither["findings"]] == ["settings.sound_target"]
    assert [f["code"] for f in unknown["findings"]] == ["config.unknown_key"]


# import


@pytest.mark.parametrize("suffix", [".wav", ".flac", ".mp3", ".ogg"])
def test_a_recording_of_each_format_is_imported_and_decoded(project: Kiripix, suffix: str) -> None:
    wav = write_wav(project.cwd / "clicks.wav", click_track(channels=2))
    recording = wav if suffix == ".wav" else encode(wav, suffix)
    project.json("new", "sound", "clicks", "--use", "sfx")

    imported = project.json("import", ASSET, recording.name)["data"]

    assert imported["created"] and imported["sound"]["rate"] == RATE and imported["sound"]["channels"] == 2
    assert imported["file"].endswith(f"{imported['variant']}{suffix}")
    assert (project.cwd / imported["file"]).read_bytes() == recording.read_bytes()  # stored whole
    project.json("pick", ASSET, imported["variant"])
    run_slice(project)
    rows = takes(project)
    assert len(rows) == 5
    shown = project.json("sound-takes", ASSET)["data"]
    assert (shown["rate"], shown["channels"]) == (RATE, 2)


def test_a_recording_imported_twice_is_one_variant_with_the_newest_provenance(project: Kiripix) -> None:
    write_wav(project.cwd / "clicks.wav", click_track())
    project.json("new", "sound", "clicks", "--use", "sfx")

    first = project.json("import", ASSET, "clicks.wav", "--author", "Me", "--licence", "own recording")["data"]
    again = project.json("import", ASSET, "clicks.wav", "--url", "https://example.org/clicks", "--licence", "CC0")["data"]
    quiet = project.json("import", ASSET, "clicks.wav")["data"]

    assert first["created"] and not again["created"] and not quiet["created"]
    assert first["variants"] == again["variants"] == [first["variant"]]
    assert first["sound"]["author"] == "Me" and first["sound"]["url"] is None
    assert (again["sound"]["url"], again["sound"]["author"], again["sound"]["licence"]) == (
        "https://example.org/clicks", "Me", "CC0")  # a flag left out keeps what the newest line had
    assert quiet["sound"]["licence"] == "CC0"
    lines = (project.cwd / "assets" / "sound" / "clicks" / "imported.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert len(records) == 2 and all(r["file"] == first["file"].split("clicks/", 1)[1] for r in records)
    assert records[0]["author"] == "Me" and records[1]["licence"] == "CC0" and records[1]["at"] >= records[0]["at"]
    assert not (project.cwd / "assets" / "sound" / "clicks" / "src" / "clicks.wav").exists()


def test_provenance_changes_no_stage(project: Kiripix) -> None:
    sliced(project)
    before = stage_status(project, ASSET)

    project.json("import", ASSET, "clicks.wav", "--author", "Me", "--licence", "CC0")

    assert stage_status(project, ASSET) == before and before["slice"] == "done"


def test_a_file_that_is_no_recording_is_refused(project: Kiripix) -> None:
    project.json("new", "sound", "clicks", "--use", "sfx")
    (project.cwd / "junk.wav").write_bytes(b"this is not audio at all")
    (project.cwd / "notes.txt").write_text("hello", encoding="utf-8")
    (project.cwd / "clip.m4a").write_bytes(b"\x00\x00\x00\x18ftypM4A ")

    junk = project.json("import", ASSET, "junk.wav", expect=1)
    text = project.json("import", ASSET, "notes.txt", expect=1)
    other = project.json("import", ASSET, "clip.m4a", expect=1)
    absent = project.json("import", ASSET, "nowhere.wav", expect=1)

    assert [f["code"] for f in junk["findings"]] == ["import.not_audio"]
    assert [f["code"] for f in text["findings"]] == ["import.not_a_sound"]
    assert [f["code"] for f in other["findings"]] == ["import.not_a_sound"]
    assert [f["code"] for f in absent["findings"]] == ["import.not_found"]
    assert not any((project.cwd / "assets" / "sound" / "clicks" / "src").glob("*")), "a refused file is not stored"


def test_provenance_flags_are_for_a_sound(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    (project.cwd / "in.png").write_bytes(b"x")

    result = project.json("import", "prop.bench", "in.png", "--author", "Me", expect=1)

    assert result["findings"][0]["code"] == "import.provenance_needs_sound"


def test_a_sound_takes_one_recording_and_no_image_roles(project: Kiripix) -> None:
    write_wav(project.cwd / "clicks.wav", click_track())
    project.json("new", "sound", "clicks", "--use", "sfx")

    result = project.json("import", ASSET, "clicks.wav", "--role", "sheet", expect=1)

    assert result["findings"][0]["code"] == "import.sound_takes_a_recording"


# slice


def test_five_clicks_give_five_takes_at_the_right_times(project: Kiripix) -> None:
    sliced(project)

    rows = takes(project)

    assert [r["number"] for r in rows] == [1, 2, 3, 4, 5]
    for row, time in zip(rows, CLICKS, strict=True):
        assert abs(float(row["onset_ms"]) - time * 1000) <= 5  # type: ignore[arg-type]
        assert abs(float(row["start_ms"]) - (time * 1000 - 10)) <= 5.1  # type: ignore[arg-type]  # 10 ms of pre-roll
        assert 20 < float(row["end_ms"]) - float(row["onset_ms"]) < 300  # type: ignore[arg-type]
        assert not row["clipped"] and not row["overlaps_next"]
        assert -8 < float(row["peak_dbfs"]) < -5.5  # type: ignore[arg-type]  # 0.5
    assert sorted(r["clean_rank"] for r in rows) == [1, 2, 3, 4, 5]  # type: ignore[type-var]
    assert all(0.5 < float(r["similarity"]) <= 1 for r in rows)  # type: ignore[arg-type]  # five alike clicks


def test_takes_are_measured(project: Kiripix) -> None:
    sliced(project, file="quiet.wav", samples=click_track() * 0.1)  # the same clicks 20 dB lower

    row = takes(project)[0]

    assert -28 < float(row["peak_dbfs"]) < -25  # type: ignore[arg-type]
    assert float(row["rms_dbfs"]) < float(row["peak_dbfs"])  # type: ignore[arg-type]
    assert abs(float(row["lufs"]) - float(row["rms_dbfs"])) < 6  # type: ignore[arg-type]  # K-weighted noise: a little louder
    assert 500 < float(row["centroid_hz"]) < 20000  # type: ignore[arg-type]  # noise: bright


def test_a_scrape_among_clicks_has_a_low_likeness(project: Kiripix) -> None:
    rng = np.random.default_rng(3)
    samples = click_track((0.5, 1.2, 2.7, 3.4, 4.1), seconds=5.0)
    start = int(1.95 * RATE)
    length = int(0.5 * RATE)
    scrape = 0.3 * np.convolve(rng.standard_normal(length), np.ones(40) / 40, mode="same") * np.hanning(length) ** 0.2
    samples[start:start + length, 0] += scrape
    sliced(project, samples=samples)

    rows = takes(project)

    assert len(rows) == 6
    odd = min(rows, key=lambda r: float(r["similarity"]))  # type: ignore[arg-type]
    assert abs(float(odd["onset_ms"]) - 1950) < 40 and float(odd["similarity"]) < 0.6  # type: ignore[arg-type]
    assert all(float(r["similarity"]) > 0.8 for r in rows if r is not odd)  # type: ignore[arg-type]


def test_slice_settings_change_the_takes(project: Kiripix) -> None:
    quiet = click_track((0.5, 1.2, 2.0), amp=0.5)
    quiet[int(2.7 * RATE):int(2.7 * RATE) + 400, 0] += click_track((0.0,), seconds=0.1, amp=0.004)[:400, 0]  # a faint tick
    sliced(project, samples=quiet)
    found = len(takes(project))

    project.json("set", ASSET, "slice", "threshold=3")
    project.json("run", ASSET, "slice")

    assert found == 3 and len(takes(project)) >= 3
    assert project.json("show", ASSET)["data"]["stages"][1]["params"]["threshold"] == 3


def test_an_ambience_is_one_take_less_its_silent_head_and_tail(project: Kiripix) -> None:
    rng = np.random.default_rng(5)
    bed = np.zeros((int(4 * RATE), 2))
    bed[int(1 * RATE):int(3 * RATE)] = 0.05 * rng.standard_normal((2 * RATE, 2))
    make_sound(project, "bed", "ambience", "bed.wav", bed)

    run_slice(project, "sound.bed")
    shown = project.json("sound-takes", "sound.bed")["data"]

    assert shown["mode"] == "whole" and shown["channels"] == 2 and len(shown["takes"]) == 1
    take = shown["takes"][0]
    assert abs(take["start_ms"] - 1000) < 30 and abs(take["end_ms"] - 3000) < 30
    assert take["similarity"] == 1


def test_the_mode_can_cut_an_ambience_by_onset(project: Kiripix) -> None:
    make_sound(project, "bed", "ambience", "bed.wav", click_track())

    project.json("set", "sound.bed", "slice", "mode=onsets")
    run_slice(project, "sound.bed")

    assert len(takes(project, "sound.bed")) == 5


def test_nothing_over_the_threshold_is_a_finding(project: Kiripix) -> None:
    steady = 0.1 * np.random.default_rng(9).standard_normal((3 * RATE, 1))
    make_sound(project, "hiss", "sfx", "hiss.wav", steady)

    result = run_slice(project, "sound.hiss", expect=2)

    found = [f for f in result["findings"] if f["code"] == "slice.none"]
    assert len(found) == 1 and found[0]["fix"] == "kiripix set sound.hiss slice threshold=8"
    assert takes(project, "sound.hiss") == []


def test_a_take_that_reaches_0_dbfs_and_runs_into_the_next_are_findings(project: Kiripix) -> None:
    sliced(project, samples=click_track((0.5, 0.75), seconds=3.0, decay_ms=100.0, amp=1.0))  # the second begins while the first rings

    check = project.json("check", ASSET)

    warnings = {f["code"]: f for f in check["findings"]}
    assert warnings["slice.clipped"]["severity"] == "warning" and warnings["slice.clipped"]["data"]["takes"] == [1, 2]
    assert warnings["slice.overlap"]["data"]["takes"] == [1]
    assert all(f["fix"] and f["owner_action"] is None for f in warnings.values())
    rows = takes(project)
    assert [(r["clipped"], r["overlaps_next"]) for r in rows] == [(True, True), (True, False)]
    assert float(rows[0]["end_ms"]) <= float(rows[1]["start_ms"])  # type: ignore[arg-type]
    assert [r["clean_rank"] for r in rows] == [2, 1]  # both clip; the first also runs into the next


def test_a_recording_whose_file_changes_is_a_new_variant(project: Kiripix) -> None:
    variant = sliced(project)
    write_wav(project.cwd / "other.wav", click_track((0.4, 1.0)))

    other = project.json("import", ASSET, "other.wav")["data"]

    assert other["variant"] != variant and len(other["variants"]) == 2
    assert stage_status(project, ASSET)["source"] == "stale"  # `source` reads every Variant in src/, as every Kind's does
    project.json("pick", ASSET, other["variant"])
    run_slice(project)
    assert stage_status(project, ASSET)["slice"] == "done" and len(takes(project)) == 2


def test_the_takes_are_not_listed_before_slice_has_run(project: Kiripix) -> None:
    make_sound(project)

    result = project.json("sound-takes", ASSET, expect=1)

    assert result["findings"][0]["code"] == "slice.not_built" and result["findings"][0]["fix"] == f"kiripix next {ASSET}"
    assert project.json("sound-takes", "sound.nope", expect=1)["findings"][0]["code"] == "asset.not_found"


def test_the_takes_print_as_a_table(project: Kiripix) -> None:
    sliced(project)

    result = project("sound-takes", ASSET)

    assert result.code == 0
    assert "5 Take(s)" in result.stdout and "centroid" in result.stdout and "overlaps-next" not in result.stdout
    assert len(result.stdout.splitlines()) == 3 + 5  # the heading, the units, the columns, a row each


# keep


def keep(project: Kiripix, numbers: str, asset: str = ASSET) -> dict[str, object]:
    return project.json("decide", asset, "keep", "--takes", numbers, "--brief")


def test_a_keep_names_takes_by_span_in_the_order_typed(project: Kiripix) -> None:
    sliced(project)
    rows = takes(project)

    kept = keep(project, "4,1,3")

    assert kept["ok"] and kept["data"]["count"] == 1  # type: ignore[index]
    shown = project.json("show", ASSET)["data"]
    keep_stage = next(s for s in shown["stages"] if s["stage"] == "keep")
    spans = keep_stage["decisions"][0]["data"]["takes"]
    assert [(s["start_ms"], s["end_ms"]) for s in spans] == [(rows[n - 1]["start_ms"], rows[n - 1]["end_ms"]) for n in (4, 1, 3)]
    assert [r["kept"] for r in takes(project)] == [2, None, 3, 1, None]
    assert project.json("run", ASSET, "keep")["ok"]
    built = json.loads((project.cwd / "assets" / "sound" / "clicks" / "work" / "keep" / "keep.json").read_text(encoding="utf-8"))
    assert [(k["variation"], k["take"]) for k in built["kept"]] == [(1, 4), (2, 1), (3, 3)]
    assert stage_status(project, ASSET)["keep"] == "done"


def test_a_keep_can_be_recorded_by_span_directly(project: Kiripix) -> None:
    sliced(project)
    first = takes(project)[0]
    spans = {"takes": [{"start_ms": float(first["start_ms"]) + 0.4, "end_ms": float(first["end_ms"]) - 0.4}]}  # within 1 ms

    project.json("decide", ASSET, "keep", "--decision", json.dumps({"decision": "keep", "data": spans}))
    project.json("run", ASSET, "keep")

    assert stage_status(project, ASSET)["keep"] == "done"  # exact: every bound within 1 ms


def test_a_keep_is_refused_for_numbers_that_are_not_takes(project: Kiripix) -> None:
    make_sound(project)
    early = project.json("decide", ASSET, "keep", "--takes", "1", expect=1)
    run_slice(project)

    unknown = project.json("decide", ASSET, "keep", "--takes", "1,9", expect=1)
    twice = project.json("decide", ASSET, "keep", "--takes", "2,2", expect=1)
    words = project.json("decide", ASSET, "keep", "--takes", "first", expect=1)
    wrong_stage = project.json("decide", ASSET, "slice", "--takes", "1", expect=1)
    bad_span = project.json("decide", ASSET, "keep", "--decision", json.dumps(
        {"decision": "keep", "data": {"takes": [{"start_ms": 500, "end_ms": 400}]}}), expect=1)

    assert early["findings"][0]["code"] == "slice.not_built"
    assert unknown["findings"][0]["code"] == "keep.take_unknown" and "1 to 5" in unknown["findings"][0]["message"]
    assert twice["findings"][0]["code"] == "keep.takes_invalid" and words["findings"][0]["code"] == "keep.takes_invalid"
    assert wrong_stage["findings"][0]["code"] == "decide.takes_need_keep"
    assert bad_span["findings"][0]["code"] == "decision.invalid"
    assert project.json("show", ASSET)["data"]["stages"][2]["decisions"] == []


def test_keep_waits_for_the_decision(project: Kiripix) -> None:
    sliced(project)

    result = project.json("run", ASSET, "keep", expect=3)

    assert stage_status(project, ASSET)["keep"] == "needs-input"
    assert result["findings"][0]["code"] == "stage.needs_input" and result["findings"][0]["fix"] == f"kiripix sound-takes {ASSET}"


def test_a_keep_survives_a_reslice_with_the_same_settings(project: Kiripix) -> None:
    sliced(project)
    keep(project, "2,4")
    project.json("run", ASSET, "keep")

    project.json("run", ASSET, "slice", "--force")
    again = project.json("run", ASSET, "keep")

    assert [r["outcome"] for r in again["data"]["results"]] == ["skipped"]  # the same inputs: nothing to rebuild, nothing asked
    assert stage_status(project, ASSET)["keep"] == "done"
    assert [r["kept"] for r in takes(project)] == [None, 1, None, 2, None]


def test_a_changed_threshold_that_drops_a_kept_take_is_a_finding(project: Kiripix) -> None:
    samples = click_track((0.5, 1.2, 2.0), amp=0.5)
    samples[int(2.7 * RATE):int(2.7 * RATE) + 300, 0] += click_track((0.0,), seconds=0.1, amp=0.1)[:300, 0]  # a -20 dBFS tick
    sliced(project, samples=samples)
    found = takes(project)
    assert len(found) == 4
    quiet = next(r for r in found if float(r["peak_dbfs"]) < -15)  # type: ignore[arg-type]
    keep(project, f"1,{quiet['number']}")
    project.json("run", ASSET, "keep")

    project.json("set", ASSET, "slice", "threshold=50")  # over the tick's rise, under the clicks'
    result = project.json("run", ASSET, expect=3)

    codes = [f["code"] for f in result["findings"]]
    assert "keep.take_missing" in codes
    finding = next(f for f in result["findings"] if f["code"] == "keep.take_missing")
    assert finding["position"]["stage"] == "keep" and finding["data"]["take"] == 2
    assert finding["data"]["start_ms"] == quiet["start_ms"] and finding["fix"] == f"kiripix sound-takes {ASSET}"
    assert stage_status(project, ASSET)["keep"] == "needs-input"
    # nothing was dropped or renumbered silently: the Decision is as recorded
    spans = next(s for s in project.json("show", ASSET)["data"]["stages"] if s["stage"] == "keep")["decisions"][0]["data"]["takes"]
    assert len(spans) == 2 and spans[1]["start_ms"] == quiet["start_ms"]


def test_a_moved_bound_is_a_review_that_accept_settles(project: Kiripix) -> None:
    sliced(project, samples=click_track(decay_ms=60.0))
    keep(project, "1,2")
    project.json("run", ASSET, "keep")
    before = takes(project)

    project.json("set", ASSET, "slice", "floor=50")  # the same Takes, each ending later
    result = project.json("run", ASSET, expect=3)

    after = takes(project)
    assert [r["start_ms"] for r in after] == [r["start_ms"] for r in before]
    assert all(float(a["end_ms"]) > float(b["end_ms"]) + 1 for a, b in zip(after, before, strict=True))  # type: ignore[arg-type]
    assert result["findings"][0]["code"] == "stage.needs_review" and stage_status(project, ASSET)["keep"] == "needs-review"
    built = json.loads((project.cwd / "assets" / "sound" / "clicks" / "work" / "keep" / "keep.json").read_text(encoding="utf-8"))
    assert built["kept"][0]["end_ms"] == after[0]["end_ms"]  # the cut is always slice's, as it is now

    project.json("accept", ASSET, "keep", owner=True)
    project.json("run", ASSET, "keep")

    assert stage_status(project, ASSET)["keep"] == "done"
    spans = next(s for s in project.json("show", ASSET)["data"]["stages"] if s["stage"] == "keep")["decisions"][-1]["data"]["takes"]
    assert [s["end_ms"] for s in spans] == [after[0]["end_ms"], after[1]["end_ms"]]


def test_a_new_take_earlier_renumbers_the_others_and_the_keep_follows_its_span(project: Kiripix) -> None:
    sliced(project, samples=click_track((1.2, 2.0, 2.7), amp=0.5))
    keep(project, "2")  # the click at 2.0 s
    project.json("run", ASSET, "keep")
    extra = click_track((0.5, 1.2, 2.0, 2.7))
    write_wav(project.cwd / "more.wav", extra)
    variant = project.json("import", ASSET, "more.wav", "--author", "A", "--licence", "CC0")["data"]["variant"]

    project.json("pick", ASSET, variant)
    project.json("run", ASSET)  # a Take earlier: what was Take 2 is Take 3, and the replay is exact

    assert stage_status(project, ASSET)["keep"] == "done"
    assert [r["kept"] for r in takes(project)] == [None, None, 1, None]


# the founder's recording


@pytest.mark.skipif(not FOOTSTEPS.is_file(), reason="the founder's recording is not in backlog/m6/0398-trial")
def test_the_asphalt_recording_slices_into_single_steps(project: Kiripix) -> None:
    project.json("new", "sound", "footstep_asphalt", "--use", "sfx", "--sound-id", "sfx.footstep.asphalt")
    asset = "sound.footstep_asphalt"
    variant = project.json("import", asset, str(FOOTSTEPS), "--author", "founder", "--licence", "own recording")["data"]
    project.json("pick", asset, variant["variant"])

    run_slice(project, asset)
    rows = takes(project, asset)

    assert 13 <= len(rows) <= 16  # about 15 events over 9 s, a step every 0.6 s
    onsets = [float(r["onset_ms"]) for r in rows]  # type: ignore[arg-type]
    assert all(b - a >= 120 for a, b in zip(onsets, onsets[1:]))
    assert all(float(r["end_ms"]) - float(r["start_ms"]) < 600 for r in rows)  # type: ignore[arg-type]  # a step, not a stretch
    assert not any(r["overlaps_next"] or r["clipped"] for r in rows)
    scrapes = [r for r in rows if float(r["similarity"]) < 0.5]  # type: ignore[arg-type]
    assert len(scrapes) <= 3
