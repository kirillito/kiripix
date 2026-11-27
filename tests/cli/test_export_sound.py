"""A sound's export (ticket 0400, ADR 0016, spec §9): the `export` Stage encodes each variation to OGG Vorbis, and `kiripix export`
copies the files byte for byte to `<[sound] folder>/<use>/`, outside the export root, with the source's Provenance in the
Manifest's `sound` block. Ownership by hash, `--force`, `--adopt`, `--prune` and the freeze apply as to any other Kind.

The recordings are made here from numpy. No test compares OGG bytes with a committed file: the bytes depend on the platform's
ffmpeg wheel."""

import hashlib
import json
import shutil
import struct
from pathlib import Path
from typing import Any

import pytest

from conftest import Kiripix, stage_status
from test_export import godot_project, set_target
from test_export_ownership import backups
from test_manifest_merge import git, init_game, needs_git
from test_sound import FOOTSTEPS, click_track, run_slice, takes, write_wav
from test_sound_process import kept_and_processed, process_dir

AUTHOR, LICENCE, URL = "A. Foley", "CC0 1.0", "https://example.com/footsteps"
PROVENANCE = ("--author", AUTHOR, "--licence", LICENCE, "--url", URL)
GAMES = b"the game's own\n"
AUDIO = "game/audio/sfx"
RES = "res://audio/sfx"


def built_sound(project: Kiripix, name: str = "clicks", numbers: str = "1,2,3,4", sound_id: str | None = None,
                flags: tuple[str, ...] = PROVENANCE, use: str = "sfx", game: bool = True, expect: int = 0) -> str:
    """A sound with every Stage built up to `export`, in a Project with a Godot project to export into. Returns its Asset ID."""
    asset = f"sound.{name}"
    file = f"{name}.wav"
    write_wav(project.cwd / file, click_track())
    project.json("new", "sound", name, "--use", use, *(("--sound-id", sound_id) if sound_id else ()))
    variant = str(project.json("import", asset, file, *flags)["data"]["variant"])
    project.json("pick", asset, variant)
    run_slice(project, asset)
    kept_and_processed(project, numbers, asset)
    if game:
        godot_project(project)
        set_target(project)
    project.json("run", asset, "export", expect=expect)
    return asset


def out(project: Kiripix, name: str = "clicks") -> Path:
    return project.cwd / "assets" / "sound" / name / "out" / "export"


def manifest(project: Kiripix, asset: str = "sound.clicks") -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / "game" / "kiripix" / "manifest" / f"{asset}.json").read_text("utf-8"))
    return value


def vorbis_channels(data: bytes) -> int:
    at = data.index(b"\x01vorbis")
    return int(struct.unpack("<B", data[at + 11:at + 12])[0])


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


# the Stage


def test_the_stage_encodes_four_mono_oggs_numbered_from_the_sound_id_and_records_them(project: Kiripix) -> None:
    built_sound(project, sound_id="sfx.footstep.asphalt")

    folder = out(project)

    names = sorted(p.name for p in folder.iterdir() if p.name != ".stage.json")
    assert names == [f"footstep_asphalt_{n}.ogg" for n in (1, 2, 3, 4)] + ["sound.json"]
    record = json.loads((folder / "sound.json").read_text("utf-8"))
    assert record["id"] == "sfx.footstep.asphalt" and record["use"] == "sfx" and record["channels"] == 1
    assert [f["file"] for f in record["files"]] == [f"footstep_asphalt_{n}.ogg" for n in (1, 2, 3, 4)]
    for item in record["files"]:
        data = (folder / item["file"]).read_bytes()
        assert data[:4] == b"OggS" and vorbis_channels(data) == 1
        assert item["peak_dbfs"] == pytest.approx(-3.0, abs=1.5)  # Vorbis is lossy: the encoded file is measured
        assert 0.05 < item["length_s"] < 0.5
    assert record["source"] == {"file": "clicks.wav", "hash": record["source"]["hash"], "url": URL, "author": AUTHOR,
                                "licence": LICENCE}
    assert stage_status(project, "sound.clicks")["export"] == "done"


def test_a_lone_variation_has_no_number(project: Kiripix) -> None:
    built_sound(project, numbers="2")

    assert sorted(p.name for p in out(project).iterdir() if p.suffix == ".ogg") == ["clicks.ogg"]


def test_the_same_inputs_give_the_same_bytes(project: Kiripix) -> None:
    built_sound(project)
    before = {p.name: p.read_bytes() for p in out(project).iterdir() if not p.name.startswith(".")}

    project.json("run", "sound.clicks", "export", "--force")

    again = {p.name: p.read_bytes() for p in out(project).iterdir() if not p.name.startswith(".")}
    assert again == before and len(before) == 5


