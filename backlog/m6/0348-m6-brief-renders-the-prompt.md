---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
---

# M6: the brief renders the room's prompt, without a Provider

Spec §4 (`bible.md`, `prompts/`), §6.1 (brief: "Renders the generation prompt from the kind's template and the style
bible") and §14 (M6, rooms at chapter scale). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md).

## The gap

Once first passes run without the Owner ([0331](0331-m6-first-passes-over-a-list-of-rooms.md)), making each room's
Source is the Owner's biggest cost per room. At the M5 gate no new ch01 room had one. The spec says the brief renders the
prompt, but `kiripix/recipes/room.py` says that waits for `gen`. Today the prompt is written in the game's `room-brief` skill
(`../urban-mystery-club`), by hand, for each room. Its scale rules, such as people about 110–130 px tall per 1376 px image
(the game's ISS-016), live there and nowhere in Kiripix.

## What to build

- **The brief renders a prompt** from `prompts/room.<ext>` and `bible.md` in the Project (spec §4), filled from the brief's
  fields (size in tiles and px, the canvas's size and aspect, mood, Exits and their sides, notes). The output is `prompt.txt`
  in the brief's output, and `show` returns it. A template or bible change makes the brief stale through its input hash.
  With no template, there's no prompt and no error.
- **The template engine:** the spec names Jinja2. Use it (added to `pyproject.toml` and `uv.lock`) or Python's
  `string.Template` if the template needs nothing more. Record which, and why.
- **A missing field** the template uses is an error naming it (`brief.prompt_field`), never an empty string in the prompt.
- **The art Project's first template:** port the game's `room-brief` rules for a ch01 room into `prompts/room.*` and
  `bible.md` (with the Owner), and record here how the rendered prompt compares with one the skill wrote for the same room.
- Spec §6.1's brief row says what is built, and §4 the template's fields.

## Acceptance criteria

- [ ] CLI seam: a test Project with a template renders `prompt.txt`; changing `bible.md` makes `brief` stale; a missing
      field is `brief.prompt_field`.
- [ ] A ch01 room's rendered prompt, side by side with the skill's, recorded here, and the Owner's view.
