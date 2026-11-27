---
status: todo
milestone: M6
type: spec
---

# M6: sound as an Asset Kind (slice, see, process, export, generate)

Asked by the Owner on 2026-11-26, from the game's laneway work (its tickets 0118 and 0245). Today every sound effect is
cut by an agent that can't listen: it guesses cut points from ffmpeg numbers, and most of an audio ticket's tokens go
there. The game's `audio` skill (`../urban-mystery-club/.claude/skills/audio/SKILL.md`) and its
`tools/audio_normalize` already set the formats and loudness targets (OGG Vorbis 44.1 kHz q5; SFX and UI mono at
peak −3 dBFS; ambience −40 LUFS, −2 dBTP, stereo; music −18 LUFS, −1 dBTP); Kiripix adopts them as Project settings
rather than inventing its own.

Why Kiripix and not a separate tool: the Manifest, provenance, the review queue and Owner approval of provider calls
(0381) already exist here, and they are the expensive parts. Credits stay the game's: Kiripix records provenance in the
Manifest, the game writes its `CREDITS.md` from it (Owner, 2026-11-26). The audio processing itself is ffmpeg
plus onset detection.

## Tickets

| # | Ticket | Agent |
|---|---|---|
| 0394 | [ADR: a `sound` Kind and its Recipe](0394-m6-adr-sound-kind.md) | reviewer |
| 0395 | [Import a recording and slice it into Takes](0395-m6-sound-import-and-slice.md) | core-engineer |
| 0396 | [A contact sheet of a sound's Takes](0396-m6-sound-contact-sheet.md) | imaging-engineer |
| 0397 | [Process: trim, speed, loop, loudness](0397-m6-sound-process-and-export.md) | core-engineer |
| 0400 | [Export to Godot, provenance in the Manifest](0400-m6-sound-export.md) | godot-export |
| 0398 | [UI: listen to the Takes and pick](0398-m6-ui-sound-screen.md) | ui-engineer |
| 0399 | [Trial: generated sound effects](0399-m6-sound-gen-trial.md) | ml-engineer |

**Order:** 0394 → 0395 → 0396 and 0397 → 0400 → 0398; 0399 any time after 0394 (it needs the Owner's approval rule, 0381).

## Done when

An agent turns the Owner's recording of footsteps on asphalt (one file, several steps) into four normalised OGG
variations in the game, their provenance in the Manifest for the game's credit line, without guessing a cut point, and can show the Owner a picture of the
cuts it chose.
