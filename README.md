# Kiripix

A local pixel asset studio for Godot games. Kiripix turns generated or imported images, and 3D Models, into
consistent, game-ready pixel art: rooms with Layers and Masks, props, and animated characters. It enforces one palette
and one resolution per game, and it is built to be driven equally well by you from the terminal or by an AI coding
agent.

> **Status: early.** Milestone 0 (the skeleton) is done and Milestone 1 (a room, end to end) is in progress. Today a
> room goes from an imported image through `brief`, `source`, `fit` and `layers`. The later room Stages, props,
> characters, generation, Godot export and the UI are not built yet (see [What's not built yet](#whats-not-built-yet)).
> Everything below describes what the CLI does now.

- [Install](#install)
- [Quick start: a room](#quick-start-a-room)
- [How Kiripix thinks](#how-kiripix-thinks)
- [Command reference](#command-reference)
- [Output, findings and exit codes](#output-findings-and-exit-codes)
- [A Project on disk](#a-project-on-disk)
- [What's not built yet](#whats-not-built-yet)
- [Further reading](#further-reading)

## Install

Kiripix needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Binaries in a Project (PNG, GLB) are meant for
[git LFS](https://git-lfs.com/).

```
git clone <this repo> kiripix
cd kiripix
uv sync
uv run kiripix --help
```

The command is `kiripix`, with the short alias `kpx`. From inside the repo, prefix it with `uv run`; to use it from
your game's asset folder, either activate the virtualenv (`.venv\Scripts\activate` on Windows,
`source .venv/bin/activate` elsewhere) or call `.venv/Scripts/kiripix.exe` directly.

## Quick start: a room

This walks one room from an image you painted or generated elsewhere. Every step prints what to do next, so you rarely
need to remember a command.

**1. Create a Project** (one per game) and look at what it can make.

```
kiripix init my-game-assets
cd my-game-assets
kiripix describe project        # the Kinds and their Recipes
kiripix describe room           # each room Stage: parameters, Decisions, Checks
```

Edit `kiripix.toml` to set your game's internal resolution, tile size and Body, and replace `style/palette.gpl`
with your palette.

**2. Create an Asset.** Asset IDs are `<kind>.<name>`, with lower-case letters, digits and underscores.

```
kiripix new room queen_west_alley --view top
kiripix status
```

**3. Ask what's next, and do it.** `next` always answers with either a command to run or something only you can do.

```
kiripix next room.queen_west_alley
# room.queen_west_alley brief is todo; run: kiripix run room.queen_west_alley

kiripix run room.queen_west_alley
# brief: done
# error brief.size_not_tiles: the brief's size 480x270 isn't a whole number of 16 px tiles
#   fix: kiripix set room.queen_west_alley brief width=480 height=272
```

Failures come with a `fix:` line, the exact command that fixes them. Run it:

```
kiripix set room.queen_west_alley brief width=480 height=272
```

**4. Bring in the art and pick it.** `import` adds a PNG as a Variant, named by its hash; `pick` makes it the Source.

```
kiripix import room.queen_west_alley ~/art/alley.png
# added the Variant ec428e583c7b2e09 ...; pick it with kiripix pick room.queen_west_alley ec428e583c7b2e09

kiripix pick room.queen_west_alley ec428e583c7b2e09
kiripix run room.queen_west_alley
```

**5. Tune, look and check.**

```
kiripix set room.queen_west_alley fit mode=downscale scale=2
kiripix run room.queen_west_alley        # rebuilds only what the change made stale
kiripix preview room.queen_west_alley    # writes .kiripix/previews/<asset>.<stage>.x4.png, prints the path
kiripix check room.queen_west_alley
```

Changed your mind? `kiripix undo room.queen_west_alley source` takes back the last Decision on a Stage, and `redo`
brings it back. Nothing is ever deleted from the Decision journal.

## How Kiripix thinks

The words below are used exactly this way in every command, message and finding. The full list is in
[GLOSSARY.md](GLOSSARY.md).

| Word | Meaning |
|---|---|
| **Project** | One game's asset workspace: palette, resolution, tile size, style bible, Mask definitions, export target. |
| **Asset** | One thing in the game, with a Kind and a stable ID such as `room.queen_west_alley`. |
| **Kind** | `room`, `prop` or `character`. The Kind fixes the Recipe. |
| **Recipe** / **Stage** | A Kind's ordered list of Stages. Each Stage has inputs, parameters, outputs and Checks. |
| **Variant** / **Source** | A candidate image (imported or generated); the one you Pick becomes the Source. |
| **Decision** | Recorded human input a Stage replays: a Pick, clicks, an Override, Marker positions. |
| **Override** | A hand edit painted over a Stage's image, recorded and re-applied every time the Stage runs. |
| **Mask** / **Layer** | A binary gameplay region (`solid`, `ladder`) / a visible image plane (the Plate, foreground Layers). |
| **Check** | A pass/fail verification with located findings. |
| **Op** | A pure image function (quantise, flood fill), reachable directly through `kiripix op`. |
| **Owner** | You. The one person whose Decisions and acceptances count as human judgement. An agent never is. |

**Recipes today:**

```
room:      brief -> source -> fit -> layers -> masks -> palette -> place -> reach -> export
prop:      brief -> source -> cutout -> fit -> palette -> finish -> footprint -> export
character: model -> rig -> clips -> render -> palette -> finish -> sheet -> export
```

**Non-destructive.** A Stage's output is a pure function of its inputs, parameters, Decisions and pinned results.
Change something upstream (a parameter, the palette, a Pick) and everything below it becomes `stale` and rebuilds on
the next `run`. Never edit a generated file by hand: record an Override instead.

**Status is derived, never stored.** Kiripix works out each Stage's status from the hashes of its inputs every time
you ask:

| Status | Meaning | What to do |
|---|---|---|
| `todo` | Never produced output. | `kiripix run <asset>` |
| `stale` | An input changed since the output was built. | `kiripix run <asset>` |
| `needs-input` | Waiting for a Decision from you (for example, no Source picked). The reason is shown. | `kiripix next <asset>` says what. |
| `needs-review` | Rebuilt by replaying your Decisions onto changed input; you need to confirm it. | Look at a `preview`, then `kiripix accept <asset> <stage>`. |
| `done` | The output matches its inputs. | Nothing. |
| `failed` | The last run failed. Kept only in the local cache. | Read the findings, fix, `run` again. |

`run` goes through Stages in order and stops at the first one that is `needs-input`, `needs-review` or `failed`.

## Command reference

Every command has `--help`, and that help is always current. Three commands describe Kiripix to itself:
`describe` (Kinds, Stages, parameters, Decisions, Checks), `schema` (the JSON Schema of every command) and `next`
(what to do now).

Options every command takes: `--json` (print one JSON object), `--progress jsonl` (stream progress events on stderr).
Commands that write also take `--wait <seconds>` to wait for a lock another process holds, instead of failing at once.

### Project

| Command | What it does |
|---|---|
| `kiripix init [DIR]` | Create a Project in `DIR` (default `.`): `kiripix.toml`, `style/` (palette, style bible, refs, prompts), `assets/`, `.gitattributes`, `.gitignore`. |
| `kiripix describe project` | List every Kind with its Recipe. |
| `kiripix describe <kind>` | Every Stage of a Kind: parameters with types and defaults, the Decisions it accepts, its Checks, and the milestone it arrives in if not built yet. |
| `kiripix schema [COMMAND]` | JSON Schemas of command inputs and outputs, for one command (`schema run`, `schema "op quantize"`) or all. |
| `kiripix status [--kind KIND]` | Every Asset and the status of each of its Stages, with the reason where there is one. |

### Assets and Stages

| Command | What it does |
|---|---|
| `kiripix new <kind> <name> [--view top\|side]` | Create an Asset from its Kind's Recipe. A room needs `--view`; other Kinds refuse it. |
| `kiripix next <asset>` | The next Stage of an Asset and what it needs: a command to run, or an action only you can take. |
| `kiripix run <asset> [STAGE] [--force]` | Run stale and todo Stages in order. With `STAGE`, run only that Stage (its upstream must be done). `--force` re-runs `done` Stages too. |
| `kiripix run --all [--kind KIND]` | Run every Asset, locking one at a time. |
| `kiripix set <asset> <stage> key=value ...` | Set Stage parameters. Values are checked against the Stage's declared parameters (`describe <kind>` lists them). |
| `kiripix check <asset>` | Run the Checks of every built Stage of an Asset and list the findings. |
| `kiripix check --all` | Check every Asset, then the Project checks (those across Assets, such as Exit pairing). |
| `kiripix preview <asset> [--stage S] [--zoom N] [--overlay masks]` | Write a Stage's image to `.kiripix/previews/` at a whole-number zoom (default 4, nearest neighbour) and print its path. Defaults to the last done Stage with an image. `--overlay masks` tints each Mask over it. |

### Sources

| Command | What it does |
|---|---|
| `kiripix import <asset> <file.png>` | Add an image made elsewhere as a Variant, named by its hash. Prints the `pick` command. |
| `kiripix pick <asset> <variant>` | Pick a Variant as the Asset's Source (records a Pick Decision). `next` lists the Variants. |

### Decisions

Every Decision goes into the Stage's append-only journal, `decisions/<stage>.jsonl`.

| Command | What it does |
|---|---|
| `kiripix decide <asset> <stage> --decision '<json>'` | Record a Decision, validated against the Stage's Decision schema. The JSON is `{"decision": "<name>", "data": {...}}`; `describe <kind>` lists each Stage's Decision names. Use `--file d.json` instead of `--decision` for long input. |
| `kiripix override <asset> <stage> <painted.png>` | Record an Override: a PNG the same size as the Stage's image, painted over it on every run. If the Stage's own image later changes, the Stage goes to `needs-review`. |
| `kiripix undo <asset> <stage>` | Undo the Stage's latest current Decision (appends an undo entry; nothing is removed). |
| `kiripix redo <asset> <stage>` | Redo the latest undone Decision. |
| `kiripix accept <asset> <stage>` | **Owner-only.** Confirm a `needs-review` Stage: re-record its Decisions against the current image so the next replay is exact. Refuses unless stdin is an interactive terminal, so an agent can't accept its own work. |

### Ops

Ops run one image function directly, outside any Asset. They use the Project's palette unless you pass `--palette`.

| Command | What it does |
|---|---|
| `kiripix op quantize <in.png> <out.png> [--palette P] [--dither none\|bayer2\|bayer4\|bayer8] [--strength 0..1]` | Map an image to the palette in OKLab, strictly or with ordered dithering. |
| `kiripix op conformance <image.png> [--palette P]` | Report pixels off the palette and partially transparent pixels. Exits 2 if there are any. |

Palettes can be GIMP `.gpl` or `.hex` files.

## Output, findings and exit codes

By default commands print readable text: results on stdout, findings on stderr. With `--json`, a command prints
exactly one object on stdout, always shaped the same way:

```json
{
  "api_version": 1,
  "ok": true,
  "data": { "asset": "room.queen_west_alley", "stage": "brief", "status": "done",
            "command": "kiripix set room.queen_west_alley brief width=480 height=272", "owner_action": null, "...": "..." },
  "findings": []
}
```

Every finding has a stable dotted `code` (such as `palette.off_palette` or `fit.size_mismatch`), a message, and
exactly one remedy: `fix`, a command anyone can run, or `owner_action`, something only you can do.

| Exit code | Meaning |
|---|---|
| 0 | OK |
| 1 | Error (bad input, missing file, ...) |
| 2 | A Check failed |
| 3 | Needs the Owner: a Stage is `needs-input` or `needs-review` |
| 4 | Busy: another process holds the lock (the JSON names it); retry, or pass `--wait` |

**Using Kiripix from an AI agent.** Point the agent at `kiripix --help`, `kiripix describe project`,
`kiripix next <asset> --json` and `kiripix check <asset> --json`; these are designed to be all it needs. Exit code 3
means the agent should stop and report back to you rather than retry.

## A Project on disk

```
my-game-assets/
  kiripix.toml              Project settings: resolution, tile, palette, Body, Masks, export target, Providers
  style/
    palette.gpl             the Project palette
    bible.md                style notes, for prompt templates
    refs/  prompts/         reference images and prompt templates
  assets/
    room/queen_west_alley/
      asset.toml            Kind and parameters (never status)
      history.jsonl         append-only log of runs and generations
      src/                  Variants, named by hash (immutable once picked)
      decisions/            one Decision journal per Stage (<stage>.jsonl), plus Override PNGs
      pinned/               pinned Runner and Provider results
      work/                 deterministic Stage outputs: a cache, safe to delete
      out/                  final outputs, the exporter's input
  .kiripix/                 hash cache, last-run failures, locks, previews (git-ignored)
```

Commit `kiripix.toml`, `style/` and, for each Asset, `asset.toml`, `history.jsonl`, `src/`, `decisions/`, `pinned/`
and `out/`. Don't commit `work/` or `.kiripix/`; `init` writes a `.gitignore` and `.gitattributes` that handle this.

## What's not built yet

These are designed in [the spec](docs/KIRIPIX_SPEC.md) but don't exist in the CLI yet:

- **Room Stages** `masks`, `palette`, `place`, `reach` and `export` report `needs-input` with "not implemented until
  M1". `layers` is a pass-through for now: the Plate is the fit image, with no foreground Layers.
- **Prop** (M2) and **character** (M3) Recipes: `new` creates them and `describe` lists their Stages, but they don't run.
- Commands: `gen` (Providers), `export` and `manifest` (Godot), `serve`, `ui` and `mcp`, `probe`, `runners`, `cost`,
  and `run --rerun` / `--cpu`.

`kiripix describe <kind>` marks each unbuilt Stage with the milestone it arrives in, so it is the quickest way to
check.

## Further reading

- [GLOSSARY.md](GLOSSARY.md): the vocabulary.
- [docs/KIRIPIX_SPEC.md](docs/KIRIPIX_SPEC.md): the full design and milestones.
- [docs/adr/](docs/adr/): the decisions behind the design.
- [docs/terminals.md](docs/terminals.md): which terminals `accept` works in.
- [CLAUDE.md](CLAUDE.md): rules for contributors and agents working on Kiripix itself.

## License

MIT; see [LICENSE](LICENSE).
