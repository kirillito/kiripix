---
status: in-progress
milestone: M6
agent: ml-engineer
type: ticket
parent: 0393-m6-sound-kind.md
---

# M6: trial: generated sound effects

## The question

Can a provider make simple one-shots (a screen door, a dog bark far off, a bin lid, a coin) good enough to keep, at
what cost, under what licence? A trial, like 0353's provider research: findings in `0399-trial/`, no Provider built.

## To do

- Shortlist providers with an API and terms that let the game ship the output commercially (check each on its own
  terms page, dated); note what the credit line must say.
- Five prompts from the game's needs; each provider's outputs sliced and sheeted with 0395 and 0396 if they exist by
  then; cost per kept sound.
- If one is worth it: a Provider ticket under 0381's rule (every call approved by the Owner, the monthly cap).

## Result (DRAFT, 2026-11-27: the Owner has not heard the outputs)

Nothing was generated: no paid call, no key, no account, no local model (this machine has no GPU). The trial's tools are in
[0399-trial/](0399-trial/): `prompts.json` (five prompts: screen door, far dog, bin lid, coin, and the bin falling), `generate.py` (the
Owner runs it; prints the estimate, asks `yes`, keys from `ELEVENLABS_API_KEY` and `STABILITY_API_KEY` only),
`slice-and-sheet.sh` (0395 and 0396 over the outputs, checked on `0398-trial/puddle-footsteps.wav`) and `gpu_stable_audio_open.py`
(to run on the GPU machine, not run). Prices and terms were read from the vendors' pages on 2026-11-27; what could not be read is
marked "not verified, Owner to check". The full findings text is handed to the main session to save as `0399-trial/findings.md`
(the agent's write of it was refused).

**Provisional recommendation (before listening):**

- **Record or download first:** Kenney, Freesound and OpenGameArt filtered to CC0 cost $0 under a licence the game already
  accepts (DEC-004 sets audio at $0).
- **If a generator is tried: ElevenLabs Sound Effects**, $0.12 a minute ($0.004 for a 2 s sound), about $0.012 to $0.02 per kept
  sound at an assumed 1-in-3 to 1-in-5 keep rate, but its terms allow commercial use only on a paid plan (Starter, $6 a month); the
  Owner confirms that API use and outputs after cancelling stay commercial. **Stability Stable Audio 2.5** is the alternative:
  $0.08 flat per generation ($0.24 to $0.40 per keeper), output owned by the user in its terms, no credit line found.
- **Not worth it:** layered sounds (the bin falling) and open weights with non-commercial licences (AudioGen, AudioLDM 2, Tango 2,
  MMAudio, MusicGen). Stable Audio Open (Community Licence, under $1M revenue, "Powered by" rules to read) waits for the GPU machine.
- **Decision after the Owner listens:** if at least 1 in 4 takes is kept for three of the five prompts, file a Provider ticket
  (draft text in the findings, section 9); otherwise "record or download instead" and close the trial.
