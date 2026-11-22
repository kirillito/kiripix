"""NPCs in bulk from a seed (ticket 0359, ADR 0015, spec §6.3): `new npc <prefix> --base … --count N --seed S` and
`new npc <id> --reroll`, and `cast-sheet --match`. Most tests need no build (a choice is parameters); the one that judges a
crowd by `npc.stack` builds the base and its Wearables on the fake Blender (slow)."""

from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix
from test_npc import BODY, COAT, HAIR, built, ramps

CAP = "wearable.cap"


def plain(project: Kiripix, wearables: tuple[str, ...] = ("hair", "coat", "cap")) -> None:
    """The ramp table, character.zed and some Wearables on it, none built."""
    ramps(project)
    project.json("new", "character", "zed")
    for name in wearables:
        project.json("new", "wearable", name, "--body", BODY)


def crowd(project: Kiripix, *flags: str, count: int = 5, seed: int = 3, expect: int = 0) -> dict[str, Any]:
    return project.json("new", "npc", "guards", "--base", BODY, "--count", str(count), "--seed", str(seed), *flags, expect=expect)


def picked(result: dict[str, Any]) -> list[tuple[str, list[str], dict[str, str]]]:
    return [(n["asset"], n["wearables"], n["colours"]) for n in result["data"]["crowd"]]


def settings(project: Kiripix) -> dict[str, bytes]:
    return {p.parent.name: p.read_bytes() for p in sorted((project.cwd / "assets" / "npc").glob("*/asset.toml"))}


