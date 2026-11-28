---
status: done
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

- [x] CLI seam: a test Project with a template renders `prompt.txt`; changing `bible.md` makes `brief` stale; a missing
      field is `brief.prompt_field`.
- [x] A ch01 room's rendered prompt, side by side with the skill's, recorded here, and the Owner's view.

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

### The art Project's template: drafted, waiting for the Owner (2026-11-23)

Drafted in `0348-trial/` (removed from this repo since; it is in git at `94077b5`), not yet copied into `urban-mystery-club-art`: adding `style/prompts/room.j2` makes every
room's `brief` stale there, and with it each room's whole chain, so the Owner copies it when they accept it.

- `room.j2` carries the skill's (v1) per-room rules: the projection reference line, the camera and
  "not isometric" lines, the cutaway box for a room narrower than the screen (640), scale said twice (adult 52k px and its share
  of the image height, the door 32k x 64k, the back wall 80k), an exit per `exits` entry on the back wall or as a gap in the
  bottom edge, the room's `notes`, and the grid line. `bible.md` carries the rules that don't depend on the
  room: the sun from the upper left (0070), lights with causes, no figures, signage only, blank surfaces, the style line.
- Rendered on a copy of `room.annex_bedroom` (ch01-001) with `exits = "living_room:top"` and `notes` holding the skill's room
  and gameplay-spot paragraphs: `annex_bedroom.prompt.txt`, beside the skill's prompt in
  `urban-mystery-club/.claude/skills/room-brief/rooms/annex_bedroom.md`.

**How it compares with the skill's prompt for the same room:**

| | Skill (hand-written) | Rendered |
|---|---|---|
| Camera, projection, empty room, text, style | the same rules, in the same words | the same (from the template and bible) |
| k (source px per game px) | 3.74, from P = 368: the room's planned width before the fit | 4.10, from the brief's `width` 336, the fitted Plate |
| Adult / door / back wall | 194 / 120 x 239 / 300 px | 213 / 131 x 262 / 328 px |
| Room's share of the width | "about 60%" (by eye) | 52% (336 / 640) |
| Furniture sizes | each in px from the size table (bed 120 px wide, closet 180 x 240) | only what `notes` says; the template has no furniture fields |
| Light | the window's sunbeam "toward the lower right" (written before 0070) | "from the upper left, shadows up and to the right" (0070's rule) |

The k gap is real: the skill picks P before painting (the room's size at ~30 px per metre), the brief knows only the Plate it
was fitted to. For a room not yet painted they're the same number if the brief's `width` is set to P; for a room already fitted
at a whole k (the bedroom's k = 4), the rendered prompt asks for a slightly larger adult than the fitted pick has.

### Accepted: the art Project's template is a merge (the Owner, 2026-11-27)

By the time of the Owner's review, the art Project already had its own `style/prompts/room.j2`: a short template for GPT Image
exteriors (the laneway), with the scale given as "a seventh of the image height" and `style/bible.md` a placeholder. The draft
above and that template were merged, and the Owner accepted the merge. It is now `style/prompts/room.j2` and `style/bible.md` in
the art Project.

- **Scale in px from the room's scale**, as in the draft: adult 52, door 32 x 64 game px, times `canvas_width / width`. "A
  seventh of the image height" is right only for an image one screen tall at the room's scale (the laneway's 937 px extension
  calls), and the brief's canvas is the whole room: it asked for 228 px on the laneway (an 87 px adult in the game) and 112 px on
  the bedroom (27 px). The merge asks for 136 and 215.
- **From the art template:** the exterior words ("ground", "The place:"), the light rule (sun high, upper left, slightly in front).
- **From the draft:** the door, the Exits, the grid line, and the bible (lights with a cause; no people, animals or graffiti;
  signage only; blank surfaces). The draft's back-wall line is kept for rooms narrower than the screen.
- **Changed from the draft:** "a cutaway box in the middle of the frame, surrounded by black, 52% of the width" is gone. It
  contradicted `fit`, which scales the whole Source to the Plate (the bedroom's Source is 1392 x 768 for a 336 x 192 Plate). A
  room narrower than the screen is now a cutaway that fills the image edge to edge.
- Every room's `brief` in the art Project goes stale with it, and so does what follows it, as expected.
- Left open, not blocking: a furniture-size field on the brief. `notes` carries sizes for now.
