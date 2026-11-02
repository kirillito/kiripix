---
status: split
milestone: M0
type: spec
---

# M0: skeleton

Background: [the Kiripix spec](../docs/KIRIPIX_SPEC.md) (§14 M0), [the glossary](../GLOSSARY.md) and
[the ADRs](../docs/adr/), especially ADR 0005 (status is derived) and ADR 0006 (one Command registry). Use the
glossary's words in code, messages and tests.

## Problem Statement

The owner is about to build a pixel asset studio that both they and a team of AI coding agents will drive, and that
UIs will later be built on. Nothing exists yet. If the first code is written Command by Command, with output formats
and conventions made up as they go, every later milestone pays for it: agents can't rely on the output, the UI and
the CLI drift apart, and status, locking and data versioning get bolted on afterwards. The owner needs a skeleton that
fixes these foundations before any real asset work starts.

## Solution

A working `kiripix` tool, with no image recipes yet, that already behaves the way every later Command must:
- One Command registry; the CLI is generated from it.
- Every Command answers in versioned JSON, with stable exit codes and stable finding codes.
- The tool describes itself (`describe`, `schema`), so an agent can drive it without reading the source.
- `init`, `new` and `status` create and show a real project on disk.
- A stage graph whose status is always derived from hashes, never stored.
- Project, Asset and GPU locks that make concurrent writers safe.
- The palette and the quantise Op exist, with golden-image tests.
- The repo has its conventions (CLAUDE.md, a locked environment, LFS, CI) and the pinned external versions.

## User Stories

**Project setup**
1. As the owner, I want `kiripix init` to create a complete project folder, so that I start from the documented layout instead of building it by hand.
2. As the owner, I want `init` to write a `kiripix.toml` with sensible defaults (resolution, tile size, palette path, body, Mask definitions, export target), so that I only change what my game needs.
3. As the owner, I want `init` to write `.gitattributes` (LFS for binaries; `merge=union` and LF for `history.jsonl` and Decision journals) and git-ignore entries for `work/` and `.kiripix/`, so that git handles the project correctly from the first commit.
4. As the owner, I want `init` to refuse to overwrite an existing project, so that I can't wipe my work by running it twice.
5. As the owner, I want `kiripix.toml` and `asset.toml` to carry a schema version, so that later Kiripix versions can migrate my files instead of breaking on them.
6. As the owner, I want an older file to be migrated in memory when it's read, and written back only by a Command that writes, so that reading never silently rewrites my files.
7. As the owner, I want a malformed or invalid `kiripix.toml` to fail with the field, the problem and a fix, so that I can repair it quickly.

**Assets**
8. As the owner, I want `kiripix new room queen_west_alley --view top` to create the Asset `room.queen_west_alley` with its folder, `asset.toml`, empty `history.jsonl` and `decisions/`, so that it's ready for its Recipe.
9. As the owner, I want Asset IDs validated (`<kind>.<name>`, lower-case letters, digits and underscores), so that IDs stay stable and safe as Godot names.
10. As the owner, I want `new` to refuse a duplicate ID, so that two Assets can never share one.
11. As the owner, I want `new` to refuse an unknown Kind and list the known ones, so that a typo is caught immediately.
12. As the owner, I want `view` to be required for rooms and refused for Kinds that don't have it, so that an Asset never has a meaningless parameter.
13. As the owner, I want `asset.toml` to hold only the Kind and parameters, never stage status, so that it never conflicts between branches (ADR 0005).

**Status**
14. As the owner, I want `kiripix status` to show every Asset with each stage's status, so that I see the whole project at a glance.
15. As the owner, I want `status --kind room` to filter by Kind, so that the board stays readable as the project grows.
16. As the owner, I want status computed from input hashes every time, so that a fresh checkout or a branch switch always shows the truth.
17. As the owner, I want file hashes cached by modification time and size, so that `status` stays fast on a large project.
18. As the owner, I want deleting `.kiripix/` to be harmless (it only makes the next status slower), so that the cache is never a source of truth.
19. As the owner, I want a stage whose input changed to show as `stale`, and a stage that never ran as `todo`, so that I know what needs rebuilding.
20. As the owner, I want `failed` remembered only in the git-ignored cache, so that a fresh checkout never shows someone else's old failure.

