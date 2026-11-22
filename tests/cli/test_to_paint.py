"""`kiripix to-paint` (ticket 0349): every prompt and canvas a district needs, in one folder, and nothing recorded."""

from pathlib import Path
from typing import Any

from conftest import Kiripix
from PIL import Image
from test_extend import CANVAS, ROOM, canvas, room, save

TEMPLATE = "A {{ view }}-view room, {{ width }}x{{ height }} px. {{ mood }}.\n"


def template(project: Kiripix) -> None:
    (project.cwd / "style" / "prompts" / "room.j2").write_text(TEMPLATE, encoding="utf-8", newline="\n")


def brief(project: Kiripix, asset: str, run: bool = True, width: int = 400, height: int = 240) -> None:
    project.json("set", asset, "brief", f"width={width}", f"height={height}", f"mood={asset.split('.')[1]}")
    if run:
        project.json("run", asset, "brief")


def district(project: Kiripix) -> dict[str, Any]:
    """The alley mid-`extend` (an east piece joined, 400x160 of the 400x240 the brief wants), the cellar with no Source,
    the dock with a picked Source."""
    template(project)
    full = room(project)
    brief(project, ROOM)
    canvas(project, "east", "--keep", "80")
    project.json("extend", ROOM, "add", save(project, "east.png", full[:160, 160:400]))
    project.json("new", "room", "cellar", "--view", "top")
    brief(project, "room.cellar")
    project.json("new", "room", "dock", "--view", "top")
    brief(project, "room.dock")
    variant = project.json("import", "room.dock", save(project, "dock.png", full))["data"]["variant"]
    project.json("pick", "room.dock", variant)
    return full


def tree(project: Kiripix) -> dict[str, bytes]:
    """Every file the Project commits or a Command writes in an Asset folder, and the settings and style."""
    found = {}
    for top in ("assets", "style"):
        for path in sorted((project.cwd / top).rglob("*")):
            if path.is_file():
                found[path.relative_to(project.cwd).as_posix()] = path.read_bytes()
    found["kiripix.toml"] = (project.cwd / "kiripix.toml").read_bytes()
    return found


def test_a_district_gives_a_prompt_a_canvas_and_an_index_with_the_return_names(project: Kiripix) -> None:
    district(project)

    result = project.json("to-paint", "--match", "room.*", "--out", "paint")["data"]

    folder = project.cwd / "paint"
    assert sorted(p.name for p in folder.iterdir()) == [
        "01-alley.prompt.txt", "01-alley.south.png", "02-cellar.prompt.txt", "index.md"]
    assert [(r["asset"], r["what"], r["return_name"]) for r in result["rooms"]] == [
        ("room.alley", "canvas", "alley.south.png"), ("room.cellar", "prompt", "cellar.png")]
    assert (folder / "02-cellar.prompt.txt").read_text(encoding="utf-8") == "A top-view room, 400x240 px. cellar.\n"
    with Image.open(folder / "01-alley.south.png") as image:
        assert image.size == CANVAS
    index = (folder / "index.md").read_text(encoding="utf-8")
    assert "`alley.south.png`" in index and "`cellar.png`" in index and "room.dock" not in index
    assert "\r" not in index and result["unready"] == []


def test_nothing_in_the_project_changes(project: Kiripix) -> None:
    district(project)
    before, status = tree(project), project.json("status")["data"]

    project.json("to-paint", "--match", "room.*")

    assert tree(project) == before
    assert project.json("status")["data"] == status
    assert list((project.cwd / ".kiripix" / "to-paint").glob("*/index.md"))  # the default folder, by date


def test_a_second_run_writes_the_same_files(project: Kiripix) -> None:
    district(project)
    project.json("to-paint", "--match", "room.*", "--out", "one")
    project.json("to-paint", "--match", "room.*", "--out", "two")

    for path in (project.cwd / "one").iterdir():
        assert path.read_bytes() == (project.cwd / "two" / path.name).read_bytes()


def test_a_room_with_no_brief_is_listed_under_no_brief_yet_with_the_command(project: Kiripix) -> None:
    template(project)
    project.json("new", "room", "cellar", "--view", "top")

    result = project.json("to-paint", "--match", "room.*", "--out", "paint")

    assert result["data"]["rooms"] == []
    assert result["data"]["unready"][0]["fix"] == "kiripix run room.cellar brief"
    assert result["findings"][0]["code"] == "to_paint.no_brief" and result["findings"][0]["fix"]
    index = (project.cwd / "paint" / "index.md").read_text(encoding="utf-8")
    assert "## No brief yet" in index and "kiripix run room.cellar brief" in index
    assert [p.name for p in (project.cwd / "paint").iterdir()] == ["index.md"]


def test_a_brief_out_of_date_is_no_brief_yet(project: Kiripix) -> None:
    template(project)
    project.json("new", "room", "cellar", "--view", "top")
    brief(project, "room.cellar")
    project.json("set", "room.cellar", "brief", "mood=changed")

    result = project.json("to-paint", "--match", "room.*", "--out", "paint")["data"]

    assert [u["code"] for u in result["unready"]] == ["to_paint.no_brief"]
    assert not list((project.cwd / "paint").glob("*.prompt.txt"))


def test_a_brief_without_a_prompt_template_says_so_and_the_owner_adds_one(project: Kiripix) -> None:
    project.json("new", "room", "cellar", "--view", "top")
    brief(project, "room.cellar")

    result = project.json("to-paint", "--match", "room.*", "--out", "paint")

    assert [u["code"] for u in result["data"]["unready"]] == ["to_paint.no_prompt"]
    assert result["findings"][0]["owner_action"] and result["findings"][0]["fix"] is None


def test_a_joined_image_as_big_as_the_brief_says_to_finish_with_done(project: Kiripix) -> None:
    template(project)
    full = room(project)
    brief(project, ROOM, width=400, height=160)
    canvas(project, "east", "--keep", "80")
    project.json("extend", ROOM, "add", save(project, "east.png", full[:160, 160:400]))

    result = project.json("to-paint", "--match", "room.*", "--out", "paint")["data"]

    [only] = result["rooms"]
    assert only["what"] == "done" and only["next"] == "kiripix extend room.alley done" and only["files"] == []
    assert not list(Path(project.cwd / "paint").glob("*.png"))


def test_a_glob_that_matches_nothing_is_match_none(project: Kiripix) -> None:
    result = project.json("to-paint", "--match", "zz*", "--out", "paint", expect=1)

    assert result["findings"][0]["code"] == "match.none"


def test_assets_that_are_not_rooms_are_left_out_with_an_info_finding(project: Kiripix) -> None:
    project.json("new", "prop", "bench")

    result = project.json("to-paint", "--match", "prop.*", "--out", "paint")

    assert result["data"]["rooms"] == [] and result["findings"][0]["code"] == "to_paint.not_a_room"
    assert result["data"]["index"] is None and not (project.cwd / "paint").exists()
