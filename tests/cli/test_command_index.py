"""The static index of the Commands (ticket 0277): `kiripix` imports only the module of the Command it runs, and the
contract stays the same as when every Command module was imported at start.

Each check runs in a fresh interpreter, so it sees the registry as `kiripix` does."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

from conftest import Kiripix, kiripix_env

ROOT = Path(__file__).resolve().parents[2]
REGENERATE = "uv run python -m kiripix.commands.index_gen"


def python(code: str, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code), *args], capture_output=True, text=True, encoding="utf-8",
                          cwd=cwd, env=kiripix_env(test_recipes=False))


def test_the_index_lists_every_command() -> None:
    """A Command added without regenerating the index fails here, naming the Command."""
    done = python("""
        import json
        from kiripix.commands import index_gen, index
        from kiripix.commands.registry import REGISTRY
        index_gen.import_all()
        real = {c.name: c.handler.__module__ for c in dict.values(REGISTRY)}
        listed = {n: e.module for n, e in index.INDEX.items()}
        print(json.dumps({"real": real, "listed": listed,
                          "current": index_gen.source() == index_gen.INDEX_FILE.read_text(encoding="utf-8")}))
    """)
    assert done.returncode == 0, done.stderr
    seen = json.loads(done.stdout)
    real, listed = seen["real"], seen["listed"]
    problems = [f"Command {n!r} (in {real[n]}) is not in the index" for n in real if n not in listed]
    problems += [f"the index lists {n!r}, which no module declares" for n in listed if n not in real]
    problems += [f"the index puts {n!r} in {listed[n]}, but it is declared in {real[n]}"
                 for n in real if n in listed and real[n] != listed[n]]
    if not problems and not seen["current"]:
        problems = ["a summary or the order of the Commands changed"]
    assert not problems, "kiripix/commands/index.py is out of date:\n  " + "\n  ".join(problems) + f"\nRun: {REGENERATE}"


def test_lazy_and_eager_registries_give_the_same_schema_and_describe(kpx: Kiripix) -> None:
    """`schema` and `describe` are byte-equal whether the Command modules load on demand or all at once."""
    eager = """
        import sys
        from kiripix.commands import index_gen
        index_gen.import_all()
        from kiripix.launch import main
        sys.argv = ["kiripix", *sys.argv[1:]]
        main()
    """
    for args in (("schema", "--json"), ("describe", "room", "--json"), ("describe", "--json", "room", "--stage",
                                                                         "brief")):
        lazy = kpx(*args, test_recipes=False)
        done = subprocess.run([sys.executable, "-c", textwrap.dedent(eager), *args], capture_output=True, text=True, encoding="utf-8",
                              cwd=kpx.cwd, env=kiripix_env(test_recipes=False))
        assert lazy.code == done.returncode, args
        assert lazy.stdout == done.stdout, f"`kiripix {' '.join(args)}` differs between lazy and eager registries"
        assert lazy.stdout.strip(), args


def test_the_help_is_the_same_with_every_command_loaded() -> None:
    """The root's, every group's and every Command's `--help` match an app built from the whole registry."""
    done = python("""
        import json, sys
        from typer.testing import CliRunner
        from kiripix.cli import build_app, called_command
        from kiripix.commands import INDEX, REGISTRY
        from kiripix.server import LAUNCHER_LISTING, load_launchers
        LAUNCHERS = load_launchers()
        listed = [(l.name, l.summary) for l in LAUNCHERS]
        full = build_app(LAUNCHER_LISTING, load_launchers, all_commands=True)
        argvs = [[]] + [["--help"]] + [[g, "--help"] for g in sorted({n.split()[0] for n in INDEX if " " in n})]
        argvs += [[*n.split(), "--help"] for n in INDEX] + [[l.name, "--help"] for l in LAUNCHERS]
        wrong = []
        for argv in argvs:
            lazy = build_app(LAUNCHER_LISTING, load_launchers, only=called_command(argv),
                             launcher=argv[0] if argv else None)
            a = CliRunner().invoke(lazy, argv, prog_name="kiripix")
            b = CliRunner().invoke(full, argv, prog_name="kiripix")
            if (a.output, a.exit_code) != (b.output, b.exit_code):
                wrong.append(" ".join(argv))
        print(json.dumps({"checked": len(argvs), "wrong": wrong, "count": len(REGISTRY),
                          "launchers": list(LAUNCHER_LISTING) == listed}))
    """)
    assert done.returncode == 0, done.stderr
    seen: dict[str, Any] = json.loads(done.stdout)
    assert seen["wrong"] == [], f"`--help` differs between the lazy and the full app: {seen['wrong']}"
    assert seen["launchers"], "kiripix.server.LAUNCHER_LISTING doesn't match the Launchers in kiripix.server.launchers"
    assert seen["checked"] > seen["count"]


def test_one_command_imports_only_its_own_module(kpx: Kiripix) -> None:
    """`status` doesn't import the modules of the other Commands, but `schema` imports them all."""
    kpx("init")
    code = """
        import sys
        from kiripix.launch import main
        sys.argv = ["kiripix", *sys.argv[1:]]
        try:
            main()
        except SystemExit:
            pass
        print("LOADED:" + ",".join(sorted(m for m in sys.modules if m.startswith("kiripix.commands."))))
    """
    status = python(code, "status", "--json", cwd=kpx.cwd).stdout.splitlines()[-1]
    assert "kiripix.commands.project" in status
    assert "kiripix.commands.image_ops" not in status and "kiripix.commands.timing" not in status, status
    every = python(code, "schema", "--json", cwd=kpx.cwd).stdout.splitlines()[-1]
    assert "kiripix.commands.image_ops" in every and "kiripix.commands.timing" in every
