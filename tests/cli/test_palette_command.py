"""`kiripix palette` (ticket 0204): the Project palette's colours, in file order, read the way the Stages read it."""

from conftest import Kiripix

OTHER = 'GIMP Palette\nName: other\n# a comment\n  1   2   3\tdeep\n255 128   0\n 16 255 160\tmint\n'


def test_palette_lists_the_project_palette_in_file_order(project: Kiripix) -> None:
    text = (project.cwd / "style" / "palette.gpl").read_text(encoding="utf-8")
    result = project.json("palette")
    data = result["data"]
    assert result["ok"] is True and data["palette"] == "style/palette.gpl"
    colours = data["colours"]
    assert [c["index"] for c in colours] == list(range(len(colours)))
    assert colours[0] == {"index": 0, "hex": "#000000", "name": "black"}
    assert all(len(c["hex"]) == 7 and c["hex"] == c["hex"].lower() for c in colours)
    assert len(colours) == len([ln for ln in text.splitlines() if ln[:1].isspace() or ln[:1].isdigit()])
    assert any(c["name"] == "red" and c["hex"] == "#ff004d" for c in colours)


def test_palette_follows_the_palette_setting(project: Kiripix) -> None:
    (project.cwd / "style" / "other.gpl").write_text(OTHER, encoding="utf-8")
    toml = project.cwd / "kiripix.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace('"style/palette.gpl"', '"style/other.gpl"'), encoding="utf-8")
    data = project.json("palette")["data"]
    assert data["palette"] == "style/other.gpl"
    assert data["colours"] == [
        {"index": 0, "hex": "#010203", "name": "deep"},
        {"index": 1, "hex": "#ff8000", "name": None},
        {"index": 2, "hex": "#10ffa0", "name": "mint"},
    ]


def test_palette_text_is_one_line_per_colour(project: Kiripix) -> None:
    count = len(project.json("palette")["data"]["colours"])
    out = project("palette")
    assert out.code == 0 and "#ff004d" in out.stdout
    assert len([ln for ln in out.stdout.splitlines() if ln.strip().startswith(tuple("0123456789"))]) == count


def test_a_missing_palette_is_refused_with_a_finding(project: Kiripix) -> None:
    (project.cwd / "style" / "palette.gpl").unlink()
    result = project.json("palette", expect=1)
    assert result["ok"] is False
    finding = result["findings"][0]
    assert finding["code"] == "palette.not_found"
    assert (finding.get("fix") is None) != (finding.get("owner_action") is None)
