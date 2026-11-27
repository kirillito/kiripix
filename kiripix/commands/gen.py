"""gen, approve, reject and cost: painting through a Provider, the Owner's approval of each call, and the spend (tickets
0379, 0378, 0381, 0380, 0143). All the work is in `kiripix.core.gen` and `kiripix.core.ledger`."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import gen, gen_sprite, ledger
from kiripix.core.assets import Asset, is_asset_id, load_asset
from kiripix.core.errors import ExitCode, fail
from kiripix.core.gen import Candidate, PendingCall
from kiripix.core.ledger import MonthSpend
from kiripix.core.graph import ProgressEvent
from kiripix.core.kinds import all_providers
from kiripix.core.locks import asset_lock, hold
from kiripix.core.project import Project, find_project

# gen


class GenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID: a room, a Prop, a portrait or a sprite.")
    count: int = Field(1, ge=1, description="How many images to ask for, each stored as a Variant (CLI -n). Refused whole "
                                            "past `[providers] max_images_per_call` or the month's budget.")
    provider: str | None = Field(None, description="The Provider: openai or pixellab. `[providers] default` by default; a "
                                                   "sprite is painted by pixellab only.")
    prompt: str | None = Field(None, description="The words. A room's Source: in place of the brief's built prompt "
                                                 "(ticket 0348). A Prop's or a portrait's Source: needed. With --look, "
                                                 "--state or --emotion: what changes, after `style/prompts/<kind>-edit.<ext>`'s "
                                                 "words, else after \"Edit this image. Keep everything exactly the same "
                                                 "except:\". With --side: what the new area holds.")
    look: str | None = Field(None, description="A room's Look: an edit of the picked Source, stored as an edit Variant of "
                                               "the Look (src/looks/<look>/), as `import --look` stores one.")
    state: str | None = Field(None, description="A Prop's declared state: an edit of its picked Source, stored as a Variant "
                                                "of the state, as `import --state` stores one. For a sprite: a pose of its "
                                                "PixelLab character (with --prompt, the pose), stored as a sheet whose clip is "
                                                "the name (`<name>_2`... when the sheets already hold it).")
    emotion: str | None = Field(None, description="A portrait's declared emotion: an edit of the picked neutral image, "
                                                  "stored as a Variant of the emotion, as `import --emotion` stores one.")
    side: str | None = Field(None, description="A room mid-`extend`: write the next canvas for this side (east, south, west, "
                                               "north, or a corner such as east,south), send it with the room's prompt, and "
                                               "keep the results as candidate pieces; `extend add` joins the one chosen.")
    canvas: int | None = Field(None, description="A sprite's character or state: its square canvas in px (32 to 256; a "
                                                 "character's default is 32, a state's the character's).")
    from_frames: bool = Field(False, description="A sprite: make the PixelLab character from the sprite's own `frames` "
                                                 "output (the first frame of --from in each direction). Directions the sprite lacks are "
                                                 "made and stored as a sheet (a new clip name); when it has them all, no sheet.")
    from_clip: str | None = Field(None, description="A sprite, with --from-frames or --clip: the clip whose first frames the "
                                                    "character or the motion starts from (default idle).")
    to_clip: str | None = Field(None, description="A sprite, with --motion keyframes: the clip whose first frame (in each "
                                                  "direction) ends the motion. Needed: no motion is made from one frame and "
                                                  "text (`gen.keyframes_need_end`).")
    clip: str | None = Field(None, description="A sprite: the clip to make, with --motion and --prompt (the action).")
    motion: str | None = Field(None, description="A sprite, with --clip: rig (PixelLab's own rig and motion, per direction), "
                                                 "skeleton (the motion of a character's render, with --render) or keyframes (a "
                                                 "clip between the first frames of --from and --to, with --prompt the action; "
                                                 "only for a sprite marked faceless: `kiripix set <sprite> pixellab faces=false`).")
    frames: int | None = Field(None, description="A sprite, with --clip: the frames to make, 1 to 15 (default 8); 3 to 15 "
                                                 "with --motion skeleton, picked evenly from the render's clip; an even 4 to 16 "
                                                 "with --motion keyframes.")
    render: str | None = Field(None, description="A sprite, with --motion skeleton: the character (`character.<name>`) whose "
                                                 "current `render` gives the motion. Its `render points` must hold the "
                                                 "joints' bones (`gen.render_points_missing` names the fix).")
    render_clip: str | None = Field(None, description="A sprite, with --motion skeleton: the render's clip to take (default: "
                                                      "the --clip name).")
    image: bool = Field(False, description="A sprite: an image of the figure from --prompt, the plain image call (with --style "
                                           "its style image), its candidates stored in src/ for `pick`, which makes the one "
                                           "chosen a one-direction sheet. -n is the candidates asked for.")
    style: str | None = Field(None, description="A sprite, with --image: the style image, `<asset>[:<clip>]` (the first south "
                                                "frame of a sprite's clip, or of a character's render; clip idle by default) "
                                                "or a PNG of the Project.")
    view: str | None = Field(None, description="A sprite's character (--prompt or --from-frames): the camera view, `low "
                                               "top-down`, `high top-down` (default) or `side`. Kept in [sprite.pixellab] and "
                                               "sent where PixelLab's endpoint takes one: the rotations and a rig or skeleton "
                                               "motion (not a state, keyframes motion or --image, which refuse --view).")
    preview: bool = Field(False, description="A sprite, with --motion skeleton: write the render's keypoints (JSON) and an "
                                             "overlay PNG under `.kiripix/calls/preview/<sprite>/` and stop: nothing is "
                                             "planned, estimated or sent.")
    directions: str | None = Field(None, description="A sprite, with --clip: the directions to make, such as s,e (default: "
                                                     "all the sprite asks for).")
    reference: list[Path] = Field([], description="Reference images sent with the call (such as the projection reference "
                                                  "a room's prompt names). Repeat for several. Over REST, one `reference` "
                                                  "part per image.")


class PreviewFiles(BaseModel):
    direction: str
    keypoints: str = Field(description="The keypoints JSON (`first_frame_keypoints`, `keypoints`, `meta`), relative to the Project.")
    overlay: str = Field(description="The overlay PNG: the render's frames with the joints drawn, the right side red.")


class GenData(BaseModel):
    asset: str
    call: str = Field(description="The call's ID: the pending call's, or the sent call's in the ledger.")
    sent: bool = Field(description="False: the call waits for the Owner (`[providers] approve = \"each\"`).")
    target: str = Field(description="source, look, state, emotion or extend; for a sprite: character, sprite_state or motion.")
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
    operation: str | None = Field(None, description="For a sprite: character, state or motion.")
    jobs: int = Field(0, description="For a sprite: the jobs planned.")
    generations: float | None = Field(None, description="When sent: the generations charged, for a Provider that charges "
                                                        "in them.")
    sheet: str | None = Field(None, description="For a sprite, when sent: the sheet stored in `src/sheets/`.")
    clips: list[str] = Field([], description="For a sprite, when sent: the clips the sheet holds.")
    character_id: str | None = Field(None, description="For a sprite's character, when sent: its ID, kept in "
                                                       "`[sprite.pixellab]`.")
    replaced_character_id: str | None = Field(None, description="A second character call replaces the first: the ID it "
                                                                "replaced.")
    next: str | None = Field(None, description="For a sprite, when sent: the command that goes on.")
    preview: list[PreviewFiles] = Field([], description="With --preview: the keypoints and overlay written, per direction.")
    terms: str = Field("", description="The Provider's terms on its output, when it has any.")

    def text(self) -> str:
        if self.preview:
            return "\n".join(f"{p.direction}: {p.keypoints}, {p.overlay}" for p in self.preview) + "\nnothing was planned or sent"
        if self.operation is not None:
            head = (f"{self.asset}: {self.operation} ({self.jobs} job(s)) from {self.provider} at {self.size}, "
                    f"est. ${self.estimated_usd:.2f}; ${self.remaining_usd:.2f} of ${self.budget_usd_month:.2f} left this month")
        else:
            head = (f"{self.asset}: {self.count} image(s) from {self.provider} {self.model} ({self.size}, {self.quality}), "
                    f"est. ${self.estimated_usd:.2f}; ${self.remaining_usd:.2f} of ${self.budget_usd_month:.2f} left this month")
        if self.terms:
            head += f"\nterms ({self.provider}): {self.terms}"
        if not self.sent:
            return f"{head}\nwaiting for the Owner: kiripix approve {self.call}"
        cost = f"${self.usd:.4f}{' (estimated)' if self.estimated else ''}" if self.usd is not None else "?"
        if self.operation is not None:
            made = f"sheet {self.sheet} (clips {', '.join(self.clips)})" if self.sheet else "no sheet"
            kept = f"; character {self.character_id}" if self.character_id else ""
            replaced = f" (replaces {self.replaced_character_id})" if self.replaced_character_id else ""
            more = f"\nnext: {self.next}" if self.next else ""
            return f"{head}\nsent ({cost}); {made}{kept}{replaced}{more}"
        if self.candidates:
            lines = "\n".join(f"  {c.file}: {c.add}" for c in self.candidates)
            return f"{head}\nsent ({cost}); candidate pieces, joined by no one:\n{lines}"
        pick = f"; pick one with kiripix pick {self.asset} <variant>" if self.target == "source" else ""
        return f"{head}\nsent ({cost}); Variants {', '.join(self.variants) or 'none new'}{pick}"


def _terms(call: PendingCall) -> str:
    found = all_providers().get(call.provider)
    return found.terms if found is not None else ""


def _data(call: PendingCall, sent: gen.Sent | None) -> GenData:
    return GenData(
        operation=call.operation, jobs=len(call.jobs), terms=_terms(call),
        generations=sent.generations if sent else None, sheet=sent.sheet if sent else None,
        clips=sent.clips if sent else [], character_id=sent.character_id if sent else None,
        replaced_character_id=sent.replaced_character_id if sent else None, next=sent.next if sent else None,
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
    for name in ("provider", "look", "state", "emotion", "side", "canvas", "clip", "motion", "frames", "directions", "render",
                 "render_clip", "style", "view"):
        if (value := getattr(arguments, name)) is not None:
            parts.append(f"--{name.replace('_', '-')} {json.dumps(value) if ' ' in str(value) else value}")
    if arguments.image:
        parts.append("--image")
    if arguments.from_frames:
        parts.append("--from-frames")
    if arguments.from_clip is not None:
        parts.append(f"--from {arguments.from_clip}")
    if arguments.to_clip is not None:
        parts.append(f"--to {arguments.to_clip}")
    if arguments.prompt is not None:
        parts.append(f"--prompt {json.dumps(arguments.prompt)}")  # double quotes, as a shell takes them
    parts += [f"--reference {r}" for r in arguments.reference]
    return " ".join(parts)


def _no_sprite_flags(asset: str, arguments: GenInput) -> None:
    """The flags that are for a sprite, refused for any other Asset before planning."""
    named = [flag for flag, value in (("--canvas", arguments.canvas), ("--from-frames", arguments.from_frames),
                                      ("--from", arguments.from_clip), ("--to", arguments.to_clip), ("--clip", arguments.clip),
                                      ("--motion", arguments.motion), ("--frames", arguments.frames),
                                      ("--directions", arguments.directions), ("--render", arguments.render),
                                      ("--render-clip", arguments.render_clip), ("--preview", arguments.preview),
                                      ("--image", arguments.image), ("--style", arguments.style),
                                      ("--view", arguments.view)) if value]
    if named:
        raise fail("gen.sprite_flag", f"{', '.join(named)} paint a sprite; {asset} is not one",
                   fix=f"kiripix gen {asset}")


def _notice(context: Context, call: PendingCall) -> None:
    context.progress(ProgressEvent(event="notice", message=gen.notice_line(call)))


def _preview(project: Project, asset: Asset, arguments: GenInput) -> Outcome[GenData]:
    """`--preview`: the render's keypoints and overlay, nothing planned or sent (ticket 0389)."""
    made, written = gen_sprite.preview(
        project, asset, clip=arguments.clip, motion=arguments.motion, render=arguments.render,
        render_clip=arguments.render_clip, frames=arguments.frames, directions=arguments.directions,
        from_clip=arguments.from_clip, again=_again(arguments))
    budget = project.settings.providers.budget_usd_month
    spent = ledger.spent_in_month(project, ledger.now().strftime("%Y-%m"))
    files = [PreviewFiles(direction=d, keypoints=k, overlay=o) for d, (k, o) in zip(made.directions, written, strict=True)]
    return Outcome(GenData(asset=asset.id, call="", sent=False, target="motion", provider="pixellab", model="", size="",
                           quality="", count=len(files), estimated_usd=0.0, remaining_usd=round(budget - spent, ledger.CENTS),
                           budget_usd_month=budget, operation="motion", preview=files))


