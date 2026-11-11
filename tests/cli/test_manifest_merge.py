"""The Manifest merge driver, `manifest install` and `manifest repair` (spec §9, ADR 0003, ticket 0049).

The merge is also run by a real `git merge` in a temporary repo; those tests skip when git is missing."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix
from PIL import Image
from test_export import MANIFEST, exportable_room
from test_export_ownership import put
from test_masks import ROOM, plate
from test_place import findings

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git isn't installed")

MANIFEST_RES = "res://kiripix/manifest/room.alley.json"
ATTRIBUTES = "game/kiripix/manifest/.gitattributes"
MISSING = "export.merge_driver_missing"
TSCN = "res://kiripix/room/alley/alley.tscn"


def git(folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.autocrlf=false", "-C", str(folder),
         *args],
        capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, check=False,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})


def init_game(project: Kiripix) -> Path:
    """The game's folder as a git repository (its own clone, apart from the Project)."""
    game = project.cwd / "game"
    assert git(game, "init", "-b", "main").returncode == 0
    git(game, "config", "core.autocrlf", "false")
    return game


def manifest_text(counter: int = 1, markers: tuple[str, ...] = ("spawn.main",), files: dict[str, str] | None = None,
                  **extra: Any) -> str:
    value: dict[str, Any] = {
        "schema_version": 2, "kiripix_version": "0.1.0", "asset": "room.alley", "exported": True, "counter": counter,
        "ids": {"markers": list(markers), "layers": [], "masks": ["solid"], "clips": []},
        "files": files if files is not None else {TSCN: "sha256:aa"}, **extra}
    return json.dumps(value, indent=2) + "\n"


def sides(folder: Path, ours: str, theirs: str, base: str = "") -> list[str]:
    for name, text in (("base.json", base), ("ours.json", ours), ("theirs.json", theirs)):
        (folder / name).write_text(text, "utf-8", newline="")
    return ["manifest", "merge", "base.json", "ours.json", "theirs.json"]


# the rule


def test_the_merge_takes_the_higher_counter_plus_one_and_the_union_of_the_ids(kpx: Kiripix) -> None:
    ours = manifest_text(2, ("spawn.main", "spawn.a"))
    theirs = manifest_text(3, ("spawn.main", "spawn.b"))

    result = kpx.json(*sides(kpx.cwd, ours, theirs))

    merged = json.loads((kpx.cwd / "ours.json").read_text("utf-8"))
    assert merged["counter"] == 4 and result["data"]["counter"] == 4 and result["data"]["asset"] == "room.alley"
    assert merged["ids"]["markers"] == ["spawn.main", "spawn.a", "spawn.b"]
    assert merged["exported"] is True


def test_exported_is_either_and_files_are_ours_with_theirs_in_replacing(kpx: Kiripix) -> None:
    png, extra = "res://kiripix/room/alley/plate.png", "res://x/only.png"
    ours = json.loads(manifest_text(1, files={TSCN: "sha256:ours", png: "sha256:same"}))
    ours["exported"] = False
    theirs = json.loads(manifest_text(1, files={TSCN: "sha256:theirs", png: "sha256:same", extra: "sha256:t"}))

    kpx.json(*sides(kpx.cwd, json.dumps(ours), json.dumps(theirs)))

    merged = json.loads((kpx.cwd / "ours.json").read_text("utf-8"))
    assert merged["exported"] is True
    assert merged["files"] == {TSCN: "sha256:ours", png: "sha256:same", extra: "sha256:t"}
    assert merged["replacing"] == {TSCN: "sha256:theirs"}
    assert merged["schema_version"] == 2


def test_the_merge_needs_no_project_and_is_byte_stable(kpx: Kiripix) -> None:
    arguments = sides(kpx.cwd, manifest_text(1), manifest_text(2, ("spawn.main", "spawn.b")))

    kpx.json(*arguments)
    first = (kpx.cwd / "ours.json").read_bytes()
    (kpx.cwd / "ours.json").write_text(manifest_text(1), "utf-8", newline="")
    kpx.json(*arguments)

    assert (kpx.cwd / "ours.json").read_bytes() == first and b"\r" not in first
    assert not (kpx.cwd / ".kiripix").exists()