**Running stages**
21. As the owner, I want `kiripix run <id>` to run every stale or todo stage in order, and stop at the first that needs input, needs review or fails, so that a rebuild is one command.
22. As the owner, I want `run <id> <stage>` to run one stage, and `--force` to re-run it even when it's done, so that I can redo a stage on purpose.
23. As the owner, I want a stage whose output already matches its inputs to be skipped, so that re-running is cheap.
24. As the owner, I want every run appended to the Asset's `history.jsonl` (stage, parameters, input hash, duration, outcome), so that I can see what happened and when.
25. As the owner, I want every output written atomically, so that a crash or a Ctrl+C never leaves a half-written file that looks done.
26. As the owner, I want Ctrl+C to stop a run cleanly, release its locks and exit with a clear result, so that cancelling is always safe.

**The JSON contract (agents)**
27. As an AI coding agent, I want every Command to accept `--json` and print exactly one JSON object on stdout, so that I can parse every result the same way.
28. As an AI coding agent, I want every result to carry `api_version`, so that I can tell when the contract changed.
29. As an AI coding agent, I want stable exit codes (0 ok, 1 error, 2 check failed, 3 needs the owner, 4 busy), so that I can branch without parsing text.
30. As an AI coding agent, I want every error and finding to carry a stable string `code`, a message, a position where there is one, and a `fix`, so that I can act on it directly.
31. As an AI coding agent, I want findings that only the owner can resolve to say so (`fix: null` and an `owner_action`), so that I report to the owner instead of guessing.
32. As an AI coding agent, I want `kiripix describe project` to list the Kinds and their Recipes, so that I learn what the project can contain without reading the spec.
33. As an AI coding agent, I want `kiripix describe <kind>` to list each stage with its parameters (types, defaults, ranges), the Decisions it accepts and its Checks, so that I know how to drive every stage.
34. As an AI coding agent, I want `kiripix schema [command]` to print the JSON Schemas of Command inputs and outputs, so that I can validate what I send and what I get back.
35. As an AI coding agent, I want `kiripix next <id>` to return either a runnable command or an explicit owner action, so that I never have to work out the next step myself.
36. As an AI coding agent, I want `--help` on every Command to be complete and accurate, because it's generated from the same registry.
37. As an AI coding agent, I want `--progress=jsonl` to stream progress events on stderr for long Commands, so that I can show progress while stdout stays one clean object.

**Concurrency**
38. As an AI coding agent, I want a writing Command to fail at once with exit code 4 and the holder's details when an Asset is locked, so that I don't corrupt work the owner is doing in parallel.
39. As an AI coding agent, I want `--wait <seconds>` on writing Commands, so that I can wait for a lock instead of failing.
40. As the owner, I want a lock left behind by a crashed process to be taken over automatically, so that I never have to delete lock files by hand.
41. As the owner, I want project-wide writes (`kiripix.toml`, the palette) to take a project lock, and locks always taken project first, then Asset, so that two writers can never deadlock.
42. As the owner, I want `run --all` to lock one Asset at a time, so that I can keep working on other Assets during a long run.
43. As the owner, I want read-only Commands (`status`, `describe`, `schema`, `next`) never to take a lock, so that I can always look at the project.
44. As a future Runner or Blender job, I want a GPU lock held while I'm loaded, so that two jobs never fill 8 GB of VRAM together.

**Palette and Ops**
45. As the owner, I want my palette loaded from a GIMP `.gpl` file, with `.hex` imported, so that I can use palettes from common tools.
46. As the owner, I want a palette with duplicate colours, colours with alpha, or no colours to fail with a clear finding, so that a broken palette is caught before it's used.
47. As the owner, I want `kiripix op quantize <in> <out>` to map an image to the palette in OKLab, so that I can test the palette on any image before Recipes exist.
48. As the owner, I want quantise to offer strict mapping and ordered dithering (Bayer 2, 4 and 8), so that I can compare both looks.
49. As the owner, I want quantise to be deterministic and bit-exact on my machine and in CI, so that "repeatable" holds from the first Op.
50. As the owner, I want quantise to keep fully transparent pixels transparent and refuse partial alpha with a finding, so that pixel art never gets semi-transparent pixels.
51. As the owner, I want `kiripix op` to report a palette conformance summary (pixel count off palette, the first positions), so that I can check any image.

**Repo conventions**
52. As the owner, I want CLAUDE.md to say that agents never commit and that I review and commit every change, so that every agent follows the rule.
53. As the owner, I want CLAUDE.md to point agents to the glossary, the ADRs and the spec, and to state the coding conventions (Pydantic classes named after what they describe, never `*Model`; `model` means only the 3D Model in names Kiripix controls), so that agents write consistent code.
54. As the owner, I want the environment locked with uv (`uv.lock`), so that every machine and CI run uses the same numpy and OpenCV and golden images stay bit-exact.
55. As the owner, I want CI to run the tests and the import rule on every push, so that a broken layer boundary is caught at once.
56. As the owner, I want the import rule enforced by a tool, not by memory, so that Ops and Checks stay pure and the adapters hold no logic.
57. As the owner, I want git LFS configured in the repo for golden images, so that test images don't bloat history.

