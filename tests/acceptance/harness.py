"""The agent acceptance harness (spec §14, ticket 0028).

It builds a fresh Project with an imported room image and an empty Godot project, starts an agent that sees only the
`kiripix` tool, plays the stand-in owner when the Project waits on one, and then checks the result itself, against the
Project and the Godot folder, never by what the agent says.

Like every test, it drives `kiripix` only as a subprocess and reads the JSON, the exit code and the files.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image

FIXTURES = Path(__file__).parent / "fixtures"
RECIPES = "acceptance_recipes"  # FIXTURES/acceptance_recipes.py: the fake Runners and nothing else
RECIPE_PATH = (FIXTURES, Path(__file__).resolve().parents[1] / "fixtures")  # it imports tests/fixtures' fakes
ASSET = "room.alley"
LAYER = "crate"  # the Layer the stand-in owner lifts (fixtures/owner.json)
WIDTH, HEIGHT = 48, 32
TOOL_NAMES = ("kiripix", "kpx")
GAME_FILES = (
    "kiripix/room/alley/alley.tscn",
    "kiripix/room/alley/plate.png",
    f"kiripix/room/alley/layer.{LAYER}.png",
    "kiripix/manifest/room.alley.json",
)
CARRY_ON = "Done, carry on."

TASK = f"""\
You are working in a Kiripix Project, a folder of pixel art assets for a Godot game, using only the command line tool \
`kiripix` (also `kpx`). It is the only thing you can run. Use its own help and output to find your way. Run one plain \
`kiripix` command per call, from the current folder, because shell syntax such as `$?` can get a call denied. A failing \
command's exit code is shown to you.

The Project has one room, {ASSET}. Its image is already imported. Take it from import to export: get it exported into \
the Godot project, and get `kiripix check --all` to pass.

