"""The acceptance harness proves itself here, with no model: a scripted agent that follows `next` (the dry run, ticket
0028's first criterion), the agent's isolation, the stream parser, the budget and the report.

This file runs in the default `uv run pytest`: the dry run is about 30 `kiripix` calls (about a minute). Skip it with
`--ignore=tests/acceptance`. Nothing here starts `claude` with a prompt.
"""

import datetime
import json
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest
from PIL import Image

from .claude_agent import ALLOWED, Stream, claude_args
from .harness import (
    AREA,
    AREA_CELL,
    ASSET,
    HEIGHT,
    WIDTH,
    AgentTurn,
    CommandRun,
    Outcome,
    ScriptedAgent,
    Setup,
    Usage,
    agent_env,
    assert_agent_env_clean,
    clean_env,
    command_allowed,
    make_setup,
    owner_env,
    project_env,
    run_acceptance,
)
from .report import render, report_path, write_report

BUDGET = 200_000


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return make_setup(tmp_path)


class StoppedAgent:
    """An agent that does nothing and stops."""

    name, agent_version, isolation = "stopped", None, ["none"]

    def __init__(self, usage: Usage | None = None) -> None:
        self.usage = usage or Usage()

    def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn:
        return AgentTurn(usage=self.usage, final_text="I could not work out what to do.")

    def resume(self, message: str, budget_left: int) -> AgentTurn:
        return AgentTurn(final_text="Still stuck.")


# The dry run (one run, shared: it is most of this file's time)


class Spy(ScriptedAgent):
    """The scripted agent, keeping the environment it was started with."""

    seen: Mapping[str, str] = {}

    def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn:
        Spy.seen = env
        return super().start(task, cwd, env, budget_left)


@pytest.fixture(scope="module")
def dry_run(tmp_path_factory: pytest.TempPathFactory) -> tuple[Setup, Outcome]:
    setup = make_setup(tmp_path_factory.mktemp("dry"))
    with pytest.MonkeyPatch.context() as patch:  # the parent has the hooks set; the agent must not get them
        patch.setenv("KIRIPIX_TEST_OWNER", "1")
        patch.setenv("KIRIPIX_TEST_RECIPES", "kiripix_test_recipes")
        return setup, run_acceptance(Spy(), setup, BUDGET, dry_run=True)


def test_dry_run_takes_the_room_from_import_to_export(dry_run: tuple[Setup, Outcome]) -> None:
    setup, outcome = dry_run

    assert outcome.passed, f"{outcome.failure_step}: {outcome.failure_reason} / {outcome.last_output}"
    assert outcome.verification and outcome.verification.exported and outcome.verification.check_clean
    assert (setup.game / "kiripix" / "room" / "alley" / "alley.tscn").is_file()
    ran = [c.command for c in outcome.commands]
    assert any(c.startswith("kiripix export") for c in ran) and ran[-1].startswith("kiripix check --all")
    assert outcome.interventions, "the Project waited on the owner at least once, and the stand-in owner answered"
    assert not outcome.denied and outcome.usage.total == 0
    assert all(c.exit_code is not None for c in outcome.commands)


def test_dry_run_lifts_the_layer_through_next_and_the_owner_reviews_it(dry_run: tuple[Setup, Outcome]) -> None:
    setup, outcome = dry_run

    ran = [c.command for c in outcome.commands]
    assert any("--rerun" in c for c in ran), "`next` led the agent to `run --rerun`; nothing told it so"
    assert any("accept room.alley layers" in i for i in outcome.interventions), "the owner reviewed the lift"
    assert any("decide room.alley layers click" in i for i in outcome.interventions)
    assert outcome.verification and any("Manifest lists the Layer `crate`" in d for d in outcome.verification.details)
    assert (setup.game / "kiripix" / "room" / "alley" / "layer.crate.png").is_file()
    scene = (setup.game / "kiripix" / "room" / "alley" / "alley.tscn").read_text("utf-8")
    assert "layer.crate.png" in scene