def test_a_recording_without_author_or_licence_is_refused_at_export_with_an_owner_action(project: Kiripix) -> None:
    asset = built_sound(project, flags=("--url", URL), expect=2)

    checked = project.json("check", asset, expect=2)
    refused = project.json("export", asset, expect=2)

    for result in (checked, refused):
        [finding] = [f for f in result["findings"] if f["code"] == "sound.provenance_missing"]
        assert finding["severity"] == "error" and finding["owner_action"] and not finding["fix"]
        assert "author and no licence" in finding["message"]
    assert not (project.cwd / "game" / "audio").exists() and not (project.cwd / "game" / "kiripix").exists()


# the Exporter


def test_export_copies_the_files_byte_for_byte_outside_the_root_and_lists_them_in_the_manifest(project: Kiripix) -> None:
    asset = built_sound(project)
    files = sorted(p for p in out(project).iterdir() if p.suffix == ".ogg")

    data = project.json("export", asset)["data"]

    assert sorted(data["written"]) == [f"{RES}/clicks_{n}.ogg" for n in (1, 2, 3, 4)] and data["counter"] == 1
    for built in files:
        assert (project.cwd / AUDIO / built.name).read_bytes() == built.read_bytes()
    assert sorted(p.name for p in (project.cwd / "game" / "audio").rglob("*") if p.is_file()) == [p.name for p in files]
    record = manifest(project, asset)
    assert record["schema_version"] == 5 and record["asset"] == asset and record["exported"] is True
    assert sorted(record["files"]) == [f"{RES}/clicks_{n}.ogg" for n in (1, 2, 3, 4)]
    assert record["files"][f"{RES}/clicks_1.ogg"] == hashlib.sha256(files[0].read_bytes()).hexdigest()
    sound = record["sound"]
    assert sound["id"] == "sfx.clicks" and sound["use"] == "sfx"
    assert [f["path"] for f in sound["files"]] == [f"{RES}/clicks_{n}.ogg" for n in (1, 2, 3, 4)]
    assert sound["source"] == {"file": "clicks.wav", "hash": sound["source"]["hash"], "url": URL, "author": AUTHOR,
                               "licence": LICENCE}
    source = next((project.cwd / "assets" / "sound" / "clicks" / "src").glob("*.wav"))
    assert sound["source"]["hash"] == hashlib.sha256(source.read_bytes()).hexdigest()
    first = sound["files"][0]
    assert set(first) >= {"path", "take", "length_s", "peak_dbfs", "lufs", "loop"} and set(first["take"]) == {"start_ms", "end_ms"}
    assert first["loop"] is False and "loop_offset" not in first  # a None is left out of the Manifest
    assert sound["processing"]["rate"] == 44100 and sound["processing"]["channels"] == 1
    assert sound["processing"]["target"] == {"peak": -3.0} and len(sound["processing"]["settings"]) == 4
    assert not list((project.cwd / "game").rglob("audio.json")) and not list((project.cwd / "game").rglob("CREDITS.md"))


