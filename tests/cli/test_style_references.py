"""Style references and the style Checks in `check` (ticket 0334, trial 0332): `[style] references` in kiripix.toml, the
owner-only `style-add` and `style-remove`, `style.outline_density` and `style.pixel_scale` against the references, and
`probe style`. Sprites on tiny synthetic sheets (see test_sprite.py): no Blender and no Runner."""

from typing import Any

from conftest import Kiripix
from test_sprite import FOUR, new_sprite, png_sheet, sheet_of


def sprite(project: Kiripix, name: str, outline: bool = True) -> str:
    """A built sprite: its figure is drawn with a 1 px outline round it, or with none."""
    asset = f"sprite.{name}"
    new_sprite(project, name)
    png_sheet(project, sheet_of(FOUR, 1), 1, asset=asset, file=f"{name}.png")
    project.json("set", asset, "finish", f"outline={'true' if outline else 'false'}", "placement=outside")
    project.json("run", asset)
    return asset


def codes(result: dict[str, Any], asset: str | None = None) -> list[str]:
    return sorted(f["code"] for f in result["findings"]
                  if f["code"].startswith("style.") and (asset is None or (f.get("position") or {}).get("asset") == asset))


def toml(project: Kiripix) -> str:
    return (project.cwd / "kiripix.toml").read_text(encoding="utf-8")


