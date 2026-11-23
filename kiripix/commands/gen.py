"""gen, approve, reject and cost: painting through a Provider, the Owner's approval of each call, and the spend (tickets
0379, 0378, 0381, 0380, 0143). All the work is in `kiripix.core.gen` and `kiripix.core.ledger`."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import gen, ledger
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.errors import ExitCode, fail
from kiripix.core.gen import Candidate, PendingCall
from kiripix.core.ledger import MonthSpend
from kiripix.core.graph import ProgressEvent
from kiripix.core.locks import asset_lock, hold
from kiripix.core.project import find_project

# gen


class GenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID: a room, a Prop or a portrait.")
    count: int = Field(1, ge=1, description="How many images to ask for, each stored as a Variant (CLI -n). Refused whole "
                                            "past `[providers] max_images_per_call` or the month's budget.")
    provider: str | None = Field(None, description="The Provider: openai. `[providers] default` by default.")
    prompt: str | None = Field(None, description="The words. A room's Source: in place of the brief's built prompt "
                                                 "(ticket 0348). A Prop's or a portrait's Source: needed. With --look, "
                                                 "--state or --emotion: what changes, after `style/prompts/<kind>-edit.<ext>`'s "
                                                 "words, else after \"Edit this image. Keep everything exactly the same "
                                                 "except:\". With --side: what the new area holds.")
    look: str | None = Field(None, description="A room's Look: an edit of the picked Source, stored as an edit Variant of "
                                               "the Look (src/looks/<look>/), as `import --look` stores one.")
    state: str | None = Field(None, description="A Prop's declared state: an edit of its picked Source, stored as a Variant "
                                                "of the state, as `import --state` stores one.")
    emotion: str | None = Field(None, description="A portrait's declared emotion: an edit of the picked neutral image, "
                                                  "stored as a Variant of the emotion, as `import --emotion` stores one.")
    side: str | None = Field(None, description="A room mid-`extend`: write the next canvas for this side (east, south, west, "
                                               "north, or a corner such as east,south), send it with the room's prompt, and "
                                               "keep the results as candidate pieces; `extend add` joins the one chosen.")
    reference: list[Path] = Field([], description="Reference images sent with the call (such as the projection reference "
                                                  "a room's prompt names). Repeat for several. Over REST, one `reference` "
                                                  "part per image.")


class GenData(BaseModel):
    asset: str
    call: str = Field(description="The call's ID: the pending call's, or the sent call's in the ledger.")
    sent: bool = Field(description="False: the call waits for the Owner (`[providers] approve = \"each\"`).")
    target: str = Field(description="source, look, state, emotion or extend.")
    provider: str
    model: str
    size: str
    quality: str
    count: int
    estimated_usd: float = Field(description="The call's estimate, from the Provider's price table.")
    remaining_usd: float = Field(description="The month's budget left before the call (UTC).")
    budget_usd_month: float
    usd: float | None = Field(None, description="When sent: what it cost, from the Provider's reported usage, else the "
                                                "estimate (`estimated`).")
    estimated: bool | None = None
    usage: dict[str, int] = Field({}, description="When sent: the token counts the Provider reported (input_tokens, "
                                                  "output_tokens, ...); empty when it reported none.")
    month_spent_usd: float | None = Field(None, description="When sent: this month's spend (UTC), this call included.")
    variants: list[str] = Field([], description="When sent: the new Variants' names; `gen` never picks.")
    files: list[str] = Field([], description="When sent: every image stored, relative to the Project.")
    candidates: list[Candidate] = Field([], description="With --side, when sent: the pieces kept, joined by no one.")
    pending: PendingCall | None = Field(None, description="When not sent: the pending call, prompt and inputs included.")

    def text(self) -> str:
        head = (f"{self.asset}: {self.count} image(s) from {self.provider} {self.model} ({self.size}, {self.quality}), "
                f"est. ${self.estimated_usd:.2f}; ${self.remaining_usd:.2f} of ${self.budget_usd_month:.2f} left this month")
        if not self.sent:
            return f"{head}\nwaiting for the Owner: kiripix approve {self.call}"
        cost = f"${self.usd:.4f}{' (estimated)' if self.estimated else ''}" if self.usd is not None else "?"
        if self.candidates:
            lines = "\n".join(f"  {c.file}: {c.add}" for c in self.candidates)
            return f"{head}\nsent ({cost}); candidate pieces, joined by no one:\n{lines}"
        pick = f"; pick one with kiripix pick {self.asset} <variant>" if self.target == "source" else ""
        return f"{head}\nsent ({cost}); Variants {', '.join(self.variants) or 'none new'}{pick}"


def _data(call: PendingCall, sent: gen.Sent | None) -> GenData:
    return GenData(
        asset=call.asset, call=call.id, sent=sent is not None, target=call.target, provider=call.provider,
        model=call.model, size=call.size, quality=call.quality, count=call.count, estimated_usd=call.estimated_usd,
        remaining_usd=call.remaining_usd, budget_usd_month=call.budget_usd_month,
        usd=sent.usd if sent else None, estimated=sent.estimated if sent else None,
        usage=sent.usage if sent else {}, month_spent_usd=sent.month_spent_usd if sent else None,
        variants=sent.variants if sent else [], files=sent.files if sent else [],
        candidates=sent.candidates if sent else [], pending=None if sent else call)


def _again(arguments: GenInput) -> str:
    parts = [f"kiripix gen {arguments.asset}"]
    if arguments.count != 1:
        parts.append(f"-n {arguments.count}")
    for name in ("provider", "look", "state", "emotion", "side"):
        if (value := getattr(arguments, name)) is not None:
            parts.append(f"--{name} {value}")
    if arguments.prompt is not None:
        parts.append(f"--prompt {json.dumps(arguments.prompt)}")  # double quotes, as a shell takes them
    parts += [f"--reference {r}" for r in arguments.reference]
    return " ".join(parts)


def _notice(context: Context, call: PendingCall) -> None:
    context.progress(ProgressEvent(event="notice", message=gen.notice_line(call)))


@command(
    "gen",
    summary="Paint through a Provider (OpenAI's GPT Image): a room's Source from its brief's prompt, a Prop's or portrait's "
            "Source, a Look's edit (--look), a Prop's state (--state), a portrait's emotion (--emotion), or the next "
            "`extend` piece (--side). Each image is a Variant (a piece a candidate); gen never picks or joins. States the "
            "estimate and the month's budget first, and refuses a call past a limit before sending it. With [providers] "
            "approve = \"each\" it only writes a pending call for the Owner's `kiripix approve <id>` (exit 3).",
    input=GenInput,
    output=GenData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset",), options={"count": ("-n", "--count")}),
    locks=LockNeeds(asset=lambda a: a.asset if is_asset_id(a.asset) else None),
    files=("reference",),
)
def gen_command(arguments: GenInput, context: Context) -> Outcome[GenData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    references = [r if r.is_absolute() else context.cwd / r for r in arguments.reference]
    call = gen.plan(project, asset, count=arguments.count, provider_name=arguments.provider, prompt=arguments.prompt,
                    look=arguments.look, state=arguments.state, emotion=arguments.emotion, side=arguments.side,
                    references=references, again=_again(arguments))
    _notice(context, call)
    if project.settings.providers.approve == "each":
        gen.write_pending(project, call)
        return Outcome(_data(call, None), [gen.approval_finding(call)], ExitCode.NEEDS_OWNER)
    with hold(project.state_dir, [gen.PROVIDER_LOCK], context.wait, context.command_line):
        call = gen.recheck(project, call)  # another call may have been sent since the plan
        sent = gen.send(project, call)
    context.progress(ProgressEvent(event="notice", message=gen.sent_line(call, sent)))
    return Outcome(_data(call, sent))


# approve


class ApproveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(None, description="The pending call's ID, as `gen` gave it.")
    list: bool = Field(False, description="List the pending calls instead, sending nothing.")


class ApproveData(BaseModel):
    pending: list[PendingCall] = Field(description="With --list: every pending call, oldest first. Else: none.")
    sent: GenData | None = Field(None, description="The call sent.")

    def text(self) -> str:
        if self.sent is not None:
            return self.sent.text()
        if not self.pending:
            return "no pending calls"
        return "\n".join(f"{c.id}  {c.asset}  {c.target}  {c.count} x {c.size} {c.quality}  est. ${c.estimated_usd:.2f}"
                         for c in self.pending)


@command(
    "approve",
    summary="Send a pending Provider call that `gen` wrote (owner-only): shows it again, checks the budget and the limits "
            "again, sends it, stores its Variants and ledger line as `gen` would, and deletes it. Refused if an input "
            "image changed since (`provider.call_stale`). --list lists the pending calls.",
    input=ApproveInput,
    output=ApproveData,
    kind="owner-only",
    mcp="owner-only",
    cli=CliMeta(positional=("id",)),
    locks=LockNeeds(project=True),
)
def approve(arguments: ApproveInput, context: Context) -> Outcome[ApproveData]:
    project = find_project(context.cwd)
    if arguments.list:
        if arguments.id is not None:
            raise fail("input.invalid", "--list lists the pending calls: not with an ID", fix="kiripix approve --list")
        return Outcome(ApproveData(pending=gen.list_pending(project)))
    if arguments.id is None:
        raise fail("input.invalid", "approve takes a pending call's ID, or --list", fix="kiripix approve --list")
    call = gen.read_pending(project, arguments.id)
    locks = [gen.PROVIDER_LOCK] + ([asset_lock(call.asset)] if is_asset_id(call.asset) else [])
    with hold(project.state_dir, locks, context.wait, context.command_line):
        call = gen.recheck(project, call)
        _notice(context, call)
        sent = gen.send(project, call)
    context.progress(ProgressEvent(event="notice", message=gen.sent_line(call, sent)))
    gen.remove_pending(project, call.id)
    return Outcome(ApproveData(pending=[], sent=_data(call, sent)))


# reject


class RejectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="The pending call's ID.")


class RejectData(BaseModel):
    rejected: str
    asset: str

    def text(self) -> str:
        return f"rejected call {self.rejected} for {self.asset}; nothing was sent"


@command(
    "reject",
    summary="Delete a pending Provider call without sending it. Not owner-only: rejecting costs nothing.",
    input=RejectInput,
    output=RejectData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("id",)),
    locks=LockNeeds(project=True),
)
def reject(arguments: RejectInput, context: Context) -> Outcome[RejectData]:
    project = find_project(context.cwd)
    call = gen.read_pending(project, arguments.id)
    gen.remove_pending(project, call.id)
    return Outcome(RejectData(rejected=call.id, asset=call.asset))


# cost


class CostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: bool = Field(False, description="Only this month (UTC), with the budget and what's left.")
    since: str | None = Field(None, description="Also sum the calls sent since this time, ISO 8601 (such as "
                                                "2026-11-23T14:05:00+00:00; no offset means UTC): an agent's session, a day.")


class CostData(BaseModel):
    months: list[MonthSpend] = Field(description="Each month with spend, oldest first; with --month only this one.")
    month: str = Field(description="This month, UTC.")
    spent_usd: float = Field(description="This month's spend.")
    budget_usd_month: float
    remaining_usd: float = Field(description="This month's budget left; below 0 if a billed failure took it over.")
    estimated_lines: int = Field(description="Ledger lines whose cost is the estimate, the Provider having reported none.")
    since: ledger.Spend | None = Field(None, description="With --since: the calls sent since then, their cost and tokens.")

    def text(self) -> str:
        lines = [f"{m.month}: ${m.usd:.4f} ({m.calls} calls, {m.images} images; "
                 + ", ".join(f"{p} ${u:.4f}" for p, u in sorted(m.providers.items())) + ")" for m in self.months]
        lines.append(f"{self.month}: ${self.spent_usd:.2f} of ${self.budget_usd_month:.2f} spent, "
                     f"${self.remaining_usd:.2f} left")
        if self.since is not None:
            tokens = ", ".join(f"{v:,} {k}" for k, v in self.since.tokens.items() if k in ("input_tokens", "output_tokens"))
            lines.append(f"since {self.since.since}: ${self.since.usd:.4f} ({self.since.calls} calls, "
                         f"{self.since.images} images" + (f"; {tokens}" if tokens else "") + ")")
        return "\n".join(lines)


@command(
    "cost",
    summary="The spend on Providers, from the cost ledger (.kiripix/cost.jsonl): by month and by Provider, and this "
            "month's budget and what's left.",
    input=CostInput,
    output=CostData,
    kind="probe",
    mcp="exposed",
)
def cost(arguments: CostInput, context: Context) -> Outcome[CostData]:
    project = find_project(context.cwd)
    lines = ledger.read(project)
    this_month = ledger.now().strftime("%Y-%m")
    months = ledger.by_month(lines)
    spent = next((m.usd for m in months if m.month == this_month), 0.0)
    budget = project.settings.providers.budget_usd_month
    window = None
    if arguments.since is not None:
        try:
            start = datetime.fromisoformat(arguments.since)
        except ValueError:
            raise fail("input.invalid", f"--since {arguments.since} is not an ISO 8601 time",
                       fix="kiripix cost --since 2026-11-23T14:05:00+00:00") from None
        window = ledger.since(lines, start if start.tzinfo else start.replace(tzinfo=UTC))
    return Outcome(CostData(months=[m for m in months if not arguments.month or m.month == this_month], month=this_month,
                            spent_usd=spent, budget_usd_month=budget, remaining_usd=round(budget - spent, ledger.CENTS),
                            estimated_lines=sum(1 for line in lines if line.estimated), since=window))