Some things only the game's owner can decide or approve. When you reach one, stop and say what you need. The owner \
will do it and tell you when to carry on. You are done when the room is exported and `kiripix check --all` passes.
"""


# Tokens and commands


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_creation: int = 0
    cache_read: int = 0

    @property
    def fresh(self) -> int:
        """What the budget counts: tokens the model read or wrote anew. Cache reads repeat the same prompt every turn."""
        return self.input + self.output + self.cache_creation

    @property
    def total(self) -> int:
        return self.fresh + self.cache_read

    def add(self, other: "Usage") -> None:
        self.input += other.input
        self.output += other.output
        self.cache_creation += other.cache_creation
        self.cache_read += other.cache_read


@dataclass
class CommandRun:
    """One Bash call (or the scripted agent's call) of the agent, in order."""

    turn: int
    command: str
    exit_code: int | None
    denied: bool = False
    output: str = ""


@dataclass
class AgentTurn:
    """What an agent did between being started (or resumed) and stopping."""

    commands: list[CommandRun] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    final_text: str = ""
    session_id: str | None = None
    over_budget: bool = False
    error: str | None = None  # the agent run itself failed (crash, bad exit, isolation breach)


class Agent(Protocol):
    """The seam both the real agent (`claude -p`) and the scripted dry-run agent plug into."""

    name: str
    agent_version: str | None
    isolation: list[str]  # what keeps it to the tool, for the report

    def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn: ...

    def resume(self, message: str, budget_left: int) -> AgentTurn: ...


# Environments


def venv_bin() -> Path:
    """The folder holding `kiripix` and `kpx`: the Scripts/bin folder of the environment the harness runs in."""
    return Path(sys.executable).parent


def clean_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The harness's own calls (setup, `next`, the checks): no KIRIPIX_ variable at all."""
    env = {k: v for k, v in (os.environ if base is None else base).items() if not k.upper().startswith("KIRIPIX_")}
    env.pop("PYTHONPATH", None)  # tests/fixtures is put there by the other tests' harness; nothing here wants it
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def project_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The harness's own calls on the Project (setup, `next`, the checks): the fake Runners (D16), set here and by the
    agent's shims only. The Runners behind a Project's hashes must be the same in every call, or it goes stale."""
    env = clean_env(base)
    env["PYTHONPATH"] = os.pathsep.join(str(p) for p in RECIPE_PATH)
    env["KIRIPIX_TEST_RECIPES"] = RECIPES
    return env


def owner_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The stand-in owner's calls: the only place KIRIPIX_TEST_OWNER is set."""
    env = project_env(base)
    env["KIRIPIX_TEST_OWNER"] = "1"
    return env


def agent_env(base: Mapping[str, str] | None = None, bin_dir: Path | None = None,
              shim_dir: Path | None = None) -> dict[str, str]:
    """The agent's environment: `kiripix` on PATH, no KIRIPIX_TEST_OWNER or KIRIPIX_TEST_RECIPES, and nothing of a Claude
    session the harness may have been started from (its messaging socket and token would be a way out of the tool).

    With `shim_dir`, that folder comes first on PATH: its `kiripix` and `kpx` give the tool the fake Runners."""
    env = {k: v for k, v in clean_env(base).items() if not k.upper().startswith(("CLAUDE", "MCP_"))}
    path = [str(bin_dir or venv_bin()), env.get("PATH", "")]
    env["PATH"] = os.pathsep.join(([str(shim_dir)] if shim_dir else []) + path)
    assert_agent_env_clean(env)
    return env


def make_shims(folder: Path) -> Path:
    """`kiripix` and `kpx` that run this interpreter's `kiripix` with the fake Runners set for that one process.

    A `.cmd` for Windows (the dry run) and a shell script for Git Bash and POSIX (the real agent's Bash), side by side."""
    folder.mkdir(parents=True, exist_ok=True)
    python = Path(sys.executable)
    for name in TOOL_NAMES:
        shell = folder / name
        shell.write_text(
            "#!/bin/sh\n"
            f'KIRIPIX_TEST_RECIPES="{RECIPES}" PYTHONPATH="{os.pathsep.join(p.as_posix() for p in RECIPE_PATH)}" '
            f'exec "{python.as_posix()}" -m kiripix "$@"\n', "utf-8", newline="\n")
        shell.chmod(0o755)
        (folder / f"{name}.cmd").write_text(
            "@echo off\r\n"
            f"set KIRIPIX_TEST_RECIPES={RECIPES}\r\n"
            f"set PYTHONPATH={os.pathsep.join(str(p) for p in RECIPE_PATH)}\r\n"
            f'"{python}" -m kiripix %*\r\n', "utf-8", newline="")
    return folder


def assert_agent_env_clean(env: Mapping[str, str]) -> None:
    leaked = sorted(k for k in env if k.upper() in ("KIRIPIX_TEST_OWNER", "KIRIPIX_TEST_RECIPES"))
    assert not leaked, f"the agent's environment must not carry {leaked}"


def assert_no_instructions_above(cwd: Path) -> None:
    """No CLAUDE.md or project .claude folder in the agent's folder or any parent, so none is found by walking up.

    The home folder's own `.claude` is the user's config, not a project one; `--safe-mode` keeps that out."""
    home = Path.home().resolve()  # a Windows TEMP can be the 8.3 short form of the same folder
    for folder in (cwd.resolve(), *cwd.resolve().parents):
        for name in ("CLAUDE.md", "CLAUDE.local.md") + (() if folder == home else (".claude",)):
            assert not (folder / name).exists(), f"{folder / name} would reach the agent"


# Running kiripix as a subprocess


@dataclass
class Call:
    code: int
    stdout: str
    stderr: str

    @property
    def json(self) -> dict[str, Any]:
        lines = [line for line in self.stdout.splitlines() if line.strip()]
        assert len(lines) == 1, f"expected one JSON line, got:\n{self.stdout}\n{self.stderr}"
        value: dict[str, Any] = json.loads(lines[0])
        return value


def kiripix(cwd: Path, env: Mapping[str, str], *args: str, expect: int | None = 0, timeout: float = 300) -> Call:
    """`kiripix <args> --json` in `cwd`, from the harness. Stdin is closed, so an owner-only Command needs the env var."""
    done = subprocess.run([sys.executable, "-m", "kiripix", *args, "--json"], cwd=cwd, env=dict(env),
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    call = Call(done.returncode, done.stdout, done.stderr)
    if expect is not None:
        assert call.code == expect, f"kiripix {' '.join(args)}: exit {call.code}, expected {expect}:\n{call.stdout}\n{call.stderr}"
    return call


# The fresh Project


def room_image() -> np.ndarray:
    """48 x 32, drawn in code so there is no PNG to keep: a blue wall on the left third, a floor, a rug, and a red crate
    near (41, 22) for the owner to lift into a foreground Layer."""
    image = np.full((HEIGHT, WIDTH, 4), (194, 195, 199, 255), dtype=np.uint8)  # colours from `init`'s palette, so
    image[:, :16] = (29, 43, 83, 255)  # `palette.mapping_error` has nothing to say
    image[8:14, 24:36] = (171, 82, 54, 255)
    image[19:26, 38:45] = (255, 0, 77, 255)
    return image


@dataclass
class Setup:
    root: Path  # the temporary folder holding all of it
    project: Path
    game: Path
    variant: str  # the imported Variant
    shims: Path  # the agent's `kiripix` and `kpx`, with the fake Runners


def make_setup(root: Path) -> Setup:
    """A fresh Project, an empty Godot project wired up as the export target, and the room image imported.

    Already done when the agent starts: `init`, `new`, `import`, the brief's size (the owner's own spec of the room,
    which `import` can't know) and the export target (a Project setting only the owner edits). Everything from the
    Source's Pick to `export` is left to the agent and the owner.
    """
    project, game = root / "project", root / "game"
    project.mkdir(parents=True)
    game.mkdir()
    (game / "project.godot").write_text("config_version=5\n", encoding="utf-8")
    env = project_env()
    kiripix(project, env, "init")
    settings = project / "kiripix.toml"
    text = settings.read_text("utf-8")
    wired = re.sub(r'^# project = ".*"', f'project = "{game.as_posix()}"', text, count=1, flags=re.MULTILINE)
    assert wired != text, "kiripix.toml no longer has the commented `# project = ...` line to wire up"
    settings.write_text(wired, "utf-8", newline="")
    kiripix(project, env, "new", "room", "alley", "--view", "top")
    source = root / "room.png"  # outside the Project: the agent's folder holds only what `import` copied
    Image.fromarray(room_image(), "RGBA").save(source)
    variant = str(kiripix(project, env, "import", ASSET, str(source)).json["data"]["variant"])
    kiripix(project, env, "set", ASSET, "brief", f"width={WIDTH}", f"height={HEIGHT}")
    return Setup(root, project, game, variant, make_shims(root / "bin"))


# What the Project is waiting on


@dataclass
class NextState:
    done: bool
    stage: str | None
    status: str | None
    reason: str | None
    command: str | None
    owner_action: str | None

    @property
    def needs_owner(self) -> bool:
        return self.owner_action is not None or self.status == "needs-review"

    def describe(self) -> str:
        if self.done:
            return "done"
        wanted = self.command or self.owner_action or "nothing named"
        return f"{self.stage} is {self.status} ({self.reason}); next names: {wanted}"


def ask_next(setup: Setup, asset: str = ASSET) -> NextState:
    data = kiripix(setup.project, project_env(), "next", asset, expect=None).json["data"]
    return NextState(data["done"], data["stage"], data["status"], data["reason"], data["command"], data["owner_action"])


# The stand-in owner


class StandInOwner:
    """Feeds the fixture's Decisions through `decide` and `accept`, with KIRIPIX_TEST_OWNER=1 on those calls only."""

    def __init__(self, setup: Setup, fixture: Path = FIXTURES / "owner.json") -> None:
        data = json.loads(fixture.read_text("utf-8"))
        self.setup = setup
        self.asset: str = data["asset"]
        self.entries: list[dict[str, Any]] = data["decisions"]
        self.applied: set[int] = set()

    def step(self, state: NextState, only_this_stage: bool = False) -> list[str] | None:
        """What the owner does now, or None when the fixture has nothing for this.

        `only_this_stage` is for an agent's own report, when `next` isn't waiting on the owner: the owner answers an
        entry tagged for this Stage and doesn't volunteer the others."""
        env, project = owner_env(), self.setup.project
        if state.status == "needs-review" and state.stage:
            call = kiripix(project, env, "accept", self.asset, state.stage, expect=None)
            return [f"accept {self.asset} {state.stage}: exit {call.code}"]
        did: list[str] = []
        pending = [(i, e) for i, e in enumerate(self.entries) if i not in self.applied]
        for index, entry in ([p for p in pending if p[1].get("when_stage") == state.stage]
                             or [p for p in pending if "when_stage" not in p[1] and not only_this_stage]):
            self.applied.add(index)
            if "pick" in entry:
                call = kiripix(project, env, "pick", self.asset, self.setup.variant, expect=None)
                did.append(f"pick {self.asset} {self.setup.variant}: exit {call.code}")
                continue
            decision = json.dumps({"decision": entry["decision"], "data": entry["data"]})
            call = kiripix(project, env, "decide", self.asset, entry["stage"], "--decision", decision, expect=None)
            did.append(f"decide {self.asset} {entry['stage']} {entry['decision']}: exit {call.code}")
        return did or None


# The result


@dataclass
class Verification:
    exported: bool
    check_clean: bool
    details: list[str]

    @property
    def passed(self) -> bool:
        return self.exported and self.check_clean


def verify(setup: Setup) -> Verification:
    """The harness's own check of the Project and the Godot folder. Ignores whatever the agent said."""
    env, details = project_env(), []
    missing = [name for name in GAME_FILES if not (setup.game / name).is_file()]
    details.append(f"missing in the Godot project: {missing}" if missing else "all four exported files are in the Godot project")
    manifest = setup.game / "kiripix" / "manifest" / "room.alley.json"
    try:
        frozen = list(json.loads(manifest.read_text("utf-8"))["ids"]["layers"])
    except (OSError, ValueError, KeyError):
        frozen = []
    listed = LAYER in frozen
    details.append(f"the Manifest lists the Layer `{LAYER}`" if listed else f"the Manifest does not list the Layer `{LAYER}`: {frozen}")
    missing += [] if listed else [f"Manifest id layers/{LAYER}"]
    dry = kiripix(setup.project, env, "export", ASSET, "--dry-run", expect=None)
    pending = dry.json["data"] or {}
    stale = [] if dry.code == 0 else [f"export --dry-run exit {dry.code}"]
    stale += list(pending.get("would_write", [])) + list(pending.get("changed", [])) + list(pending.get("unmanaged", []))
    details.append(f"export --dry-run: nothing left to write" if not stale else f"export --dry-run still finds: {stale}")
    exported = not missing and not stale
    check = kiripix(setup.project, env, "check", "--all", expect=None)
    findings = [f for f in check.json["findings"] if f["severity"] in ("error", "warning")]
    clean = check.code == 0 and not findings
    details.append("check --all: exit 0, no errors or warnings" if clean
                   else f"check --all: exit {check.code}, findings {[f['code'] for f in findings]}")
    return Verification(exported, clean, details)


@dataclass
class Outcome:
    passed: bool
    dry_run: bool
    agent: str
    agent_version: str | None
    isolation: list[str]
    budget: int
    max_usd: float | None
    usage: Usage
    commands: list[CommandRun]
    interventions: list[str]
    verification: Verification | None
    failure_step: str | None
    failure_reason: str | None
    last_output: str
    seconds: float
    session_id: str | None = None
    turns: int = 0
    final_text: str = ""

    @property
    def denied(self) -> list[CommandRun]:
        return [c for c in self.commands if c.denied]


MAX_OWNER_TURNS = 10  # the Decisions, then a review of each Stage the lift sends back to needs-review


def run_acceptance(agent: Agent, setup: Setup, budget: int, dry_run: bool, max_usd: float | None = None,
                   fixture: Path = FIXTURES / "owner.json") -> Outcome:
    """Start the agent, play the owner until the Project is done or the agent is lost, and verify.

    The harness never names a Command to the agent: after an owner step it only says "Done, carry on."
    """
    started = time.monotonic()
    owner = StandInOwner(setup, fixture)
    usage, commands, interventions = Usage(), [], []
    turns, owner_turns, session = 0, 0, None
    last_output = ""
    failure: tuple[str, str] | None = None

    env = agent_env(shim_dir=setup.shims)
    assert_no_instructions_above(setup.project)
    turn = agent.start(TASK, setup.project, env, budget)
    while True:
        turns += 1
        usage.add(turn.usage)
        session = turn.session_id or session
        for run in turn.commands:
            run.turn = turns
        commands += turn.commands
        last_output = next((c.output for c in reversed(commands) if c.output), turn.final_text) or last_output
        if turn.error:
            failure = ("agent", turn.error)
            break
        if turn.over_budget or usage.fresh > budget:
            failure = ("budget", f"{usage.fresh} tokens used, the budget is {budget}")
            break
        state = ask_next(setup)
        if state.done:
            break
        # The agent's own report counts too: the owner answers it if the fixture has something for this Stage. When `next`
        # offered a command instead, the tool told the agent two things, so the report says so.
        asked = not state.needs_owner and "owner" in turn.final_text.lower()
        if state.needs_owner or asked:
            owner_turns += 1
            did = owner.step(state, only_this_stage=asked) if owner_turns <= MAX_OWNER_TURNS else None
            if did is not None:
                note = f" (the agent asked the owner, though `next` names `{state.command}`)" if asked else ""
                interventions += [f"after turn {turns}, waiting at {state.stage}{note}: " + "; ".join(did)]
                turn = agent.resume(CARRY_ON, budget - usage.fresh)
                continue
            if state.needs_owner:
                failure = (state.describe(), "the project waits on the owner and the fixture has nothing left for it")
                break
        failure = (state.describe(), "the agent stopped with nothing for the owner to do: it got lost here")
        break

    verification = verify(setup)
    if failure is None and not verification.passed:
        failure = ("verification", "; ".join(verification.details))
    return Outcome(
        passed=failure is None and verification.passed, dry_run=dry_run, agent=agent.name, agent_version=agent.agent_version,
        isolation=agent.isolation, budget=budget, max_usd=max_usd, usage=usage, commands=commands,
        interventions=interventions, verification=verification,
        failure_step=failure[0] if failure else None, failure_reason=failure[1] if failure else None,
        last_output=last_output, seconds=time.monotonic() - started, session_id=session, turns=turns,
        final_text=turn.final_text,
    )


# The scripted agent (the dry run)


def command_allowed(command: str) -> bool:
    """The same rule the real agent runs under: `kiripix ...` or `kpx ...` and nothing else (no env-var prefix)."""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return bool(words) and words[0] in TOOL_NAMES and not any(w in ("&&", "||", ";", "|", ">", "<") for w in words)


class ScriptedAgent:
    """Follows `kiripix next` exactly: runs the Command it names, stops when the owner is needed or it is done.

    It knows only what the task says: the Asset's ID, and to run `check --all` at the end. If it ever needs more,
    that is a bug in the tool's output, to report, not to script around.
    """

    name = "scripted (dry run)"
    agent_version = None
    isolation = ["same allow-list as the real agent (kiripix and kpx prefixes only)", "agent env without KIRIPIX_TEST_*",
                 "fake Runners (D16) through the shims `kiripix` and `kpx`, not the agent's env"]
    MAX_STEPS = 40

    def __init__(self, asset: str = ASSET) -> None:
        self.asset = asset
        self.cwd = Path()
        self.env: Mapping[str, str] = {}

    def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn:
        assert self.asset in task, "the task must name the Asset, as the real agent's does"
        assert_agent_env_clean(env)
        self.cwd, self.env = cwd, env
        return self._follow_next()

    def resume(self, message: str, budget_left: int) -> AgentTurn:
        return self._follow_next()

    def _run(self, turn: AgentTurn, command: str) -> CommandRun:
        if not command_allowed(command):
            run = CommandRun(0, command, None, denied=True, output="denied: only kiripix and kpx commands are allowed")
        else:
            words = shlex.split(command)
            exe = shutil.which(words[0], path=self.env["PATH"])
            assert exe, f"{words[0]} is not on the agent's PATH"
            done = subprocess.run([exe, *words[1:]], cwd=self.cwd, env=dict(self.env), stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, encoding="utf-8", timeout=300)
            run = CommandRun(0, command, done.returncode, output=(done.stdout + done.stderr).strip())
        turn.commands.append(run)
        return run

    def _follow_next(self) -> AgentTurn:
        turn, previous = AgentTurn(), None
        for _ in range(self.MAX_STEPS):
            asked = self._run(turn, f"kiripix next {self.asset} --json")
            data = json.loads(asked.output)["data"]
            if data["done"]:
                self._run(turn, "kiripix check --all --json")
                turn.final_text = "done"
                return turn
            if data["command"] is None:  # the owner's to do, or nothing is named: stop and say so
                turn.final_text = data["owner_action"] or f"stuck at {data['stage']}: {data['reason']}"
                return turn
            if data["command"] == previous:
                turn.final_text = f"`{data['command']}` did not move the project on"
                return turn
            previous = data["command"]
            self._run(turn, data["command"])
        turn.error = f"scripted agent gave up after {self.MAX_STEPS} steps"
        return turn


AgentFactory = Callable[[], Agent]