def test_the_same_seed_makes_the_same_five_choices_in_two_projects(project: Kiripix, tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    plain(project)
    other = Kiripix(tmp_path / "other")
    other.cwd.mkdir()
    other.json("init")
    plain(other)

    first = crowd(project)
    monkeypatch.setenv("PYTHONHASHSEED", "12345")  # the pick doesn't read the hash seed
    second = crowd(other)

    assert picked(first) == picked(second)
    assert [a for a, _, _ in picked(first)] == [f"npc.guards_0{n}" for n in range(1, 6)]
    assert first["data"]["asset"] == ",".join(a for a, _, _ in picked(first))
    assert len({(tuple(w), tuple(c.items())) for _, w, c in picked(first)}) == 5  # no two alike while the space allows it
    assert settings(project).keys() == {f"guards_0{n}" for n in range(1, 6)}
    for _, wearables, colours in picked(first):
        assert set(wearables) <= {HAIR, COAT, CAP} and set(colours) == {"hair", "top"}
        assert colours["hair"] in ("auburn", "blond") and colours["top"] == "red"
    assert [f["code"] for f in first["findings"]] == ["new.crowd_stack_unchecked"]  # nothing is rendered: said, not silent
    assert first["findings"][0]["severity"] == "info" and first["findings"][0]["fix"]


def test_a_choice_is_written_as_choose_parameters_and_another_seed_gives_another_crowd(project: Kiripix) -> None:
    plain(project)

    made = crowd(project)
    npc, wearables, colours = picked(made)[0]
    text = (project.cwd / "assets" / "npc" / "guards_01" / "asset.toml").read_text("utf-8")

    assert 'base = "character.zed"' in text and "[stages.choose]" in text
    assert f"hair={colours['hair']}" in text
    if wearables:
        assert f'wearables = "{",".join(wearables)}"' in text
    assert npc == "npc.guards_01"
    other = Kiripix(project.cwd.parent / "again")
    other.cwd.mkdir()
    other.json("init")
    plain(other)
    assert picked(crowd(other, seed=4)) != picked(made)


def test_the_flags_narrow_what_a_pick_may_use(project: Kiripix) -> None:
    plain(project)

    result = crowd(project, "--wearables", "wearable.h*,wearable.cap", "--choices", "hair=auburn", count=6)

    for _, wearables, colours in picked(result):
        assert set(wearables) <= {HAIR, CAP} and colours["hair"] == "auburn"
    assert {w for _, ws, _ in picked(result) for w in ws} == {HAIR, CAP}


def test_a_crowd_that_cannot_be_all_different_keeps_the_closest_with_a_warning(project: Kiripix) -> None:
    plain(project, ())

    result = crowd(project, "--choices", "hair=auburn", count=3)

    unsatisfied = [f for f in result["findings"] if f["code"] == "new.crowd_unsatisfied"]
    assert len(picked(result)) == 3 and len(unsatisfied) == 2  # one choice only: the second and third repeat it
    assert unsatisfied[0]["severity"] == "warning" and unsatisfied[0]["fix"].endswith("--reroll")
    assert unsatisfied[0]["position"]["asset"] == "npc.guards_02"


def test_reroll_changes_one_npc_and_no_other(project: Kiripix) -> None:
    plain(project)
    made = crowd(project)
    before = settings(project)

    first = project.json("new", "npc", "npc.guards_03", "--reroll")
    after = settings(project)

    assert [k for k in before if before[k] != after[k]] == ["guards_03"]
    changed = picked(first)
    assert len(changed) == 1 and changed[0][0] == "npc.guards_03" and first["data"]["crowd"][0]["changed"]
    assert changed[0][1:] != picked(made)[2][1:]
    assert all(changed[0][1:] != p[1:] for p in picked(made))  # nor is it another one's twin
    seeded = project.json("new", "npc", "guards_03", "--reroll", "--seed", "9")
    assert picked(seeded)[0][1:] != changed[0][1:] and settings(project)["guards_03"] != after["guards_03"]
    assert {k: v for k, v in settings(project).items() if k != "guards_03"} == {k: v for k, v in before.items() if k != "guards_03"}


def test_a_refused_crowd_makes_nothing(project: Kiripix) -> None:
    plain(project)
    crowd(project, count=2)
    cases = [
        (["new", "npc", "guards", "--base", BODY, "--count", "2"], "new.crowd_incomplete"),  # no seed
        (["new", "npc", "guards", "--base", BODY, "--count", "2", "--seed", "1"], "asset.duplicate_id"),
        (["new", "npc", "cops", "--base", BODY, "--count", "2", "--seed", "1", "--wearables", "wearable.nothing"],
         "new.crowd_wearables_unknown"),
        (["new", "npc", "cops", "--base", BODY, "--count", "2", "--seed", "1", "--choices", "hair=pink"], "new.crowd_choice_unknown"),
        (["new", "npc", "cops", "--base", "character.nobody", "--count", "2", "--seed", "1"], "npc.base_unknown"),
        (["new", "prop", "cops", "--count", "2", "--seed", "1"], "new.crowd_needs_npc"),
        (["new", "npc", "cops", "--base", BODY, "--reroll"], "new.crowd_reroll_args"),
    ]
    for arguments, code in cases:
        result = project.json(*arguments, expect=1)
        assert [f["code"] for f in result["findings"]] == [code], arguments
        assert result["findings"][0]["fix"]
    assert settings(project).keys() == {"guards_01", "guards_02"}


def test_a_built_crowd_passes_the_checks_and_cast_sheet_shows_it(project: Kiripix) -> None:
    built(project, (HAIR, COAT))

    result = crowd(project, count=3)

    assert [f for f in result["findings"] if f["code"] in ("new.crowd_stack_unchecked", "new.crowd_unsatisfied")] == []
    for npc, _, _ in picked(result):
        project.json("run", npc, "choose")
    checked = project("check", "--match", "npc.guards_*", "--json")
    assert checked.code == 0, checked.stdout
    assert [f for f in checked.json["findings"] if f["code"].startswith("npc.") and f["severity"] != "info"] == []
    sheet = project.json("cast-sheet", "--match", "npc.guards_*")
    assert [c["asset"] for c in sheet["data"]["cells"]][:1] == ["npc.guards_01"]
    assert {c["asset"] for c in sheet["data"]["cells"]} == {"npc.guards_01", "npc.guards_02", "npc.guards_03"}
    project.json("cast-sheet", "npc.guards_02")  # one NPC by its ID, too
    assert project.json("cast-sheet", "--match", "npc.nobody_*", expect=1)["findings"][0]["code"] == "match.none"