def test_dry_run_takes_the_character_from_import_of_its_model_to_export_with_its_clips(dry_run: tuple[Setup, Outcome]) -> None:
    setup, outcome = dry_run

    ran = [c.command for c in outcome.commands]
    assert any(c.startswith("kiripix import character.hero") and "hero.glb" in c for c in ran), "the agent imported the Model"
    assert any(c.startswith("kiripix export character.hero") for c in ran)
    assert not any("--role" in c or "mixamo" in c.lower() for c in ran), "the pre-rigged Model needs no Mixamo round trip"
    clips = [i for i in outcome.interventions if "decide character.hero clips clip" in i]
    assert len(clips) == 1 and clips[0].count(": exit 0") == 3, "the owner made the three clips in one go"
    assert outcome.verification and any("lists every clip (idle, walk, attack)" in d for d in outcome.verification.details)
    for name in ("hero.tscn", "frames.tres", "texture.tres", "color.png", "normal.png"):
        assert (setup.game / "kiripix" / "character" / "hero" / name).is_file()
    manifest = json.loads((setup.game / "kiripix" / "manifest" / "character.hero.json").read_text("utf-8"))
    assert {f"{c}_{d}" for c in ("idle", "walk", "attack") for d in ("s", "sw", "w", "nw", "n", "ne", "e", "se")} == set(
        manifest["ids"]["clips"])


def test_dry_run_joins_the_second_piece_with_extend_and_picks_the_joined_variant_first(dry_run: tuple[Setup, Outcome]) -> None:
    setup, outcome = dry_run

    ran = [c.command for c in outcome.commands]
    steps = [i for i, c in enumerate(ran) if c.startswith("kiripix extend room.alley")]
    assert [ran[i].split()[3] for i in steps] == ["canvas", "add", "done"], "the room's first moves, in this order"
    assert steps == [0, 1, 2] and ran[3].startswith("kiripix pick room.alley "), "`done` says to pick the joined Variant"
    assert "piece-east.png" in ran[steps[1]] and all(outcome.commands[i].exit_code == 0 for i in (*steps, 3))
    journal = (setup.project / "assets" / "room" / "alley" / "extend" / "journal.jsonl").read_text("utf-8")
    assert [json.loads(line)["action"] for line in journal.splitlines()] == ["add", "done"]
    assert outcome.verification and any(f"masks/solid.png and room.json" in d for d in outcome.verification.details)
    solid = setup.game / "kiripix" / "room" / "alley" / "masks" / "solid.png"
    assert Image.open(solid).size == (WIDTH, HEIGHT), "the export is the whole room, both pieces"


def test_dry_run_the_area_is_put_wrong_first_and_the_owner_moves_it_when_the_agent_reports_the_finding(
        dry_run: tuple[Setup, Outcome]) -> None:
    setup, outcome = dry_run

    assert any("area.no_walkable" in c.output for c in outcome.commands), "the agent was shown the finding"
    moves = [i for i in outcome.interventions if "decide room.alley place marker" in i and "masks" not in i]
    assert len(moves) == 1, f"one owner step moved the area: {outcome.interventions}"
    first = next(i for i in outcome.interventions if "decide room.alley masks brush" in i)
    assert outcome.interventions.index(first) < outcome.interventions.index(moves[0])
    decisions = (setup.project / "assets" / "room" / "alley" / "decisions" / "place.jsonl").read_text("utf-8")
    areas = [json.loads(line)["data"] for line in decisions.splitlines() if '"type":"area"' in line.replace(" ", "")]
    assert [a["id"] for a in areas] == [AREA, AREA] and areas[0]["x"] == 0 and areas[1]["x"] == 40
    assert all(a["cell"] == AREA_CELL and a["walkable"] for a in areas)
    assert outcome.verification and any("Area2D" in d for d in outcome.verification.details)