def test_a_second_export_writes_nothing(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    before = (project.cwd / "game" / "kiripix" / "manifest" / f"{asset}.json").read_bytes()

    again = project.json("export", asset)["data"]

    assert again["written"] == [] and again["counter"] == 1
    assert (project.cwd / "game" / "kiripix" / "manifest" / f"{asset}.json").read_bytes() == before


def test_export_all_exports_the_sound_and_the_stage_state_says_when_the_game_is_behind(project: Kiripix) -> None:
    asset = built_sound(project)
    assert project.json("show", asset)["data"].get("export_command") == f"kiripix export {asset}"

    project.json("export", "--all")

    assert (project.cwd / AUDIO / "clicks_1.ogg").is_file()
    assert project.json("show", asset)["data"].get("export_command") is None


def test_a_corrected_provenance_changes_only_the_manifest(project: Kiripix) -> None:
    asset = built_sound(project, flags=("--author", "A. Foley", "--licence", "CC-BY 4.0"))
    project.json("export", asset)
    ogg = (project.cwd / AUDIO / "clicks_1.ogg").read_bytes()
    stages = stage_status(project, asset)

    project.json("import", asset, "clicks.wav", "--licence", "CC0 1.0", "--url", URL)

    changed = stage_status(project, asset)
    assert [s for s in changed if changed[s] != stages[s]] == ["export"], changed
    project.json("run", asset, "export")
    data = project.json("export", asset)["data"]
    assert data["written"] == [] and data["counter"] == 2, "the files are the same; the block is not"
    assert (project.cwd / AUDIO / "clicks_1.ogg").read_bytes() == ogg
    source = manifest(project, asset)["sound"]["source"]
    assert source["licence"] == "CC0 1.0" and source["url"] == URL and source["author"] == "A. Foley"


def test_a_file_the_game_changed_is_refused_by_name_and_force_backs_it_up(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    (project.cwd / AUDIO / "clicks_2.ogg").write_bytes(GAMES)

    refused = project.json("export", asset, expect=3)

    [finding] = refused["findings"]
    assert finding["code"] == "export.file_changed" and f"{RES}/clicks_2.ogg" in finding["message"] and finding["owner_action"]
    assert (project.cwd / AUDIO / "clicks_2.ogg").read_bytes() == GAMES
    project.json("run", asset, "export", "--force")  # the built files are unchanged, so only the flag takes the file

    forced = project.json("export", asset, "--force")["data"]

    assert forced["written"] == [f"{RES}/clicks_2.ogg"] and forced["backed_up"] == [f"{RES}/clicks_2.ogg"]
    [stamp] = backups(project)
    assert next(stamp.rglob("clicks_2.ogg")).read_bytes() == GAMES
    assert (project.cwd / AUDIO / "clicks_2.ogg").read_bytes() == (out(project) / "clicks_2.ogg").read_bytes()


def test_a_file_of_the_games_own_at_the_path_needs_adopt(project: Kiripix) -> None:
    asset = built_sound(project)
    (project.cwd / AUDIO).mkdir(parents=True)
    (project.cwd / AUDIO / "clicks_1.ogg").write_bytes(GAMES)

    refused = project.json("export", asset, expect=3)

    assert refused["findings"][0]["code"] == "export.file_unmanaged" and f"{RES}/clicks_1.ogg" in refused["findings"][0]["message"]
    assert (project.cwd / AUDIO / "clicks_1.ogg").read_bytes() == GAMES
    assert not (project.cwd / "game" / "kiripix").exists(), "nothing was written"

    adopted = project.json("export", asset, "--adopt")["data"]

    assert f"{RES}/clicks_1.ogg" in adopted["backed_up"]
    [stamp] = backups(project)
    assert next(stamp.rglob("clicks_1.ogg")).read_bytes() == GAMES
    assert (project.cwd / AUDIO / "clicks_1.ogg").read_bytes() == (out(project) / "clicks_1.ogg").read_bytes()


def test_prune_removes_a_deleted_sounds_files_and_their_import_sidecars(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    keep = project.cwd / "game" / "audio" / "ui" / "mine.ogg"
    keep.parent.mkdir(parents=True)
    keep.write_bytes(GAMES)
    for n in (1, 2, 3, 4):  # Godot's own, beside what it imported
        (project.cwd / AUDIO / f"clicks_{n}.ogg.import").write_text("[remap]\n", "utf-8")
    shutil.rmtree(project.cwd / "assets" / "sound" / "clicks")

    data = project.json("export", "--prune")["data"]

    assert sorted(data["removed"]) == sorted(
        [f"{RES}/clicks_{n}.ogg" for n in (1, 2, 3, 4)] + ["res://kiripix/manifest/sound.clicks.json"])
    assert not (project.cwd / "game" / "audio" / "sfx").exists(), "the emptied use folder goes, with its sidecars"
    assert keep.read_bytes() == GAMES and (project.cwd / "game" / "audio").is_dir()
    assert not (project.cwd / "game" / "kiripix" / "manifest" / "sound.clicks.json").exists()


def test_prune_refuses_a_changed_sound_file_and_force_backs_it_up(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    (project.cwd / AUDIO / "clicks_3.ogg").write_bytes(GAMES)
    shutil.rmtree(project.cwd / "assets" / "sound" / "clicks")

    refused = project.json("export", "--prune", expect=3)

    assert refused["findings"][0]["code"] == "export.file_changed" and "clicks_3.ogg" in refused["findings"][0]["message"]
    assert (project.cwd / AUDIO / "clicks_1.ogg").is_file()
    project.json("export", "--prune", "--force")
    assert not (project.cwd / "game" / "audio" / "sfx").exists()
    assert next(backups(project)[0].rglob("clicks_3.ogg")).read_bytes() == GAMES


def test_a_manifest_that_lists_a_file_outside_both_folders_is_refused_by_prune(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    path = project.cwd / "game" / "kiripix" / "manifest" / f"{asset}.json"
    path.write_text(path.read_text("utf-8").replace(f"{RES}/clicks_1.ogg", "res://project.godot", 1), "utf-8")
    shutil.rmtree(project.cwd / "assets" / "sound" / "clicks")

    refused = project.json("export", "--prune", expect=1)

    assert refused["findings"][0]["code"] == "export.manifest_invalid"
    assert (project.cwd / "game" / "project.godot").is_file()


def test_the_sound_folder_is_a_setting(project: Kiripix) -> None:
    asset = built_sound(project)
    settings = project.cwd / "kiripix.toml"
    settings.write_text(settings.read_text("utf-8").replace('folder = "res://audio"', 'folder = "res://sfx_bank"'), "utf-8")
    project.json("run", asset)  # `export` reads the `[sound]` table; `process` only its `use` rows
    data = project.json("export", asset)["data"]

    assert data["written"] == [f"res://sfx_bank/sfx/clicks_{n}.ogg" for n in (1, 2, 3, 4)]
    assert (project.cwd / "game" / "sfx_bank" / "sfx" / "clicks_1.ogg").is_file()


def test_prune_removes_a_deleted_sounds_files_from_the_folder_it_was_exported_to(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    settings = project.cwd / "kiripix.toml"
    settings.write_text(settings.read_text("utf-8").replace('folder = "res://audio"', 'folder = "res://sfx_bank"'), "utf-8")
    shutil.rmtree(project.cwd / "assets" / "sound" / "clicks")

    data = project.json("export", "--prune")["data"]

    assert sorted(data["removed"]) == sorted(
        [f"{RES}/clicks_{n}.ogg" for n in (1, 2, 3, 4)] + ["res://kiripix/manifest/sound.clicks.json"])
    assert not (project.cwd / AUDIO / "clicks_1.ogg").exists()


def test_a_sound_folder_outside_the_game_is_refused(project: Kiripix) -> None:
    asset = built_sound(project)
    settings = project.cwd / "kiripix.toml"
    settings.write_text(settings.read_text("utf-8").replace('folder = "res://audio"', 'folder = "res://../elsewhere"'), "utf-8")

    project.json("run", asset)

    refused = project.json("export", asset, expect=1)

    assert refused["findings"][0]["code"] == "export.bad_sound_folder"
    assert not (project.cwd / "elsewhere").exists()


# the freeze


def test_the_sound_id_and_use_are_frozen_once_exported(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    toml = project.cwd / "assets" / "sound" / "clicks" / "asset.toml"
    original = toml.read_text("utf-8")

    toml.write_text(original.replace("[params]", '[params]\nsound_id = "sfx.renamed"', 1), "utf-8")
    renamed = project.json("check", asset, expect=2)
    refused = project.json("export", asset, expect=2)

    for result in (renamed, refused):
        [finding] = [f for f in result["findings"] if f["code"] == "export.id_frozen"]
        assert "sound ID 'sfx.clicks'" in finding["message"] and finding["owner_action"]
    toml.write_text(original.replace('use = "sfx"', 'use = "ui"'), "utf-8")
    reused = [f["message"] for f in project.json("check", asset, expect=2)["findings"] if f["code"] == "export.id_frozen"]
    assert any("use 'sfx'" in message for message in reused)
    toml.write_text(original, "utf-8")
    assert project.json("check", asset)["ok"] is True


def test_two_sounds_of_one_use_with_the_same_file_name_are_a_project_finding(project: Kiripix) -> None:
    project.json("new", "sound", "first", "--use", "sfx", "--sound-id", "sfx.footstep.asphalt")
    project.json("new", "sound", "second", "--use", "sfx", "--sound-id", "sfx.footstep_asphalt")
    project.json("new", "sound", "third", "--use", "ui", "--sound-id", "ui.footstep.asphalt")

    result = project.json("check", "--all", expect=2)

    [taken] = [f for f in result["findings"] if f["code"] == "sound.name_taken"]
    assert taken["position"]["asset"] == "sound.second" and "sound.first" in taken["message"] and taken["owner_action"]


# git


@needs_git
def test_manifest_install_writes_no_sound_rule_in_a_game_with_no_sound_folder(project: Kiripix) -> None:
    built_sound(project)
    init_game(project)

    result = project.json("manifest", "install")

    assert not (project.cwd / "game" / "audio").exists()
    assert not any("audio" in path for path in result["data"]["changed"])


@needs_git
def test_manifest_install_writes_the_ours_rule_for_ogg_into_the_sound_folder(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    init_game(project)

    result = project.json("manifest", "install")

    assert "res://audio/.gitattributes" in result["data"]["changed"]

    attributes = project.cwd / "game" / "audio" / ".gitattributes"
    assert attributes.read_text("utf-8") == "*.ogg merge=kiripix-ours\n"
    assert git(project.cwd / "game", "check-attr", "merge", "--", "audio/sfx/x.ogg").stdout.strip().endswith("merge: kiripix-ours")
    project.json("manifest", "install")
    assert attributes.read_text("utf-8") == "*.ogg merge=kiripix-ours\n"


@needs_git
def test_a_game_with_sounds_and_no_rule_gets_the_missing_driver_warning(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    init_game(project)
    project.json("manifest", "install")
    (project.cwd / "game" / "audio" / ".gitattributes").unlink()

    result = project.json("export", asset)

    assert "export.merge_driver_missing" in codes(result)


# the Manifest


def test_merge_takes_our_sound_block_with_our_files(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    ours = (project.cwd / "game" / "kiripix" / "manifest" / f"{asset}.json").read_text("utf-8")
    other = json.loads(ours)
    other["counter"] = 5
    other["files"][f"{RES}/clicks_1.ogg"] = "ff" * 32
    other["sound"]["source"]["licence"] = "theirs"
    (project.cwd / "ours.json").write_text(ours, "utf-8", newline="")
    (project.cwd / "theirs.json").write_text(json.dumps(other, indent=2) + "\n", "utf-8", newline="")
    (project.cwd / "base.json").write_text(ours, "utf-8", newline="")

    project.json("manifest", "merge", "base.json", "ours.json", "theirs.json")

    merged = json.loads((project.cwd / "ours.json").read_text("utf-8"))
    assert merged["counter"] == 6 and merged["schema_version"] == 5
    assert merged["sound"] == json.loads(ours)["sound"] and merged["sound"]["source"]["licence"] == LICENCE
    assert merged["files"] == json.loads(ours)["files"] and merged["replacing"] == {f"{RES}/clicks_1.ogg": "ff" * 32}


def test_a_schema_4_manifest_is_read_as_having_no_sound_block_and_rewritten_once(project: Kiripix) -> None:
    asset = built_sound(project)
    project.json("export", asset)
    path = project.cwd / "game" / "kiripix" / "manifest" / f"{asset}.json"
    old = json.loads(path.read_text("utf-8"))
    del old["sound"]
    old["schema_version"] = 4
    path.write_text(json.dumps(old, indent=2) + "\n", "utf-8")

    data = project.json("export", asset)["data"]

    assert data["written"] == [], "the files are the game's own bytes: only the Manifest is rewritten"
    assert manifest(project, asset)["schema_version"] == 5 and manifest(project, asset)["sound"]["id"] == "sfx.clicks"


# the founder's recording


@pytest.mark.skipif(not FOOTSTEPS.is_file(), reason="the founder's footsteps recording is not in the working tree")
def test_the_asphalt_recording_exports_four_oggs_at_minus_3_dbfs_mono_with_its_provenance(project: Kiripix) -> None:
    project.json("new", "sound", "asphalt", "--use", "sfx", "--sound-id", "sfx.footstep.asphalt")
    variant = str(project.json("import", "sound.asphalt", str(FOOTSTEPS), *PROVENANCE)["data"]["variant"])
    project.json("pick", "sound.asphalt", variant)
    run_slice(project, "sound.asphalt")
    best = sorted(takes(project, "sound.asphalt"), key=lambda r: int(str(r["clean_rank"])))[:4]
    kept_and_processed(project, ",".join(str(r["number"]) for r in best), "sound.asphalt")
    godot_project(project)
    set_target(project)
    project.json("run", "sound.asphalt", "export")

    data = project.json("export", "sound.asphalt")["data"]

    names = [f"res://audio/sfx/footstep_asphalt_{n}.ogg" for n in (1, 2, 3, 4)]
    assert sorted(data["written"]) == names
    sound = manifest(project, "sound.asphalt")["sound"]
    assert sound["source"]["url"] == URL and sound["source"]["author"] == AUTHOR and sound["source"]["licence"] == LICENCE
    for entry in sound["files"]:
        assert entry["peak_dbfs"] == pytest.approx(-3.0, abs=1.5)
        assert vorbis_channels((project.cwd / "game" / entry["path"].removeprefix("res://")).read_bytes()) == 1
    assert process_dir(project, "sound.asphalt").is_dir()
