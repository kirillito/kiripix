# Kiripix

A local pixel asset studio for Godot games. Read [GLOSSARY.md](GLOSSARY.md) and the ADRs in [docs/adr/](docs/adr/)
before changing anything; the full design is in [docs/KIRIPIX_SPEC.md](docs/KIRIPIX_SPEC.md).

## Rules

- **Never commit, stage for a commit, or push.** The owner reviews every change and commits it. Finish by listing the
  changed files.
- **Tickets live in [backlog/](backlog/)** as Markdown files with YAML frontmatter (`status`, `milestone`, `agent`).
  There is no issue tracker.
- Never set `KIRIPIX_TEST_OWNER` or `KIRIPIX_TEST_RECIPES` outside the test harness.

## Commands to run

```
uv sync                          # the locked environment (uv.lock); never add a dependency without updating it
uv run pytest                    # all tests; `uv run pytest tests/cli/test_graph.py` for one file
uv run lint-imports              # the import rule
uv run mypy                      # the type check
uv run kiripix --help            # the CLI (alias kpx)
```

CI runs the last three of these, plus `uv sync --locked`, on Linux and Windows for every push.

## Code conventions

- **Use the glossary's words** in code, messages, finding codes and tests: Asset, Kind, Recipe, Stage, Decision,
  Mask, Layer, Op, Check, Command. Not "item", "pipeline", "step" or "endpoint".
- **Pydantic classes are named after what they describe** (`ProjectSettings`, `StageState`, `Finding`), never
  `*Model`. In names Kiripix controls (code, fields, paths, flags), `model` means only the 3D Model; a Runner's files
  are its weights.
- **The import rule** (spec §13, enforced by `lint-imports`, layers in `pyproject.toml`): `ops` imports nothing else
  from Kiripix; `checks` only `ops`; `recipes` only `runners`, `providers`, `checks` and `ops`; `core` sits on
  `recipes`; `commands` on `core`; `cli` and `server` import only `kiripix.commands`.
- **Every operation is a Command** in `kiripix/commands/`, declared with `@command(...)`. Adapters hold no logic.
  Every result is the envelope `api_version`, `ok`, `data`, `findings`; every finding has a stable dotted `code` and
  exactly one of `fix` (a command an agent can run) or `owner_action` (only the owner can do it). Exit codes: 0 ok,
  1 error, 2 check failed, 3 needs the owner, 4 busy. A REST transport route (file route, event stream, cancel) and
  the `serve`/`ui` Launchers are not Commands (ADR 0007). They change nothing in the Project and hold no logic.
- **Long work is cancellable** (ticket 0031). Never `time.sleep` in core, a Stage or a Runner: wait on the Command's
  cancel token instead. A loop that can take more than about a second checks the token between chunks (tiles,
  frames, batches). A Runner passes it on to its engine (ONNX Runtime: set `RunOptions.terminate` on cancel). A
  cancel leaves nothing half-written, because every write is atomic.
- **Status is derived, never stored** (ADR 0005). Nothing writes status to `asset.toml` or `kiripix.toml`.
- **Every write is atomic** (`kiripix.core.atomic`); `.jsonl` files are append-only, one object per line, LF.
- **Data files carry `schema_version`.** A format change bumps it and adds a pure migration from N to N + 1 in
  `kiripix/core/settings.py`. Unknown keys are an error.
- **Ops are pure**: numpy arrays in, arrays out, no I/O. Core's own image I/O lives in `kiripix.core.images`. A
  Stage in `recipes` can't import core, so it reads its inputs and writes its outputs itself (PIL), and only inside
  the output folder core gives it. Core swaps that folder into place whole, so the Stage's writes are atomic too.

## Tests

- **CLI seam** (`tests/cli/`): run `kiripix … --json` as a subprocess in a temporary Project and check the JSON, the
  exit code and the files. Never import internals to check them. Stage-graph tests use the test Kind `demo` from
  `tests/fixtures/kiripix_test_recipes.py`, loaded through `KIRIPIX_TEST_RECIPES` by the harness only.
- **Golden seam** (`tests/golden/`): Ops called directly, outputs compared pixel-exactly with PNGs in git LFS.
  `uv run pytest tests/golden --update-golden` rewrites them; the owner reviews the images before committing.
- A new Command needs a sample in `tests/cli/test_contract.py`, or the contract test fails.

## Subagents: cost rules

The agents in `.claude/agents/` are expensive. Each one starts with no context and re-reads the project.
- **Delegate only when the ticket's `agent:` field names an agent, or the owner names one.** Otherwise do the work in
  the main session, whatever the task looks like.
- **One agent per ticket.** Don't fan a ticket out to several agents. If a ticket needs two areas, say so to the owner;
  it should probably be split.
- **Don't call `reviewer` after every change.** The owner asks for a review, or a ticket names it.
- **Small changes stay in the main session:** typo fixes, renames, doc edits, one-file changes, running tests,
  answering questions.
- Agents never call other agents.

| Agent | Area |
|---|---|
| `reviewer` | Read-only pre-review against the spec, ADRs and glossary; ADR drafts; splitting specs into tickets |
| `core-engineer` | core, commands, cli, server |
| `imaging-engineer` | ops, checks, room and prop image stages |
| `ml-engineer` | runners, providers, pinning, VRAM, licences, cost |
| `qa-engineer` | tests at the CLI and golden-image seams; the acceptance-test harness |
| `godot-export` | export, the Manifest |
| `ui-engineer` | web/ |
| `character-pipeline` | the character recipe, blender/ |