**Pinned versions and licences**
58. As the owner, I want the Godot and Blender versions pinned and recorded, so that exports and renders are reproducible.
59. As the owner, I want every planned Runner's licence verified and recorded (SAM 2 sizes, BiRefNet, Depth Anything V2 sizes, LaMa), so that I never build on a non-commercial model by accident.
60. As the owner, I want `isatty` tested in each terminal I use (Windows Terminal, the VS Code terminal, Git Bash with mintty) and the result recorded, so that I know where owner-only Commands will work before M1 depends on it.

## Implementation Decisions

**Modules built in M0**
- **commands**: the registry. Each Command declares a name, typed input and output (Pydantic), its kind (writing, Probe or owner-only), its MCP exposure (exposed, hidden or owner-only), its CLI metadata (positional arguments, short aliases) and which locks it takes. Input types support file paths in and image paths out; output types can emit progress events. Only the CLI adapter is generated in M0, but the registry shape must already support REST and MCP (ADR 0006).
- **cli**: a Typer adapter generated from the registry. It holds no logic: it parses arguments into the Command's input type, calls it, and renders the result as text or as `--json`. The exit code comes from the result, never from the adapter.
- **core**: project and Asset loading and saving (Pydantic, versioned, with migrations), Kinds and Recipes as declarations, the stage graph, hashing with the mtime-and-size cache, derived status, history appends, atomic writes and locks.
- **recipes**: the room, prop and character Recipes declared with their stage lists, parameters, Decision schemas and Checks, so that `new` and `describe` work. No stage does real image work in M0 (see Out of Scope).
- **ops**: palette load and save, OKLab conversion, nearest-colour mapping, ordered dithering, and the conformance report. Pure functions, arrays in and arrays out.
- **checks**: the palette Checks on a palette file and on an image, returning findings.

**The import rule**, enforced in CI by an import-linting tool: `ops` and `checks` import nothing else from Kiripix; `recipes` use `ops`, `checks`, `runners` and `providers`; `commands` uses `core` and `recipes`; `cli` and `server` use only `commands`.

**The JSON contract**
- One `api_version` for the whole tool, starting at 1.
- Every result has `api_version`, `ok`, a Command-specific `data` object, and `findings` (a list, possibly empty).
- A finding has `code` (stable, dotted: `palette.off_palette`, `asset.duplicate_id`), `severity`, `message`, an optional `position` (Asset, stage, file, x/y or a field path), `fix` (a command string, or null) and `owner_action` (a string, or null). Exactly one of `fix` and `owner_action` is set.
- Exit codes: 0 ok, 1 error, 2 check failed, 3 needs the owner, 4 busy.
- `--json` prints exactly one object on stdout; `--progress=jsonl` writes events (`{event, stage, done, total, message}`) on stderr.
- `schema` output is generated from the same Pydantic types the Commands use, so it can't drift from them.

**Commands in M0:** `init`, `new`, `status`, `describe`, `schema`, `next`, `run`, `op quantize` (and `op conformance`).

**Stage graph and status (ADR 0005)**
- A stage declares its inputs: files, upstream stage outputs, named project settings, parameters and (later) Decisions and pinned results. Its input hash is the hash of all of these.
- A stage is `todo` with no recorded output, `stale` when the current input hash differs from the one its output was produced from, `done` when they match. `failed`, `needs-input` and `needs-review` come from the cache or from the stage itself; in M0 only `failed` can occur.
- The input hash an output was built from is stored next to the output in `work/` or `out/`, not in `asset.toml`. Status is never written to a committed file.
- The hash cache, last-run failures and locks live in the git-ignored `.kiripix/`. Deleting it loses nothing.
- `history.jsonl` entries are one JSON object per line, LF, appended only.

**Locks**
- Three kinds: project, Asset, GPU. Lock files in `.kiripix/` record the process ID, the host and the start time.
- A lock whose process is gone on this host is stale and is taken over; a lock from another host is never taken over automatically.
- Order is always project, then Asset, then GPU. Writing Commands declare their locks in the registry, and the core takes them; Commands never take locks themselves.
- Busy: exit code 4, with the holder in `data`. `--wait <seconds>` polls until the timeout, then exits 4.

**Data files**
- `kiripix.toml` and `asset.toml` have a `schema_version`. Migrations are pure functions from version N to N+1, run in memory on read, and written back only when a writing Command saves the file.
- Unknown keys are an error with a finding, not ignored, so typos surface.