def test_a_missing_base_is_fine(kpx: Kiripix) -> None:
    arguments = sides(kpx.cwd, manifest_text(1), manifest_text(1))
    (kpx.cwd / "base.json").unlink()

    kpx.json(*arguments)


@pytest.mark.parametrize("broken", [
    "not json at all",
    '{"schema_version": 1}',
    manifest_text().replace('"schema_version": 2', '"schema_version": 3'),
    manifest_text().replace("room.alley", "room.other"),
    "",
])
def test_an_unreadable_theirs_exits_1_and_leaves_ours_unchanged(kpx: Kiripix, broken: str) -> None:
    arguments = sides(kpx.cwd, manifest_text(5), broken)

    result = kpx.json(*arguments, expect=1)

    assert (kpx.cwd / "ours.json").read_text("utf-8") == manifest_text(5)
    [finding] = result["findings"]
    assert finding["code"] == "manifest.merge_unreadable" and finding["fix"] is None and finding["owner_action"]


def test_an_unreadable_ours_exits_1_and_leaves_it_unchanged(kpx: Kiripix) -> None:
    arguments = sides(kpx.cwd, "<<<<<<< oops\n", manifest_text())

    kpx.json(*arguments, expect=1)

    assert (kpx.cwd / "ours.json").read_text("utf-8") == "<<<<<<< oops\n"


def test_a_newer_schema_version_is_named(kpx: Kiripix) -> None:
    newer = manifest_text().replace('"schema_version": 2', '"schema_version": 3')

    result = kpx.json(*sides(kpx.cwd, manifest_text(), newer), expect=1)

    assert "newer" in result["findings"][0]["message"] and "upgrade" in result["findings"][0]["message"]


def test_a_version_1_manifest_is_migrated_with_no_clips_and_the_merge_unions_the_clips(kpx: Kiripix) -> None:
    old = json.loads(manifest_text(2))
    old["schema_version"] = 1
    del old["ids"]["clips"]
    new = json.loads(manifest_text(3))
    new["ids"]["clips"] = ["idle_s", "walk_s"]
    other = json.loads(manifest_text(3))
    other["ids"]["clips"] = ["attack_s", "idle_s"]

    kpx.json(*sides(kpx.cwd, json.dumps(old), json.dumps(new)))
    migrated = json.loads((kpx.cwd / "ours.json").read_text("utf-8"))
    assert migrated["schema_version"] == 2 and migrated["ids"]["clips"] == ["idle_s", "walk_s"]

    kpx.json(*sides(kpx.cwd, json.dumps(new), json.dumps(other)))
    merged = json.loads((kpx.cwd / "ours.json").read_text("utf-8"))
    assert merged["ids"]["clips"] == ["idle_s", "walk_s", "attack_s"]


def test_a_version_1_manifest_is_migrated_with_no_clips_and_the_merge_unions_the_clips(kpx: Kiripix) -> None:
    old = json.loads(manifest_text(2))
    old["schema_version"] = 1
    del old["ids"]["clips"]
    new = json.loads(manifest_text(3))
    new["ids"]["clips"] = ["idle_s", "walk_s"]
    other = json.loads(manifest_text(3))
    other["ids"]["clips"] = ["attack_s", "idle_s"]

    kpx.json(*sides(kpx.cwd, json.dumps(old), json.dumps(new)))
    migrated = json.loads((kpx.cwd / "ours.json").read_text("utf-8"))
    assert migrated["schema_version"] == 2 and migrated["ids"]["clips"] == ["idle_s", "walk_s"]

    kpx.json(*sides(kpx.cwd, json.dumps(new), json.dumps(other)))
    merged = json.loads((kpx.cwd / "ours.json").read_text("utf-8"))
    assert merged["ids"]["clips"] == ["idle_s", "walk_s", "attack_s"]