def test_the_agent_sees_only_the_real_kinds_and_runners_though_the_fakes_are_loaded(setup: Setup) -> None:
    env = agent_env(shim_dir=setup.shims)

    for name in ("kiripix", "kpx"):
        exe = shutil.which(name, path=env["PATH"])
        assert exe and Path(exe).parent == setup.shims, "the shim comes first on the agent's PATH"
    run = ScriptedAgent()
    run.cwd, run.env = setup.project, env
    turn = AgentTurn()
    described = run._run(turn, "kiripix describe project --json").output
    runners = run._run(turn, "kiripix runners --json").output

    assert "demo" not in described and "sketch" not in described and "layered" not in described
    assert "character" in described, "the real Kinds include the character"
    assert "fake.tampered" not in runners and "inpainter-b" not in runners
    assert "KIRIPIX_TEST" not in "".join(env)


def test_the_scripted_agent_was_started_without_the_test_hooks(dry_run: tuple[Setup, Outcome]) -> None:
    assert Spy.seen and "KIRIPIX_TEST_OWNER" not in Spy.seen and "KIRIPIX_TEST_RECIPES" not in Spy.seen


def test_dry_run_report_is_labelled_and_names_every_command(dry_run: tuple[Setup, Outcome]) -> None:
    _, outcome = dry_run

    text = render(outcome, "m1", datetime.date(2026, 11, 4))

    assert "DRY RUN" in text and "**Result: PASS**" in text
    assert text.count("`kiripix ") >= len(outcome.commands)


# The harness's own checks catch failures


def test_an_agent_that_stops_with_nothing_for_the_owner_is_lost_at_a_named_step(setup: Setup) -> None:
    outcome = run_acceptance(StoppedAgent(), setup, BUDGET, dry_run=True)

    assert not outcome.passed
    assert outcome.failure_step and outcome.failure_step.startswith("room.alley brief")  # the first Stage that is not done
    assert "lost" in (outcome.failure_reason or "")


class AskingAgent(StoppedAgent):
    """Stops at once and asks the owner for something, although `next` names `kiripix run`."""

    def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn:
        return AgentTurn(final_text="The first Mask is the owner's call.")


def test_the_owner_answers_what_the_agent_reports_and_the_contradiction_is_recorded(setup: Setup, tmp_path: Path) -> None:
    fixture = tmp_path / "owner-brief.json"  # one answer for the brief; the others wait until they are asked for
    fixture.write_text(json.dumps({"asset": ASSET, "decisions": [
        {"when_stage": "brief", "stage": "masks", "decision": "brush",
         "data": {"mask": "solid", "erase": False, "radius": 4, "points": [[8, 0], [8, 40]]}},
        {"stage": "place", "decision": "marker", "data": {"id": "spawn.main", "type": "spawn", "x": 64, "y": 16}}]}),
        encoding="utf-8")

    outcome = run_acceptance(AskingAgent(), setup, BUDGET, dry_run=True, fixture=fixture)

    assert any("decide room.alley masks brush: exit 0" in i and "the agent asked the owner" in i
               for i in outcome.interventions)
    assert outcome.failure_step and outcome.failure_step.startswith("room.alley brief is todo"), "the owner moved nothing on"
    assert len(outcome.interventions) == 1, "the Markers wait until they are asked for"
    assert "Still stuck." in render(outcome, "m1", datetime.date(2026, 11, 4)), "the closing message is in the report"


def test_the_owner_volunteers_nothing_when_the_agent_asks_at_a_stage_with_no_entry(setup: Setup) -> None:
    class Asks(StoppedAgent):
        def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn:
            return AgentTurn(final_text="I need the owner.")

    outcome = run_acceptance(Asks(), setup, BUDGET, dry_run=True)

    assert not outcome.interventions and outcome.failure_step and outcome.failure_step.startswith("room.alley brief")


