# A character can be made from a base

**Status: accepted** (2026-11-14, by the Owner, for ticket 0165; built the same day. What building it changed is marked
"as built").

Today each character does the whole round trip on its own: its Model, its rig (often a Mixamo trip), its clip-source files
and every `clip` Decision. NPCs and outfits built on one body repeat all of it. The stop-gap, `kiripix clips copy` (ticket
0171), copies the Decisions and files with no link, so a change on the first character is never carried over. The
generator trial (ticket 0164) made six NPCs on mc03's two rigs and showed what sharing needs: the NPC's Model carries the
body's skeleton with its rest pose changed on purpose (build, age, height, posture), and the body's clips still play,
because a clip's rotations are relative to rest.

We considered three ways:

1. **Keep copying** (`clips copy`, run again with `--replace`). No core change, but nothing goes stale when the body's clips
   change, every NPC holds its own copy of the clip sources, and every Stage parameter is set by hand on each.
2. **A layer or Variant of the body**, inside the body's Asset. A body would hold dozens of NPCs, each with its own Model,
   journal and export, in one folder and under one lock. It also mixes this with 0152's open question 3 (how a layer is
   held), which the layer trial still has to answer.
3. **A character names a base character** (`params.base` in its `asset.toml`), and some of its Stages read the base's
   files, Decisions, parameters and built outputs as **inputs that cross Assets**, hashed like any other input.

We chose 3.

## The rule

- **`base` is an Asset parameter** of the character Kind: `kiripix new character guard --base character.body_m`, or
  `base = "character.body_m"` under `[params]` in `asset.toml`. The base must be a character, not the Asset itself, and
  have no base of its own (one level only). Otherwise `asset.base_invalid` (error), with the reason.
- **A Stage declares what it reads of the base**, in `StageInputs.base`: `files` (globs in the base's folder), `decisions`
  (the base Stages whose current Decisions come before its own) and `built` (the base Stages whose built output it reads).
  Core adds all of these to the Stage's input hash: the files by content hash, the Decisions as the journal hash does, and
  each `built` Stage's input hash. A Stage that declares nothing reads nothing of the base, so rooms, props and sprites
  don't change.
- **A `built` base Stage must be `done`.** Until it is, the Stage is `needs-input`, with the command
  `kiripix run <base> <stage>`. `run --all` builds a base before the characters made from it.
- **Parameters fall back to the base.** For every Stage of a character with a base, a parameter the character doesn't set
  takes the base's value from the base's `asset.toml`, then the declared default. One level only, as for the base itself.
  A parameter can opt out (`ParamSpec.from_base` false): `render` `height`, which is scaled (below), never copied, and, as
  built, `model`'s `facing` and `generator`, which describe the character's own file.
  Parameters are already part of the input hash, so a changed base parameter makes the character's Stage stale. As built,
  the hash of a character with a base also covers which parameters the character sets itself, because a Stage may prefer
  another value to the base's (a generated Model's, ticket 0224) unless the character set one.
- **Decisions add on top.** A Stage that lists itself in `decisions` sees the base's current Decisions first, then its
  own. The character's journal holds only its own: `undo` never touches the base, and a changed clip stays on the
  character (0156: a `clip` under a name the base has replaces it). A new `remove` Decision of `clips` takes a clip away by
  name, as `remove` does for a Loop (ADR 0011), together with every transition from or to it, so removing a base clip
  never leaves a `clips.transition_missing_clip`. `show` marks each Decision that came from the base.
- **Files are referenced, not copied.** The base's clip sources stay in the base's `src/clips/`. A character's own clip
  source of the same stored name is the same bytes, and one of another name is its own.

## What each character Stage reads