def test_a_missing_file_exits_1(kpx: Kiripix) -> None:
    kpx.json("manifest", "merge", "a.json", "b.json", "c.json", expect=1)


# a real git merge


def two_branches(project: Kiripix, driver: bool, images: bool = False) -> Path:
    """A game repo with room.alley exported on `main`, then branches `a` and `b` that each export it again with another
    Spawn. With `images`, branch `a` also exports a different Plate (the rug in another colour), and so does `b`, in a third. Returns the game folder,
    on branch `b`."""
    exportable_room(project)
    game = init_game(project)
    if driver:
        project.json("manifest", "install")
    project.json("export", "room.alley")
    git(game, "add", "-A")
    assert git(game, "commit", "-m", "base").returncode == 0
    git(game, "checkout", "-q", "-b", "a")
    put(project, ROOM, "spawn.a", "spawn", at=(36, 16))
    if images:
        other = plate()
        other[8:14, 24:36] = (200, 30, 160, 255)
        Image.fromarray(other, "RGBA").save(project.cwd / "other.png")
        project.json("pick", ROOM, str(project.json("import", ROOM, "other.png")["data"]["variant"]))
        project.json("run", ROOM, expect=3)
        project.json("accept", ROOM, "masks", owner=True)  # the clicks were replayed onto a changed image
    project.json("run", ROOM)
    project.json("export", "room.alley")
    git(game, "add", "-A")
    assert git(game, "commit", "-m", "a").returncode == 0
    git(game, "checkout", "-q", "main")
    git(game, "checkout", "-q", "-b", "b")
    project.json("undo", ROOM, "place")
    if images:
        third = plate()
        third[8:14, 24:36] = (20, 200, 60, 255)  # a third Plate: both branches change the image from the base
        Image.fromarray(third, "RGBA").save(project.cwd / "again.png")
        project.json("pick", ROOM, str(project.json("import", ROOM, "again.png")["data"]["variant"]))
        project.json("run", ROOM, expect=3)
        project.json("accept", ROOM, "masks", owner=True)
    put(project, ROOM, "spawn.b", "spawn", at=(38, 16))
    project.json("run", ROOM)
    project.json("export", "room.alley")
    git(game, "add", "-A")
    assert git(game, "commit", "-m", "b").returncode == 0
    return game


@needs_git
def test_a_real_git_merge_with_the_driver_merges_the_manifest_without_conflict(project: Kiripix) -> None:
    game = two_branches(project, driver=True)
    assert json.loads((project.cwd / MANIFEST).read_text("utf-8"))["counter"] == 2

    done = git(game, "merge", "a", "-m", "merge")

    unmerged = git(game, "ls-files", "-u").stdout
    assert "manifest/room.alley.json" not in unmerged, done.stdout + done.stderr
    text = (project.cwd / MANIFEST).read_text("utf-8")
    assert "<<<<<<<" not in text
    merged = json.loads(text)
    assert merged["counter"] == 3  # both were 2: the higher + 1
    assert {"spawn.main", "spawn.a", "spawn.b"} <= set(merged["ids"]["markers"])
    # the scene and images differ on the two branches too: the `merge=kiripix-ours` rules keep ours, no conflict
    assert unmerged == "", unmerged
    assert git(game, "status", "--porcelain").stdout.strip() == ""
    # the next export is clean: nothing refused, and the files are the ones the Manifest accepts
    put(project, ROOM, "spawn.a", "spawn", at=(36, 16))  # the Project has both branches' Markers, as after a merge
    project.json("run", ROOM)
    again = project.json("export", "room.alley")
    assert again["ok"] is True and not [f for f in again["findings"] if f["severity"] == "error"]