**Palette and quantise**
- `.gpl` is the stored format; `.hex` imports. A palette is an ordered list of opaque sRGB colours with optional names.
- Nearest colour is by Euclidean distance in OKLab, with ties broken by palette order, so results are deterministic.
- Dithering is ordered Bayer (2, 4, 8) applied in OKLab before the nearest-colour step, with a strength parameter.
- Alpha: 0 stays 0, 255 is mapped, anything else is a finding (`image.partial_alpha`) and the Op refuses.

**Repo**
- uv with a committed `uv.lock`; Python 3.12.
- CI on every push: tests, the import rule and a type check. Golden images through git LFS. CI never commits or pushes anything.
- CLAUDE.md: agents never commit (the owner reviews and commits); read the glossary and ADRs first; naming conventions; never set `KIRIPIX_TEST_OWNER`; tickets live in `backlog/`.
- The pinned Godot and Blender versions, the Runner licence table and the `isatty` results are recorded in the spec (Godot and Blender) and in a short docs note (licences, terminals).

## Testing Decisions

**What makes a good test:** it drives Kiripix the way an agent does and checks only what an agent can see: the JSON result, the exit code and the files in the project folder. It never imports internals to check them, so a refactor that keeps behaviour keeps the tests green.

**Seam 1: the CLI.** Each test creates a temporary project folder, runs `kiripix … --json` as a subprocess, and checks the JSON, the exit code and the files on disk. This covers `init`, `new`, `status`, `describe`, `schema`, `next`, `run`, data validation and migrations, derived status (change an input file, then see `stale`), cache deletion, atomic writes (kill a run mid-write, then see no completed output), and history.
- Locks are tested with two real processes: one holds a lock (a test stage that waits on a signal file), and the other gets exit code 4, or succeeds with `--wait` once the first releases. Stale takeover is tested by leaving a lock with a dead process ID.
- The stage graph needs stages that actually run before any image Recipe exists. Tests register a **test Kind** with trivial deterministic stages (copy, concatenate, wait, fail on purpose) through a test-only hook, `KIRIPIX_TEST_RECIPES`, which names a Python module to load. Like `KIRIPIX_TEST_OWNER`, it's for the test harness only, and CLAUDE.md says agents must never set it outside tests.
- A **contract test** walks every Command in the registry and checks that its `--json` output validates against its `schema`, and that `--help` exists. That way, a new Command can't silently break the contract.

**Seam 2: the Ops**, palette load and quantise, with golden images: fixed input images and palettes, and expected output PNGs compared pixel-exactly. Cases: strict mapping, each Bayer size, tie-breaking, transparent pixels, the partial-alpha refusal, an image already on the palette (output equals input), and a palette with duplicates.

**Also in CI:** the import rule, and a type check.

**Prior art:** none; the repo has no code yet. These tests set the pattern every later milestone follows.

## Out of Scope

- Real stage work: `import`, `gen`, `pick`, `fit`, `layers`, `masks`, `place`, `reach`, `export`, and every Runner and Provider. The Recipes are declared but not runnable (their stages report `needs-input` with "not implemented until M1" or later).
- `set`, `decide`, `override`, `undo`, `redo`, `accept` and the Decision journal (M1). Decision schemas are declared in `describe`, but nothing records Decisions yet.
- The owner-only guard (M1), apart from the `isatty` investigation.
- `serve`, the REST adapter, SSE, Probes, the warm Runner and the UI (M1). The MCP adapter (M4).
- Pinning Runner and Provider calls (M1 with SAM 2).
- The Manifest and anything to do with Godot export (M1).
- The agent acceptance test (its first run is at the M1 gate). M0's tests are written so that it can reuse their fixtures.
- `.ase` palette import, palette extraction (k-means), and every Op other than palette and quantise.

## Further Notes

- The **test Kind hook** (`KIRIPIX_TEST_RECIPES`) is a decision made in this spec, not in the main spec. It's needed because the stage graph has to be tested through the CLI before any real Recipe can run. If the owner prefers not to have it, the alternative is to implement one real deterministic stage in M0.
- The JSON contract fixed here (result envelope, finding shape, exit codes) is what M1's REST adapter and the agent acceptance test depend on. Changing it later means bumping `api_version`.
- An agent can split this spec into tickets in `backlog/` along these lines: repo and CLAUDE.md, registry and CLI adapter with the contract, data files and migrations, `init`/`new`/`status`/`describe`, stage graph and status, locks, palette and quantise, and the versions/licences/terminals research.
