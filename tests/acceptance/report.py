"""The dated Markdown record of an acceptance run, under docs/acceptance/."""

import datetime
from pathlib import Path

from .harness import Outcome

DOCS = Path(__file__).resolve().parents[2] / "docs" / "acceptance"


def report_path(docs: Path, milestone: str, today: datetime.date) -> Path:
    """`<date>-<milestone>.md`; a second run the same day gets `-2`, `-3`, and no run overwrites another."""
    path = docs / f"{today.isoformat()}-{milestone}.md"
    count = 2
    while path.exists():
        path = docs / f"{today.isoformat()}-{milestone}-{count}.md"
        count += 1
    return path


def render(outcome: Outcome, milestone: str, today: datetime.date) -> str:
    o, u = outcome, outcome.usage
    title = f"Agent acceptance test, {milestone.upper()}, {today.isoformat()}"
    lines = [f"# {title}", ""]
    if o.dry_run:
        lines += ["> **DRY RUN.** A scripted agent that follows `next`, not a model. No tokens were spent. This proves "
                  "the harness only; it is not the milestone's record.", ""]
    lines += [
        f"**Result: {'PASS' if o.passed else 'FAIL'}**",
        "",
        f"- Agent: {o.agent}" + (f", on `{o.agent_version}`" if o.agent_version else ""),
        f"- Session: {o.session_id or 'none'}; agent runs (start plus resumes): {o.turns}",
        f"- Tokens in/out: {u.input} / {u.output}; cache written/read: {u.cache_creation} / {u.cache_read}",
        f"- Tokens total: {u.total} (fresh, the budget's basis: {u.fresh} = in + out + cache written)",
        f"- Budget: {o.budget} fresh tokens across all resumes"
        + (f"; also a cap of ${o.max_usd:.2f} per `claude` call" if o.max_usd is not None else ""),
        f"- Duration: {o.seconds:.0f} s",
        "",
        "## Isolation",
        "",
        *[f"- {line}" for line in o.isolation],
        "",
        "## Verification (by the harness, not the agent)",
        "",
        *([f"- {d}" for d in o.verification.details] if o.verification else ["- not run"]),
        "",
    ]
    if not o.passed:
        lines += ["## Where it failed", "", f"- Step: {o.failure_step}", f"- Why: {o.failure_reason}", "",
                  "Last output:", "", "```", (o.last_output or "(none)")[-2000:], "```", ""]
    lines += ["## The agent's closing message", "", "```", (o.final_text or "(none)")[-2000:], "```", ""]
    lines += ["## Owner interventions", ""]
    lines += [f"- {i}" for i in o.interventions] or ["- none"]
    lines += ["", "## Commands the agent ran", "", "| # | Run | Command | Exit |", "|---|---|---|---|"]
    for index, c in enumerate(o.commands, 1):
        exit_code = "denied" if c.denied else ("?" if c.exit_code is None else str(c.exit_code))
        lines.append(f"| {index} | {c.turn} | `{c.command.replace('|', chr(92) + '|')}` | {exit_code} |")
    lines += ["", "## Denied attempts", ""]
    lines += [f"- `{c.command}`: {c.output[:200]}" for c in o.denied] or ["- none"]
    return "\n".join(lines) + "\n"


def write_report(outcome: Outcome, milestone: str, docs: Path = DOCS, today: datetime.date | None = None) -> Path:
    today = today or datetime.date.today()
    path = report_path(docs, milestone, today)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(outcome, milestone, today), encoding="utf-8", newline="\n")
    return path