@command(
    "gen",
    summary="Paint through a Provider (OpenAI's GPT Image; PixelLab): a room's Source from its brief's prompt, a Prop's or "
            "portrait's Source, a Look's edit (--look), a Prop's state (--state), a portrait's emotion (--emotion), or the next "
            "`extend` piece (--side). Each image is a Variant (a piece a candidate); gen never picks or joins. A SPRITE is "
            "painted by PixelLab only, as one pending call of jobs under one approval: a character from text (--prompt "
            "\"<who>\" [--canvas N] [--view V]) or from its own frames (--from-frames [--from <clip>] [--view V], which makes the "
            "facings the sprite lacks (the 8 rotations, then the character) and stores them as a new clip), an image of the "
            "figure (--image --prompt \"<what>\" [--style <asset>[:<clip>]|<png>] [-n N]: candidates for `pick`, which makes "
            "the one chosen a one-direction sheet), a state of it (--state <name> "
            "--prompt \"<the pose>\"), or motion by PixelLab's own rig (--clip <name> --motion rig --prompt \"<the action>\" "
            "[--frames N] [--directions s,e] [--from <clip>]) or by a character's render (--clip <name> --motion skeleton "
            "--render character.<name> [--render-clip <clip>] [--frames N] [--directions s,e] [--from <clip>]; --preview writes "
            "the keypoints and an overlay under .kiripix/calls/preview/ and sends nothing) or, for a sprite marked faceless "
            "(`set <sprite> pixellab faces=false`), between two of its own frames (--clip <name> --motion keyframes --from <clip> "
            "--to <clip> --prompt \"<the action>\" [--frames N] [--directions s,e]; never from one frame and text); each stored as a sheet (clip = state or clip name) for `frames`, "
            "and the character kept in asset.toml's [sprite.pixellab]. States the "
            "estimate and the month's budget first, and refuses a call past a limit before sending it. With [providers] "
            "approve = \"each\" it only writes a pending call for the Owner's `kiripix approve <id>` (exit 3).",
    input=GenInput,
    output=GenData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset",), options={"count": ("-n", "--count"), "from_clip": ("--from",), "to_clip": ("--to",)}),
    locks=LockNeeds(asset=lambda a: a.asset if is_asset_id(a.asset) else None),
    files=("reference",),
)
def gen_command(arguments: GenInput, context: Context) -> Outcome[GenData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    references = [r if r.is_absolute() else context.cwd / r for r in arguments.reference]
    if gen_sprite.takes(asset):
        if arguments.preview:
            return _preview(project, asset, arguments)
        call = gen_sprite.plan(project, asset, provider_name=arguments.provider, prompt=arguments.prompt,
                               canvas=arguments.canvas, from_frames=arguments.from_frames, from_clip=arguments.from_clip,
                               state=arguments.state, clip=arguments.clip, motion=arguments.motion, frames=arguments.frames,
                               directions=arguments.directions, count=arguments.count, look=arguments.look,
                               emotion=arguments.emotion, side=arguments.side, references=references,
                               render=arguments.render, render_clip=arguments.render_clip, again=_again(arguments),
                               image=arguments.image, style=arguments.style, view=arguments.view,
                               to_clip=arguments.to_clip, cwd=context.cwd)
    else:
        _no_sprite_flags(asset.id, arguments)
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
        return "\n".join(f"{c.id}  {c.asset}  {c.target}  "
                         + (f"{len(c.jobs)} job(s)" if c.operation else f"{c.count} x {c.size} {c.quality}")
                         + f"  est. ${c.estimated_usd:.2f}" for c in self.pending)


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
    terms: dict[str, str] = Field({}, description="The terms of each Provider that has them, by Provider.")

    def text(self) -> str:
        lines = [f"{m.month}: ${m.usd:.4f} ({m.calls} calls, {m.images} images; "
                 + ", ".join(f"{p} ${u:.4f}" + (f" ({m.generations[p]:g} generations)" if p in m.generations else "")
                             for p, u in sorted(m.providers.items())) + ")" for m in self.months]
        lines += [f"terms ({p}): {t}" for p, t in sorted(self.terms.items())]
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
                            estimated_lines=sum(1 for line in lines if line.estimated), since=window,
                            terms={p.id: p.terms for p in sorted(all_providers().values(), key=lambda p: p.id) if p.terms}))
