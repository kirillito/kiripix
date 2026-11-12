"""`import --role sheet`: a sprite Asset's PNG sheets and ZIPs (ticket 0178), against the test Kind `sheeted`, which takes
sheets as the sprite Kind does."""

import io
import stat
import zipfile
from pathlib import Path

from PIL import Image

from conftest import Kiripix

SPRITE = "sheeted.npc"


def png_bytes(colour: tuple[int, int, int, int] = (255, 0, 77, 255), fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB" if fmt == "JPEG" else "RGBA", (4, 4), colour[:3] if fmt == "JPEG" else colour).save(buffer, fmt)
    return buffer.getvalue()


def make_zip(project: Kiripix, name: str, entries: dict[str, bytes], links: tuple[str, ...] = ()) -> Path:
    path = project.cwd / name
    with zipfile.ZipFile(path, "w") as archive:
        for entry, data in entries.items():
            archive.writestr(entry, data)
        for entry in links:
            info = zipfile.ZipInfo(entry)
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, "target.png")
    return path


def sprite(project: Kiripix) -> Path:
    project.json("new", "sheeted", "npc")
    return project.cwd / "assets" / "sheeted" / "npc"


def src_files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in (folder / "src").rglob("*")) if (folder / "src").exists() else []


def refused(project: Kiripix, folder: Path, file: str, entry: str | None = None, *extra: str) -> None:
    before = src_files(folder)
    result = project.json("import", SPRITE, file, "--role", "sheet", *extra, expect=1)
    finding = result["findings"][0]
    assert result["ok"] is False and finding["code"] == "import.sheet_invalid"
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    if entry is not None:
        assert entry in finding["message"]
    assert src_files(folder) == before
    assert not (folder / "imported.jsonl").exists()


def test_a_png_sheet_imports_by_its_hash_and_twice_is_one_sheet(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())

    data = project.json("import", SPRITE, "walk.png", "--role", "sheet")["data"]
    again = project.json("import", SPRITE, "walk.png", "--role", "sheet")["data"]

    assert data["role"] == "sheet" and data["created"] and not again["created"]
    assert data["variant"] is None and data["sheet"] == again["sheet"]
    assert data["file"] == f"assets/sheeted/npc/src/sheets/{data['sheet']}.png"
    assert data["sheets"] == [data["sheet"]]
    assert (folder / "src" / "sheets" / f"{data['sheet']}.png").read_bytes() == png_bytes()
    assert src_files(folder) == [f"src/sheets", f"src/sheets/{data['sheet']}.png"]


def test_a_zip_imports_unopened(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "walk.zip", {"walk/south/000.png": png_bytes(), "walk/south/001.png": png_bytes((1, 2, 3, 255)),
                                   "walk/": b""})

    data = project.json("import", SPRITE, "walk.zip", "--role", "sheet")["data"]

    assert data["file"].endswith(f"src/sheets/{data['sheet']}.zip")
    assert src_files(folder) == ["src/sheets", f"src/sheets/{data['sheet']}.zip"]
    assert (folder / "src" / "sheets" / f"{data['sheet']}.zip").read_bytes() == (project.cwd / "walk.zip").read_bytes()


def test_import_without_a_role_on_a_sprite_means_sheet(project: Kiripix) -> None:
    sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())

    data = project.json("import", SPRITE, "walk.png")["data"]

    assert data["role"] == "sheet" and data["sheet"]


def test_a_sprite_takes_no_variant_role(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())

    finding = project.json("import", SPRITE, "walk.png", "--role", "variant", expect=1)["findings"][0]

    assert finding["code"] == "import.sprite_takes_sheets"
    assert finding["fix"] == f"kiripix import {SPRITE} walk.png --role sheet"
    assert src_files(folder) == []


def test_a_sprite_takes_no_pick(project: Kiripix) -> None:
    sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())
    sheet = project.json("import", SPRITE, "walk.png")["data"]["sheet"]

    result = project.json("pick", SPRITE, sheet, expect=1)

    assert result["findings"][0]["code"] == "pick.no_stage"


def test_the_original_name_is_recorded(project: Kiripix) -> None:
    sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())
    make_zip(project, "run.zip", {"run/south/000.png": png_bytes()})
    project.json("import", SPRITE, "walk.png")
    project.json("import", SPRITE, "run.zip")

    sheets = project.json("show", SPRITE)["data"]["sheets"]

    assert {s["imported_as"] for s in sheets} == {"walk.png", "run.zip"}


def test_show_lists_each_sheet_with_its_size_and_a_zips_png_count(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())
    make_zip(project, "run.zip", {"run/south/000.png": png_bytes(), "run/south/001.png": png_bytes((1, 2, 3, 255)),
                                  "run/south/": b""})
    png = project.json("import", SPRITE, "walk.png")["data"]
    archive = project.json("import", SPRITE, "run.zip")["data"]

    shown = project.json("show", SPRITE)["data"]
    by_name = {s["name"]: s for s in shown["sheets"]}

    assert shown["variants"] == [] and shown["picked"] is None
    assert set(by_name) == {png["sheet"], archive["sheet"]}
    assert by_name[png["sheet"]] == {
        "name": png["sheet"], "file": png["file"], "imported_as": "walk.png", "size": len(png_bytes()),
        "png_count": None}
    assert by_name[archive["sheet"]]["size"] == (folder / "src" / "sheets" / f"{archive['sheet']}.zip").stat().st_size
    assert by_name[archive["sheet"]]["png_count"] == 2
    assert by_name[archive["sheet"]]["file"].endswith(".zip")


