"""Run the agent acceptance test by hand: `uv run python -m tests.acceptance.run` (see docs/acceptance/README.md)."""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .claude_agent import DEFAULT_VERSION, ClaudeAgent
from .harness import Agent, ScriptedAgent, make_setup, run_acceptance
from .report import DOCS, write_report

DEFAULT_BUDGET = 200_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tests.acceptance.run", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="a scripted agent that follows `next`; costs nothing")
    parser.add_argument("--agent-version", default=DEFAULT_VERSION, help="what `claude -p` runs on (default: %(default)s)")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                        help="fresh tokens (in + out + cache written) across all resumes (default: %(default)s)")
    parser.add_argument("--max-usd", type=float, default=1.0, help="`--max-budget-usd` for each `claude` call")
    parser.add_argument("--milestone", default="m1", help="the report's name: docs/acceptance/<date>-<milestone>.md")
    parser.add_argument("--report", action="store_true", help="write the report even for a dry run")
    parser.add_argument("--docs-dir", type=Path, default=DOCS)
    parser.add_argument("--keep", action="store_true", help="keep the temporary Project and Godot folder")
    args = parser.parse_args(argv)

    agent: Agent = ScriptedAgent() if args.dry_run else ClaudeAgent(args.agent_version, args.max_usd)
    root = Path(tempfile.mkdtemp(prefix="kiripix-acceptance-"))
    try:
        setup = make_setup(root)
        outcome = run_acceptance(agent, setup, args.budget, args.dry_run, None if args.dry_run else args.max_usd)
    finally:
        if args.keep:
            print(f"kept {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)
    if not args.dry_run or args.report:
        print(f"report: {write_report(outcome, args.milestone, args.docs_dir)}")
    print(f"{'PASS' if outcome.passed else 'FAIL'}: {outcome.usage.fresh} fresh tokens, {len(outcome.commands)} commands")
    if not outcome.passed:
        print(f"lost at {outcome.failure_step}: {outcome.failure_reason}")
    return 0 if outcome.passed else 1


if __name__ == "__main__":
    sys.exit(main())