| Stage | Reads of the base | So |
|---|---|---|
| `model` | nothing | The character's own Model, imported or (ticket 0224) generated. |
| `rig` | `built: rig` | The Model's own armature is compared with the base's skeleton by **bone names and hierarchy**, not by rest proportions, which a generated Model changes on purpose. No rigged file and no Mixamo trip. Every bone of the base must be in the Model, by its exact name (clips bind by name), with the same parent. Extra bones (a skirt's, a hair chain's) are allowed: the base's clips don't move them. A mismatch is `rig.base_mismatch`, naming the missing and re-parented bones. A Model with no armature is `rig.missing`, saying the Model must be built on the base's skeleton. As built, the base's roles (its `mapping`, with its `bone` Decisions) hold for the character too. |
| `clips` | `files: src/clips/*`, `src/things/*/*`, `decisions: clips` | The base's clip sources and clips, plus the character's own. The base's held things too (ticket 0312): a thing of the character's own wins the base's of the same ID. Stale when the base's clip sources or clips change. As built: a clip source of the character's own wins a base's of the same name; and only clip-source files cross, so a base clip that plays an action of the base's own Model file resolves against the character's Model, and is `clips.source_missing` when that has no such action. |
| `render` | `files: src/clips/*`, `src/things/*/*`, `imported.jsonl`, `built: rig` | The base's held things, numbered before the character's own, and the base's `imported.jsonl`, which orders them and names each one's current Variant (tickets 0312, 0313), so a re-import on the base makes the render stale. `height`, when the character doesn't set it, is the base's height (its own `height`, or the Project's `[character] height`) times this character's rig height over the base's, rounded half up to whole px. A rig's height (`rig.json` `height`) is the height of the file that carries the armature, in the rest pose, as imported into Blender, before normalising, so a posture baked into the rest pose counts: the rigged file's when there is one, else the Model's (`model.json` gains `source_height`). Bands, shadow and eyes fall back as above. |
| `palette`, `finish`, `sheet`, `export` | nothing new | Parameters fall back as above (`parts`, outline colour, eyes); everything else is the character's own. |

## Consequences

- **Core change:** `AssetGraph` loads the base's `AssetGraph` when a Stage declares `StageInputs.base`, and adds a `base`
  view to `StageRun` (the base's ID and folder, the files found, the Decisions, the folders of its `built` Stages and its
  parameters). Recipes still don't import core. A Stage reads a base's output only through that view, read-only.
- **Status stays derived** (ADR 0005). A change on the base makes each character made from it stale through its input
  hash. Nothing is written to the character when the base changes.
- **A base changed while a character builds:** the character reads the base's swapped-in output (every write is atomic)
  and is stamped with the hash it read, so it is stale afterwards if the base moved. Running a character takes no lock on
  its base.
- **A change to the base's Model** makes the character's `rig` stale, through the base `rig`'s input hash, and its
  `render` (the height). That is a few spurious rebuilds, accepted to keep one rule: a `built` input counts by its input hash.
- **`rig.json` schema 2** records each bone's parent, so the comparison has the base's hierarchy, and the rig's height. A
  base's `rig.json` from schema 1 makes the character's `rig` needs-input, with the rebuild as its command
  (`kiripix run <base> rig --force`).
- **The height is the rig file's, not the Model's** (as built). The draft compared the two Models' heights. On the Owner's
  mc03 the base's Model file is 1.78 units tall and its rigged file from Mixamo 2.0 (the size of Kiripix's upload), and a
  Model on the base's skeleton is built from the rigged file: against the Model, an NPC of 0.96 of the body came out at 56 px
  of 52; against the rigged file, at 50. So `render` reads the base's `rig`, not its `model`.
- **Checked on the Owner's files** (2026-11-14, Blender 5.2, a scratch Project): mc03_male's rigged FBX and two generated
  NPC GLBs have the same 65 bones under the same parents, and the base's clips play on an NPC from the base's folder.
- **Parameters that name materials** (`palette` `parts`, `render` `eyes`, `finish` `watch_parts` and `line_skip`) fit a
  character whose materials are the base's, as every generated character's are (the generator's material slots). A
  hand-made Model with other materials sets its own; until it does, the Stage reports the material it can't find.
- **`show`, `describe` and the UI** give each parameter's value with where it came from (the character, its base or the
  default), so a value nobody typed on the character isn't a mystery.
- **`clips copy` stays** (the Owner, 2026-11-14), for characters that share clips but not a body. A copy onto a character
  with a base adds Decisions of its own, on top of the base's.
- **Not covered:** a base of a base; layers over a body (0152, still open after the layer trial 0153); ramps from another
  character (`ramps_from`, which the Project ramp table of ticket 0166 stands in for). The `StageInputs.base` mechanism
  is meant to carry them later.