@needs_git
def test_a_merge_of_two_different_exported_images_keeps_ours_and_the_next_export_is_clean(project: Kiripix) -> None:
    game = two_branches(project, driver=True, images=True)
    png = "kiripix/room/alley/plate.png"
    on_a = subprocess.run(["git", "-C", str(game), "show", f"a:{png}"], capture_output=True, check=True).stdout
    on_b = (project.cwd / "game" / png).read_bytes()
    assert on_a != on_b  # the two branches exported different images

    done = git(game, "merge", "a", "-m", "merge")

    assert git(game, "ls-files", "-u").stdout == "", done.stdout + done.stderr
    assert (project.cwd / "game" / png).read_bytes() == on_b  # ours
    put(project, ROOM, "spawn.a", "spawn", at=(36, 16))
    project.json("run", ROOM)
    again = project.json("export", "room.alley")
    assert again["ok"] is True and not [f for f in again["findings"] if f["severity"] == "error"]


@needs_git
def test_without_the_driver_the_same_merge_conflicts_in_the_manifest(project: Kiripix) -> None:
    game = two_branches(project, driver=False)

    git(game, "merge", "a", "-m", "merge")

    assert "manifest/room.alley.json" in git(game, "ls-files", "-u").stdout
    assert "<<<<<<<" in (project.cwd / MANIFEST).read_text("utf-8")
    # committed with the markers (a pull request on GitHub): export refuses, and `manifest repair` merges it
    refused = project.json("export", "room.alley", expect=1)
    assert "export.manifest_conflicted" in [f["code"] for f in refused["findings"]]
    repaired = project.json("manifest", "repair")
    assert repaired["data"]["repaired"] == [MANIFEST_RES]
    merged = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    assert merged["counter"] == 3 and {"spawn.a", "spawn.b"} <= set(merged["ids"]["markers"])


# export's warning, and install


@needs_git
def test_export_warns_without_the_driver_and_its_fix_installs_it(project: Kiripix) -> None:
    exportable_room(project)
    init_game(project)

    [warning] = findings(project.json("export", "room.alley"), MISSING)

    assert warning["severity"] == "warning" and warning["fix"] == "kiripix manifest install"
    assert warning["owner_action"] is None
    installed = project.json("manifest", "install")
    assert "git config" in installed["data"]["changed"]
    again = project.json("export", "room.alley")
    assert again["findings"] == []
    assert "merge=kiripix-manifest" in (project.cwd / ATTRIBUTES).read_text("utf-8")


@needs_git
def test_gitattributes_alone_still_warns(project: Kiripix) -> None:
    exportable_room(project)
    init_game(project)
    (project.cwd / ATTRIBUTES).parent.mkdir(parents=True)
    (project.cwd / ATTRIBUTES).write_text("*.json merge=kiripix-manifest\n", "utf-8")

    result = project.json("export", "room.alley")

    assert [f["code"] for f in result["findings"]] == [MISSING]


@needs_git
def test_the_manifest_rules_without_the_image_rules_still_warn(project: Kiripix) -> None:
    exportable_room(project)
    game = init_game(project)
    project.json("manifest", "install")
    (project.cwd / "game/kiripix/.gitattributes").unlink()

    [warning] = findings(project.json("export", "room.alley"), MISSING)

    assert warning["fix"] == "kiripix manifest install"
    assert git(game, "config", "--get", "merge.kiripix-ours.driver").stdout.strip() == "true"
    project.json("manifest", "install")
    assert project.json("export", "room.alley")["findings"] == []


@needs_git
def test_the_config_alone_still_warns(project: Kiripix) -> None:
    exportable_room(project)
    game = init_game(project)
    git(game, "config", "merge.kiripix-manifest.driver", "echo %O %A %B")

    assert [f["code"] for f in project.json("export", "room.alley")["findings"]] == [MISSING]


def test_export_says_nothing_when_the_game_isnt_a_git_repo(project: Kiripix) -> None:
    exportable_room(project)

    assert project.json("export", "room.alley")["findings"] == []


@needs_git
def test_export_says_nothing_when_git_is_missing(project: Kiripix, monkeypatch: pytest.MonkeyPatch) -> None:
    exportable_room(project)
    init_game(project)
    monkeypatch.setenv("PATH", str(project.cwd))  # a folder without git

    assert project.json("export", "room.alley")["findings"] == []


