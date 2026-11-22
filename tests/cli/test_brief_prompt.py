"""The room brief renders `prompt.txt` from `style/prompts/room.<ext>` and `style/bible.md` (ticket 0348)."""

from pathlib import Path

from conftest import Kiripix, stage_status

ROOM = "room.alley"

TEMPLATE = """Pixel-art {{ view }}-view room, {{ width }}x{{ height }} px ({{ tiles_wide }}x{{ tiles_high }} tiles of {{ tile }}).
Canvas {{ canvas_width }}x{{ canvas_height }} (aspect {{ canvas_aspect }}).
Mood: {{ mood }}.
{% for e in exits %}Exit {{ e.name }} on the {{ e.side }} side.
{% endfor %}{% if notes %}Notes: {{ notes }}
{% endif %}
{{ bible }}"""


def room(project: Kiripix, template: str | None = TEMPLATE, name: str = "room.j2") -> Path:
    if template is not None:
        (project.cwd / "style" / "prompts" / name).write_text(template, encoding="utf-8", newline="\n")
    project.json("new", "room", "alley", "--view", "side")
    return project.cwd / "assets" / "room" / "alley"


def test_a_template_renders_the_prompt_from_the_brief_and_the_bible(project: Kiripix) -> None:
    (project.cwd / "style" / "bible.md").write_text("Muted palette.\n", encoding="utf-8", newline="\n")
    folder = room(project)
    project.json("set", ROOM, "brief", "width=640", "height=368", "mood=damp", "notes=rain",
                 "exits=door:top, stairs:left")

    project.json("run", ROOM, "brief")

    text = (folder / "work" / "brief" / "prompt.txt").read_text(encoding="utf-8")
    assert text == (
        "Pixel-art side-view room, 640x368 px (40x23 tiles of 16).\n"
        "Canvas 1376x768 (aspect 1.7917).\n"
        "Mood: damp.\n"
        "Exit door on the top side.\n"
        "Exit stairs on the left side.\n"
        "Notes: rain\n"
        "\n"
        "Muted palette.\n"
    )
    shown = next(s for s in project.json("show", ROOM)["data"]["stages"] if s["stage"] == "brief")
    assert "prompt.txt" in str(shown["outputs"])


def test_a_project_without_a_template_has_no_prompt_and_no_error(project: Kiripix) -> None:
    folder = room(project, template=None)

    result = project.json("run", ROOM, "brief")

    assert result["ok"] is True
    assert not (folder / "work" / "brief" / "prompt.txt").exists()
    assert (folder / "work" / "brief" / "brief.json").is_file()


def test_changing_the_bible_or_the_template_makes_the_brief_stale(project: Kiripix) -> None:
    room(project)
    project.json("run", ROOM, "brief")
    assert stage_status(project, ROOM)["brief"] == "done"

    (project.cwd / "style" / "bible.md").write_text("Changed.\n", encoding="utf-8", newline="\n")
    assert stage_status(project, ROOM)["brief"] == "stale"
    project.json("run", ROOM, "brief")
    assert stage_status(project, ROOM)["brief"] == "done"

    (project.cwd / "style" / "prompts" / "room.j2").write_text("{{ mood }}\n", encoding="utf-8", newline="\n")
    assert stage_status(project, ROOM)["brief"] == "stale"


def test_a_field_the_brief_doesnt_have_is_brief_prompt_field(project: Kiripix) -> None:
    folder = room(project, "Light from the {{ lighting }}.\n")

    result = project.json("run", ROOM, "brief", expect=3)  # the template is the Owner's to correct

    assert [f["code"] for f in result["findings"]][:1] == ["brief.prompt_field"]
    assert "lighting" in result["findings"][0]["message"]
    assert not (folder / "work" / "brief" / "prompt.txt").exists()
    assert stage_status(project, ROOM)["brief"] == "failed"


def test_a_bad_exit_side_is_refused(project: Kiripix) -> None:
    room(project)
    project.json("set", ROOM, "brief", "exits=door:up")

    result = project.json("run", ROOM, "brief", expect=1)

    assert result["findings"][0]["code"] == "brief.exit_side"
