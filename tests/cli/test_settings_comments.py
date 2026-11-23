"""Ticket 0235: a write to kiripix.toml keeps the Owner's comments, key order and layout, also when it migrates the file."""

import tomllib
from pathlib import Path

from conftest import Kiripix
from test_ramp_table import hero
from test_character_model import HERO



def comments(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.lstrip().startswith("#")]


def annotate(path: Path) -> str:
    """The Project file with a comment above every table and key, and a trailing comment on schema_version."""
    out: list[str] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.startswith("schema_version"):
            line += "  # keep this"
        elif line.startswith("["):
            out.append(f"# about {line} ({index})")
        elif "=" in line and not line.startswith(" "):
            out.append(f"# the key on line {index}")
        out.append(line)
    text = "\n".join(out) + "\n"
    path.write_text(text, encoding="utf-8")
    return text


def test_ramps_add_keeps_every_comment_and_the_settings(project: Kiripix) -> None:
    hero(project)
    path = project.cwd / "kiripix.toml"
    before = annotate(path)
    settings = tomllib.loads(before)

    project.json("ramps-add", HERO, "--parts", "cloth,skin", "--colours", owner=True)

    after = path.read_text(encoding="utf-8")
    assert comments(before) == comments(after)
    kept = iter(after.splitlines())
    assert all(line in kept for line in before.splitlines())  # every line stays, in order; rows were added
    assert {k: v for k, v in tomllib.loads(after).items()} == {
        **settings, "character": {**settings["character"], "ramps": tomllib.loads(after)["character"]["ramps"]}}
    assert [r["name"] for r in tomllib.loads(after)["character"]["ramps"]] == ["cloth", "skin"]


def test_a_migration_written_by_ramps_add_keeps_every_comment(project: Kiripix) -> None:
    hero(project)
    path = project.cwd / "kiripix.toml"
    text = annotate(path)
    old = text.replace("schema_version = 14", "schema_version = 2")
    for key in ("light_angle", "light_tilt"):
        old = "\n".join(line for line in old.splitlines() if not line.startswith(key)) + "\n"
    assert old != text
    path.write_text(old, encoding="utf-8")
    old_settings = tomllib.loads(old)

    project.json("ramps-add", HERO, "--parts", "cloth", owner=True)

    after = path.read_text(encoding="utf-8")
    assert "schema_version = 14  # keep this" in after
    kept = [c for c in comments(old) if not c.startswith(("# the key on line",)) or "light_" not in c]
    assert set(comments(old)) - set(comments(after)) <= {c for c in comments(old) if "light" in c} | {
        c for c in comments(old) if c.startswith("# the key on line")}
    assert all(c in comments(after) for c in comments(old) if c.startswith("# about "))
    assert len(kept) >= len(comments(after)) - 1
    migrated = tomllib.loads(after)
    for section in ("project", "extend"):
        assert migrated.get(section) == old_settings.get(section)
    assert migrated["character"]["ramps"] == [{"name": "cloth", "length": migrated["character"]["ramps"][0]["length"]}]
    assert project.json("status")["ok"]


def test_a_second_ramps_add_appends_a_row_and_keeps_the_layout(project: Kiripix) -> None:
    hero(project)
    path = project.cwd / "kiripix.toml"
    annotate(path)
    project.json("ramps-add", HERO, "--parts", "cloth", owner=True)
    first = path.read_text(encoding="utf-8")

    project.json("ramps-add", HERO, "--parts", "skin", owner=True)

    after = path.read_text(encoding="utf-8")
    assert comments(first) == comments(after)
    assert [r["name"] for r in tomllib.loads(after)["character"]["ramps"]] == ["cloth", "skin"]
    assert "length = 3\n\n[[character.ramps]]" in after.replace("\r\n", "\n")
