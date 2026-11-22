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

## Result

Built (the code and the CLI-seam tests; the two acceptance items about the art Project stay open, so `status` stays `todo`):

- **Engine: Jinja2** (`jinja2>=3.1` in `pyproject.toml`, locked in `uv.lock` with MarkupSafe). `string.Template` can't loop over
  the Exits or branch on the view, and the room-brief rules (scale per view, a line per Exit, notes only when there are any)
  need both. It runs in a `SandboxedEnvironment` with `StrictUndefined`, so a template can't reach Python and a missing field
  never becomes an empty string. It is imported inside the render, so no other Command pays for it.
- `kiripix/recipes/room_prompt.py`: finds `style/prompts/room.<any extension>`, renders it with the brief's fields and `bible`,
  writes `prompt.txt` (LF) beside `brief.json`. No template: no file, no error. `show` lists it in the brief's `outputs`.
- New brief parameters, all at a default that is left out of the hash: `notes`, `exits` (`name:side,...`), `canvas_width` and
  `canvas_height` (default 1376 x 768, the image the prompt asks for). The canvas is a brief parameter and not read from
  `[extend] canvas`, because declaring that setting would change every brief's input hash.
- The template and `style/bible.md` are the brief's `project_files`, so a change to either makes `brief` stale. They are named only
  when the Project has a room template.
- Findings: `brief.prompt_field` (the template names a field the brief lacks; `owner_action`, exit 3: the template is the Owner's),
  `brief.prompt_template` (Jinja2 syntax error), `brief.exit_side` (`exits` names a side that isn't top, right, bottom or left).
- **No `StageSpec.version` bump, on purpose.** The brief writes exactly what it did before in a Project with no room template, and
  a bump would make every room's whole chain stale. In a Project with a template the input hash changes by itself (the template's and
  bible's content), so no room keeps a stale output. Consequence to know: when the Owner first adds `room.<ext>`, `brief` of each
  room goes stale and so does everything downstream of it (a Stage's hash covers its upstream hashes), as it does for any brief change.
- Spec §4 (fields of the template) and §6.1 (brief row) say what is built. Tests: `tests/cli/test_brief_prompt.py`.

### Still open, needs the Owner

- Port the game's `room-brief` rules for a ch01 room into the art Project's `style/prompts/room.j2` and `style/bible.md`. Not done: the
  art Project and `../urban-mystery-club` are the Owner's. `docs/examples/room-prompt.j2` is a starting point (its scale rule is a
  placeholder, not the game's ISS-016).
- Run `kiripix run <room> brief` on a ch01 room, record here how `prompt.txt` compares with the one the skill wrote for the same room,
  and the Owner's view. If a rule needs a field the brief doesn't have (for example the room's lighting), say which: it is one more
  brief parameter.
