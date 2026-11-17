---
status: todo
milestone: M5
agent: core-engineer
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0241-m5-portrait-trial.md]
---

# M5: the `portrait` Kind, its emotions, and `import --emotion`

Part of [0240](0240-m5-portrait-kind.md): the Kind, `brief` and `source` with its emotions. The Stages after `source` are
[0243](0243-m5-portrait-recipe.md).

## What to build

- **The Kind:** `kiripix new portrait <name>` and `describe portrait`. The recipe's Stages are declared, and those after
  `source` are stubs until 0243. `new --help` lists the Kind (the M4 gate found `sprite` missing there, 0250).
- **`[portrait]` in `kiripix.toml`:** `canvas` (w, h) and the default `anchor`. Bump `schema_version`, with its migration.
- **`brief`:** the canvas and anchor (the Project's unless set), the `fallback` emotion (default `neutral`).
- **`source`:** the neutral Source is a Pick, as a Prop's is. An `emotion` Decision declares an emotion ID. `import <id> <png>
  --emotion <e>` stores a Variant under `src/emotions/<e>/`, and `pick <id> <v> --emotion <e>` picks it, recording the
  neutral Source's hash. A new neutral Source puts every emotion's pick in needs-input, with "the edit was made on another
  Source", as Looks do. `remove` and `rename` an emotion before export; after export the ID is frozen (ADR 0003).
- **Owner input:** picking an emotion's Variant among several is the Owner's, as a Pick is. An agent may pick a lone Variant.
- Findings: `portrait.emotion_unknown`, `portrait.emotion_unpicked` (needs-input, naming the emotion),
  `portrait.emotion_duplicate`.

## Acceptance criteria

- [ ] CLI seam: a portrait with a neutral Source and two emotions, each imported and picked, shows them in `show`. A new
      neutral Source makes both needs-input.
- [ ] `import --emotion` on an undeclared emotion fails with a fix that declares it.
- [ ] Contract samples for the new Decision and the import flag. The glossary gets **Portrait** and **Emotion**, and spec §3
      moves `portrait` out of "later".