def test_exceeding_the_token_budget_ends_the_run_as_a_failure(setup: Setup) -> None:
    outcome = run_acceptance(StoppedAgent(Usage(input=150, output=60)), setup, 200, dry_run=True)

    assert not outcome.passed and outcome.failure_step == "budget"


# Isolation


def test_the_agents_environment_never_carries_the_test_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIRIPIX_TEST_OWNER", "1")
    monkeypatch.setenv("KIRIPIX_TEST_RECIPES", "kiripix_test_recipes")
    monkeypatch.setenv("PYTHONPATH", "somewhere")

    env = agent_env()

    assert not [k for k in env if k.startswith("KIRIPIX_")] and "PYTHONPATH" not in env
    assert "KIRIPIX_TEST_OWNER" not in clean_env(), "the harness's own calls are not the owner either"
    assert owner_env()["KIRIPIX_TEST_OWNER"] == "1"
    assert project_env()["KIRIPIX_TEST_RECIPES"] == "acceptance_recipes" and "KIRIPIX_TEST_OWNER" not in project_env()
    with pytest.raises(AssertionError):
        assert_agent_env_clean({"KIRIPIX_TEST_OWNER": "1"})


def test_the_agents_environment_carries_nothing_of_a_claude_session_around_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_MESSAGING_TOKEN", "secret")
    monkeypatch.setenv("MCP_CONNECTION_NONBLOCKING", "1")

    env = agent_env()

    assert not [k for k in env if k.startswith(("CLAUDE", "MCP_"))]


@pytest.mark.parametrize("command", [
    "cat kiripix.toml",
    "python -c 1",
    "KIRIPIX_TEST_OWNER=1 kiripix accept room.alley masks",
    "kiripix next room.alley && cat kiripix.toml",
    "kiripix next room.alley | head",
    "env kiripix next room.alley",
])
def test_only_kiripix_and_kpx_commands_are_allowed(command: str) -> None:
    assert not command_allowed(command)


@pytest.mark.parametrize("command", ["kiripix --help", "kpx next room.alley --json", "kiripix"])
def test_kiripix_and_kpx_commands_are_allowed(command: str) -> None:
    assert command_allowed(command)


def test_a_denied_attempt_is_recorded(setup: Setup) -> None:
    agent = ScriptedAgent()
    agent.cwd, agent.env = setup.project, agent_env()
    turn = AgentTurn()

    run = agent._run(turn, "KIRIPIX_TEST_OWNER=1 kiripix accept room.alley masks")

    assert run.denied and run in turn.commands


def test_the_agent_starts_outside_any_claude_md(setup: Setup) -> None:
    for folder in (setup.project, *setup.project.parents):
        assert not (folder / "CLAUDE.md").exists()
    assert not str(setup.project).startswith(str(Path(__file__).resolve().parents[2]))


def test_the_claude_flags_exist_and_confine_it_to_the_tool() -> None:
    args = claude_args("claude-haiku-5-5", 1.0, "00000000-0000-4000-8000-000000000000", resume=False)

    assert args[args.index("--tools") + 1] == "Bash" and args[args.index("--allowedTools") + 1] == ALLOWED
    assert "Bash(kiripix *)" in ALLOWED and "Bash(*" not in ALLOWED
    assert "--session-id" in args and "--resume" in claude_args("m", 1.0, "s", resume=True)
    claude = shutil.which("claude")
    if claude is None:
        pytest.skip("claude is not installed, so its flags can't be checked")
    help_text = subprocess.run([claude, "--help"], capture_output=True, text=True, encoding="utf-8").stdout
    missing = [a for a in args if a.startswith("--") and a not in help_text]
    assert not missing, f"not in `claude --help`: {missing}"


# The stream of `claude -p --output-format stream-json`


def _stream(events: list[dict[str, object]]) -> Stream:
    stream = Stream(turn=1)
    for event in events:
        stream.feed(event)
    return stream


INIT = {"type": "system", "subtype": "init", "session_id": "s1", "tools": ["Bash"], "mcp_servers": []}


