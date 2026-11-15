---
status: done
milestone: M4
agent: character-pipeline
type: ticket
parent: ../m5/0152-m5-character-layers.md
depends_on: [0164-m4-claude-built-base-models-trial.md, 0165-m4-characters-share-a-base.md]
---

# M4: a Model built from a parameter file

Spec §6.3 (model). From the generator trial in [0164](0164-m4-claude-built-base-models-trial.md), 2026-11-14. Settle after the
Owner's choice there; this is the direction.

## The gap

The trial's generator lives in the art repo (`urban-mystery-club-art/chargen/`): a parameter file (base, shape, parts,
colours) and a Blender script make a rigged GLB in about 2 s, and a second script (`to_kiripix.py`) imports it, picks it,
copies the base's clips and sets the Stage parameters. Kiripix sees only the finished GLB as an imported Variant. So:

- a change to the parameter file, the parts library or the generator doesn't make the character stale;
- the Model can't be rebuilt from the Project alone, although every other Stage's output can;
- `parts`, `eyes` and `height` are worked out by the generator and typed into the Stages by a script.

## What to build

- The `model` Stage accepts **a script-built Source**: a parameter file in the Asset's `src/`, and in `kiripix.toml` the
  generator it belongs to (a script and its library folder, in the Project, run with the Project's Blender). The Stage's
  inputs are the parameter file and the hashes of the script and library, so a change to any makes `model` stale, and
  the rebuild is deterministic work, like `render`.
- The generator stays the Project's own code: Kiripix runs it and reads what it wrote, a Model and a small JSON beside it
  (the materials, the eye materials, the Model's height against its base). Kiripix holds no parts and no game content.
- `palette` `parts`, `render` `eyes` and `height` take their defaults from that JSON when they are unset.
- `new character <name> --from-parameters <file>` (or `import --role parameters`) starts such a character.

## Settled, 2026-11-14

- **The generator goes on** (the Owner): "I like generated characters in test results as a first step". Built after
  [0165](0165-m4-characters-share-a-base.md), in the main session.
- **The generator's code stays in the art repo** (recommended 2026-11-14; built that way): its script, parts library and parameter files are
  game content, in the Project, so `model` can hash them. Kiripix gets only the generic part: running a Project's generator
  and reading what it wrote.
- **Agreed by the Owner:** the `kiripix.toml` format change, and the order a missing value is resolved in (below).
- **Proposed details** (the Owner reviews them with ADR 0012, before code):
  - `kiripix.toml` gains `[character.generators.<name>]` with `script` and `library`, paths in the Project (a settings
    `schema_version` bump, with a migration that adds an empty table).
  - The parameter file is stored in `src/parameters/` (`import <id> <file.toml> --role parameters`), and is the Source:
    no Pick is needed. A character with both a parameter file and an imported Model is refused with a finding.
    `model` gets a `generator` parameter, needed only when the Project has more than one.
  - `model`'s input hash covers the parameter file, the generator's settings, and the content of its script and every
    file under its library. Core hashes those the way it hashes `src/` files; a Stage can't read the Project's tree.
  - Kiripix runs `<Blender> -b --python <script> -- <json>`, with the parameter file, the library and the two paths to
    write: the Model (`.glb`) and a JSON beside it (`materials`, `parts`, `eyes`, `height`: the Model's height over its
    base's). Then `model` normalises the Model as it does an imported one, and `model.json` keeps the JSON as `generated`.
  - A missing value is resolved as: the character's own `asset.toml`, then the generator's JSON, then the base's
    parameters (ADR 0012), then the declared default. The Stages read the JSON through `model.json`, which `render` passes
    on to `palette`.
  - The parameter file names a base body in the generator's own words; Kiripix doesn't map it to a base Asset.
    `new character <name> --from-parameters <file> --base <character>` sets both.
  - A failed generator is `model.generator_failed` (error), naming the script and showing its last 20 lines; one that
    wrote no Model or no JSON says which file is missing.

## Built, 2026-11-14

In the main session, after 0165. Tests: `tests/cli/test_character_generator.py` (14, on the fake Blender, which runs a
test's own generator script with Python by the same protocol). Spec §6.3 has the contract.

- **As proposed above, except:**
  - The parameter file is stored under its own name (`src/parameters/<name>`), not by hash, and may be edited in place.
  - The script gets two paths after `--`, as Kiripix's own Blender scripts do: `<args.json>` (`parameters`, `library`,
    `model`) and `<result.json>`, which it writes (`materials`, `parts`, `eyes`, `height`).
  - `library` is a list of files and folders (one path may be given as text), so a generator's outputs and other
    characters' parameter files needn't be in it.
  - A missing generator, an unknown one, or a script that isn't in the Project is needs-input for the Owner, not a
    failure. `import.model_or_parameters` refuses a second kind of Source.
- **In core:** a Stage may name files of the Project that build the Asset (`StageSpec.project_files`), hashed with its
  inputs, and values that what is built upstream gives its parameters (`StageSpec.generated_params`). The input hash of a
  character with a base or a parameter file also covers which parameters it sets itself. A character with neither keeps
  the hashes it had, so nothing built before goes stale.
- **Checked on real Blender 5.2** (a scratch Project): a small generator script ran through the real launcher, its Model
  matched the base's skeleton, `render` took the height (0.92 of 52 px: 48) and the eyes from its JSON and `palette` the
  parts, and a change to the script made only that character's `model` stale.
- **For the art repo, not done here:** `chargen/generate.py` takes parameter files after `--` and writes into its own
  `out/` folder. It needs the two-path protocol above (read `args.json`, write the `.glb` to `model`, and write `parts`,
  `eyes`, `materials` and `height` as a ratio, not `height_px`, to `result.json`), and `kiripix.toml` needs
  `[character.generators.chargen]`. Then `chargen/to_kiripix.py` isn't needed.
- **The UI** is [0227](0227-m4-ui-a-character-made-from-a-base.md).

## Acceptance criteria

- [x] CLI seam, on a fake generator: a character with a parameter file reaches `render`; editing the file makes `model`
      stale; editing the generator's library does too.
- [x] `parts`, `eyes` and `height` come from the generator's JSON when unset, and a value set by hand wins.
- [x] A generator that fails or writes no Model is a finding that names the script and shows its last lines.