@needs_git
def test_install_is_idempotent_and_keeps_the_games_own_attributes(project: Kiripix) -> None:
    exportable_room(project)
    init_game(project)
    (project.cwd / ATTRIBUTES).parent.mkdir(parents=True)
    (project.cwd / ATTRIBUTES).write_text("*.png binary", "utf-8", newline="")

    first = project.json("manifest", "install")
    second = project.json("manifest", "install")

    assert first["data"]["changed"] and second["data"]["changed"] == []
    assert (project.cwd / ATTRIBUTES).read_text("utf-8") == "*.png binary\n*.json merge=kiripix-manifest\n"


def test_install_refuses_outside_a_git_repo(project: Kiripix) -> None:
    exportable_room(project)

    finding = project.json("manifest", "install", expect=1)["findings"][0]

    assert finding["code"] == "manifest.not_git" and finding["owner_action"] and finding["fix"] is None
    assert not (project.cwd / ATTRIBUTES).exists()


def test_install_and_repair_refuse_without_the_game(project: Kiripix) -> None:
    assert project.json("manifest", "install", expect=3)["findings"][0]["code"] == "export.no_target"
    assert project.json("manifest", "repair", expect=3)["findings"][0]["code"] == "export.no_target"


# repair


def conflicted(ours: str, theirs: str, base: str | None = None) -> str:
    """Git's conflict markers around the lines where two Manifests differ (they differ in one line)."""
    a, b = ours.splitlines(keepends=True), theirs.splitlines(keepends=True)
    start = next(i for i, (x, y) in enumerate(zip(a, b, strict=False)) if x != y)
    middle = f"||||||| base\n{base}" if base else ""
    return ("".join(a[:start]) + "<<<<<<< HEAD\n" + a[start] + middle + "=======\n" + b[start] + ">>>>>>> other\n"
            + "".join(a[start + 1:]))


def test_export_refuses_a_manifest_with_conflict_markers_and_repair_fixes_it(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", "room.alley")
    now = (project.cwd / MANIFEST).read_text("utf-8")
    ours = now.replace('"counter": 1', '"counter": 4')
    theirs = now.replace('"counter": 1', '"counter": 6')
    (project.cwd / MANIFEST).write_text(conflicted(ours, theirs, '  "counter": 1,\n'), "utf-8", newline="")

    refused = project.json("export", "room.alley", expect=1)

    [finding] = refused["findings"]
    assert finding["code"] == "export.manifest_conflicted" and finding["fix"] == "kiripix manifest repair"
    assert "room.alley.json" in finding["message"]
    repaired = project.json("manifest", "repair")
    assert repaired["data"]["repaired"] == [MANIFEST_RES]
    assert json.loads((project.cwd / MANIFEST).read_text("utf-8"))["counter"] == 7
    exported = project.json("export", "room.alley")
    assert exported["ok"] is True
    assert json.loads((project.cwd / MANIFEST).read_text("utf-8"))["counter"] == 7  # the files are what it lists


def test_repair_leaves_a_manifest_without_markers_alone(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", "room.alley")
    before = (project.cwd / MANIFEST).read_bytes()

    result = project.json("manifest", "repair")

    assert result["data"]["repaired"] == [] and (project.cwd / MANIFEST).read_bytes() == before


def test_repair_refuses_all_when_one_cant_be_repaired(project: Kiripix) -> None:
    exportable_room(project)
    project.json("export", "room.alley")
    good = (project.cwd / MANIFEST).read_text("utf-8")
    broken = project.cwd / "game/kiripix/manifest/room.street.json"
    broken.write_text("<<<<<<< HEAD\nnot json\n=======\nalso not\n>>>>>>> x\n", "utf-8", newline="")
    (project.cwd / MANIFEST).write_text(
        conflicted(good, good.replace('"counter": 1', '"counter": 2')), "utf-8", newline="")
    before = (project.cwd / MANIFEST).read_bytes()

    result = project.json("manifest", "repair", expect=1)

    assert result["findings"][0]["code"] == "manifest.merge_unreadable"
    assert "room.street.json" in result["findings"][0]["message"]
    assert (project.cwd / MANIFEST).read_bytes() == before