def _call(tool_id: str, command: str, message: str = "m1") -> dict[str, object]:
    return {"type": "assistant", "session_id": "s1", "message": {
        "id": message, "usage": {"input_tokens": 3, "output_tokens": 5, "cache_creation_input_tokens": 7,
                                 "cache_read_input_tokens": 100},
        "content": [{"type": "tool_use", "id": tool_id, "name": "Bash", "input": {"command": command}}]}}


def _answer(tool_id: str, text: str, is_error: bool = False) -> dict[str, object]:
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": text, "is_error": is_error}]}}


def test_the_stream_gives_commands_exit_codes_denials_and_tokens() -> None:
    stream = _stream([
        INIT,
        _call("a", "kiripix next room.alley --json"), _answer("a", "{}"),
        _call("b", "kiripix run room.alley", "m2"), _answer("b", "Exit code 3\nneeds input", is_error=True),
        _call("c", "KIRIPIX_TEST_OWNER=1 kiripix accept room.alley masks", "m3"),
        _answer("c", "Permission to use Bash has been denied.", is_error=True),
        {"type": "result", "subtype": "success", "is_error": False, "result": "done", "permission_denials": [],
         "usage": {"input_tokens": 30, "output_tokens": 50, "cache_creation_input_tokens": 70,
                   "cache_read_input_tokens": 1000}},
    ])

    [a, b, c] = stream.commands()

    assert (a.exit_code, b.exit_code, c.denied) == (0, 3, True)
    assert stream.usage == Usage(30, 50, 70, 1000) and stream.usage.fresh == 150 and stream.usage.total == 1150
    assert stream.isolation_breach() is None


def test_tokens_before_the_result_count_each_message_once() -> None:
    stream = _stream([INIT, _call("a", "kiripix x"), _call("b", "kiripix y"), _call("c", "kiripix z", "m2")])

    assert stream.live_fresh == 2 * 15 and stream.usage.fresh == 2 * 15


def test_an_init_with_more_than_bash_is_an_isolation_breach() -> None:
    assert _stream([{**INIT, "tools": ["Bash", "Read"]}]).isolation_breach()
    assert _stream([{**INIT, "mcp_servers": [{"name": "x"}]}]).isolation_breach()
    assert _stream([]).isolation_breach()


# The report


def _outcome(passed: bool = False) -> Outcome:
    return Outcome(
        passed=passed, dry_run=False, agent="claude -p", agent_version="claude-haiku-5-5", isolation=["x"], budget=BUDGET,
        max_usd=1.0, usage=Usage(1, 2, 3, 4), session_id="s1", turns=2, seconds=5,
        commands=[CommandRun(1, "kiripix next room.alley", 0), CommandRun(1, "cat x", None, denied=True, output="no")],
        interventions=["after turn 1: decide"], verification=None, failure_step="reach is needs-input",
        failure_reason="lost", last_output="the last output",
    )


def test_a_failed_real_run_reports_model_tokens_commands_denials_and_where_it_got_lost() -> None:
    text = render(_outcome(), "m1", datetime.date(2026, 11, 4))

    assert "DRY RUN" not in text and "FAIL" in text and "claude-haiku-5-5" in text
    assert "1 / 2" in text and "3 / 4" in text and "total: 10" in text
    assert "`kiripix next room.alley` | 0" in text and "`cat x` | denied" in text
    assert "reach is needs-input" in text and "the last output" in text and "after turn 1: decide" in text


def test_a_report_never_overwrites_another_run_of_the_same_day(tmp_path: Path) -> None:
    day = datetime.date(2026, 11, 4)

    first = write_report(_outcome(), "m1", tmp_path, day)
    second = write_report(_outcome(), "m1", tmp_path, day)

    assert first.name == "2026-11-04-m1.md" and second.name == "2026-11-04-m1-2.md"
    assert report_path(tmp_path, "m1", day).name == "2026-11-04-m1-3.md"
    json.dumps(first.read_text("utf-8"))