def test_a_sheet_is_a_stage_input(project: Kiripix) -> None:
    sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())
    project.json("import", SPRITE, "walk.png")

    project.json("run", SPRITE, "frames")

    assert {s["stage"]: s["status"] for s in project.json("status")["data"]["assets"][0]["stages"]} == {"frames": "done"}


def test_a_dotdot_entry_is_refused_whole(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"ok/south/000.png": png_bytes(), "ok/../../escape.png": png_bytes()})

    refused(project, folder, "evil.zip", "escape.png")


def test_a_dotdot_entry_with_backslashes_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"ok\\..\\..\\x.png": png_bytes()})

    refused(project, folder, "evil.zip", "x.png")


def test_an_absolute_path_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"ok/south/000.png": png_bytes(), "/etc/passwd.png": png_bytes()})

    refused(project, folder, "evil.zip", "/etc/passwd.png")


def test_a_drive_path_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"C:/windows/x.png": png_bytes()})

    refused(project, folder, "evil.zip", "C:/windows/x.png")


def test_a_link_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"ok/south/000.png": png_bytes()}, links=("ok/south/001.png",))

    refused(project, folder, "evil.zip", "ok/south/001.png")


def test_an_entry_that_is_not_a_png_by_its_bytes_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"ok/south/000.png": png_bytes(), "ok/south/001.png": png_bytes(fmt="JPEG")})

    refused(project, folder, "evil.zip", "ok/south/001.png")


def test_a_zip_with_a_text_entry_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    make_zip(project, "evil.zip", {"ok/south/000.png": png_bytes(), "notes.txt": b"hello"})

    refused(project, folder, "evil.zip", "notes.txt")


def test_a_zip_with_more_than_4096_entries_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    one = png_bytes()
    path = project.cwd / "many.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for number in range(4097):
            archive.writestr(f"walk/south/{number:05d}.png", one)

    refused(project, folder, "many.zip")


def test_a_zip_of_exactly_4096_entries_imports(project: Kiripix) -> None:
    sprite(project)
    one = png_bytes()
    with zipfile.ZipFile(project.cwd / "many.zip", "w") as archive:
        for number in range(4096):
            archive.writestr(f"walk/south/{number:05d}.png", one)

    data = project.json("import", SPRITE, "many.zip", "--role", "sheet")["data"]

    assert data["created"]
    assert project.json("show", SPRITE)["data"]["sheets"][0]["png_count"] == 4096


def test_a_zip_that_unpacks_to_more_than_256_mb_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    # A PNG that is mostly one long comment chunk of zeros: a few hundred KB zipped, 257 MB unpacked.
    big = png_bytes() + b"\x00" * (257 * 1024 * 1024)
    with zipfile.ZipFile(project.cwd / "bomb.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("walk/south/000.png", big)

    refused(project, folder, "bomb.zip", "walk/south/000.png")


def test_a_file_that_is_not_a_zip_but_is_named_one_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "broken.zip").write_bytes(b"PK\x03\x04 not really")

    refused(project, folder, "broken.zip")


def test_a_jpeg_renamed_png_is_refused(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "sheet.png").write_bytes(png_bytes(fmt="JPEG"))

    refused(project, folder, "sheet.png")


def test_a_missing_file_is_import_not_found(project: Kiripix) -> None:
    sprite(project)

    finding = project.json("import", SPRITE, "nowhere.png", "--role", "sheet", expect=1)["findings"][0]

    assert finding["code"] == "import.not_found"


def test_a_sheet_on_a_room_or_a_character_is_refused(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("new", "character", "hero")
    (project.cwd / "walk.png").write_bytes(png_bytes())

    for asset in ("room.alley", "character.hero"):
        finding = project.json("import", asset, "walk.png", "--role", "sheet", expect=1)["findings"][0]

        assert finding["code"] == "import.role_needs_sprite"
        assert finding["fix"] or finding["owner_action"]
    assert not (project.cwd / "assets" / "room" / "alley" / "src" / "sheets").exists()
    assert not (project.cwd / "assets" / "character" / "hero" / "src" / "sheets").exists()


def test_the_other_roles_on_a_sprite_are_refused(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "walk.png").write_bytes(png_bytes())

    for role in ("clip-source", "rigged"):
        finding = project.json("import", SPRITE, "walk.png", "--role", role, expect=1)["findings"][0]

        assert finding["code"] == "import.role_needs_character"
    assert src_files(folder) == []


def test_a_room_still_imports_a_variant_without_a_role(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    (project.cwd / "in.png").write_bytes(png_bytes())

    data = project.json("import", "room.alley", "in.png")["data"]

    assert data["role"] == "variant" and data["sheet"] is None and data["variant"]