def test_an_older_settings_file_migrates_in_memory_and_gains_the_style_section(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = toml(project)
    assert "schema_version = 14" in text and "[style]" in text
    block = text[text.index("[style]"):].split("\n\n", 1)[0]
    old = text.replace("schema_version = 14", "schema_version = 10").replace(block + "\n\n", "")
    assert "[style]" not in old
    path.write_text(old, encoding="utf-8")

    assert project.json("status")["ok"]
    assert path.read_text(encoding="utf-8") == old  # migrated in memory only

    project.json("new", "prop", "bench")
    project.json("style-add", "prop.bench", owner=True)  # a writing Command writes the migration back

    written = toml(project)
    assert "schema_version = 14" in written and 'references = ["prop.bench"]' in written


def test_an_unknown_reference_is_a_finding_in_check_all_and_style_remove_takes_it_out(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    path.write_text(toml(project).replace("references = []", 'references = ["room.nowhere", "demo.a"]'), encoding="utf-8")
    project.json("new", "demo", "a")

    result = project.json("check", "--all", expect=2)

    found = [f for f in result["findings"] if f["code"] == "style.reference_unknown"]
    assert len(found) == 2 and all(f["severity"] == "error" for f in found)
    assert all((f["fix"] is None) != (f["owner_action"] is None) for f in found)
    assert {"room.nowhere", "demo.a"} == {n for f in found for n in ("room.nowhere", "demo.a") if n in f["message"]}

    project.json("style-remove", "room.nowhere", owner=True)  # an entry that names no Asset goes too
    project.json("style-remove", "demo.a", owner=True)
    assert "references = []" in toml(project)
    assert "style.reference_unknown" not in codes(project.json("check", "--all"))


def test_style_add_is_owner_only_and_writes_the_list_keeping_comments(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    project.json("new", "demo", "a")

    refused = project.json("style-add", "prop.bench", expect=3)
    assert refused["findings"] and "references = []" in toml(project)

    added = project.json("style-add", "prop.bench", owner=True)["data"]
    again = project.json("style-add", "prop.bench", owner=True)["data"]
    assert added["changed"] is True and added["references"] == ["prop.bench"]
    assert again["changed"] is False and again["references"] == ["prop.bench"]
    text = toml(project)
    assert 'references = ["prop.bench"]' in text and "`kiripix style-add <id>`" in text  # the comment stayed

    unsupported = project.json("style-add", "demo.a", owner=True, expect=1)
    assert unsupported["findings"][0]["code"] == "style.reference_unknown"
    unknown = project.json("style-add", "room.nowhere", owner=True, expect=1)
    assert unknown["findings"][0]["code"] == "style.reference_unknown"

    removed = project.json("style-remove", "prop.bench", owner=True)["data"]
    assert removed["changed"] is True and removed["references"] == []
    assert project.json("style-remove", "prop.bench", owner=True)["data"]["changed"] is False


def test_style_remove_from_a_session_is_refused(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    project.json("style-add", "prop.bench", owner=True)

    project.json("style-remove", "prop.bench", expect=3)

    assert 'references = ["prop.bench"]' in toml(project)


def test_a_sprite_drawn_without_an_outline_gets_the_warning_against_two_that_have_one(project: Kiripix) -> None:
    first, second = sprite(project, "a"), sprite(project, "b")
    odd = sprite(project, "c", outline=False)
    assert codes(project.json("check", odd)) == []  # no references: nothing runs and nothing is reported
    waiting = "prop.bench"
    project.json("new", "prop", "bench")
    project.json("style-add", waiting, owner=True)
    only_unbuilt = project.json("check", odd)  # a reference that isn't built is left out, and nothing is left to measure against
    unbuilt = [f for f in only_unbuilt["findings"] if f["code"] == "style.reference_unbuilt"]
    assert len(unbuilt) == 1 and unbuilt[0]["severity"] == "info" and unbuilt[0]["position"]["asset"] == waiting
    assert unbuilt[0]["fix"] == f"kiripix run {waiting} export" and "style.outline_density" not in codes(only_unbuilt, odd)
    project.json("style-add", first, owner=True)
    project.json("style-add", second, owner=True)

    one = project.json("check", odd)
    everything = project.json("check", "--all")

    for result in (one, everything):
        assert codes(result, odd) == ["style.measures", "style.outline_density"]
        warning = next(f for f in result["findings"] if f["code"] == "style.outline_density")
        assert warning["severity"] == "warning" and warning["fix"] == f"kiripix set {odd} finish outline=true"
        assert warning["owner_action"] is None and warning["position"]["stage"] == "finish"
        assert warning["data"]["density"] == 0.0 and warning["data"]["references_low"] >= 1.0
        assert warning["data"]["furthest"] in (first, second)
    assert codes(project.json("check", first), first) == ["style.measures"]  # in range: the numbers only
    assert codes(everything, first) == ["style.measures"] and codes(everything, second) == ["style.measures"]
    matched = project.json("check", "--match", "sprite.c")
    assert codes(matched, odd) == ["style.measures", "style.outline_density"] and codes(matched, first) == []

    data = project.json("probe", "style", odd)["data"]["result"]  # what the UI reads (ticket 0335)
    assert data["asset"] == odd and data["kind"] == "sprite" and data["stage"] == "finish" and data["built"] is True
    assert data["measures"]["outline_density"]["density"] == 0.0 and data["measures"]["pixel_scale"]["gcd"] >= 1
    assert [r["asset"] for r in data["references"]] == [waiting, first, second]
    assert [r["built"] for r in data["references"]] == [False, True, True]
    assert data["references"][1]["measures"]["outline_density"]["density"] >= 1.0
    spread = data["range"]["outline_density"]
    assert spread["low"] >= 1.0 and spread["high"] >= spread["low"] and spread["furthest"] in (first, second)
    assert data["limits"]["outline_density_floor"] == 0.5
    assert sorted(f["code"] for f in data["findings"]) == ["style.measures", "style.outline_density"]
    reference = project.json("probe", "style", first)["data"]["result"]
    assert [r["left_out"] for r in reference["references"]] == [False, True, False]  # the Asset itself is left out of the range


def test_probe_style_of_a_kind_without_style_checks_says_so(project: Kiripix) -> None:
    project.json("new", "demo", "a")

    data = project.json("probe", "style", "demo.a")["data"]["result"]

    assert data["stage"] is None and data["built"] is False and data["measures"] is None and data["findings"] == []
