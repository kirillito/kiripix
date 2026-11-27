# 0399 trial: generated sound effects (findings, DRAFT)

Written 2026-11-27. The Owner has not heard any output. Nothing was generated. Every price and licence was read from the
vendor's page on 2026-11-27 with `curl -sL`; anything unread is marked "not verified, Owner to check".

**Decision (the Owner, 2026-11-27): local models are declined.** Cloud Providers only, when a sound has to be generated.
The free weights are non-commercial, and Stable Audio Open is free only under $1M revenue (registration, possibly a credit
line), so a local route would mean running a GPU and still paying later. Stable Audio Open stays in the desk table below
for the record only.

**Files:** `prompts.json` (the five prompts), `generate.py` (the Owner's generation script, standard library only),
`slice-and-sheet.sh` (the 0395 and 0396 Commands over a folder of outputs), `.gitignore` (leaves out `out/` and
`scratch-project/`).

## Steps for the Owner

```
cd backlog/m6/0399-trial
python generate.py --provider elevenlabs --provider stability --takes 3 --dry-run   # estimate only, needs no key
python generate.py --provider elevenlabs --provider stability --takes 3             # about $1.27, 30 calls, type "yes"
bash slice-and-sheet.sh out/elevenlabs
bash slice-and-sheet.sh out/stability
```

- Keys go in `ELEVENLABS_API_KEY` and `STABILITY_API_KEY`. ElevenLabs needs a paid plan for commercial use.
- `slice-and-sheet.sh` runs `kiripix new sound <n> --use sfx`, `import`, `pick`, `run`, `sound-takes` and `sound-sheet`
  per file. Sheets land in `out/<provider>/sheets/`. `keep` waits for input until the Owner picks a Take:
  `kiripix decide sound.<n> keep --takes 1`.
- A generated sound is one event, so `slice` should find one Take. If it finds more, use
  `kiripix set sound.<n> slice threshold=<higher>` or pick the Take from the sheet.
- On Windows `generate.py` can't refuse a piped run (`NUL` counts as a terminal). A missing key still refuses.

**Verified:**
- `generate.py --dry-run` prints the plan and the estimate. It refuses when the key is missing and when `--max-usd` is
  exceeded.
- In a scratch Project: `init`, `new sound`, `import`, `pick`, `run`, `sound-takes` and `sound-sheet` on
  `0398-trial/puddle-footsteps.wav`. It found 11 Takes and wrote a 1500 px sheet.
- `decide ... keep --takes 10,4` followed by `run` built `process` and `export`.
- `slice-and-sheet.sh` ran end to end on a temporary folder holding that WAV.

**Not verified, Owner to check:**
- MP3 input through the wheel's ffmpeg. 0395's Result says it decodes MP3.
- `generate.py` against the real APIs.
- Stability's accepted `output_format` values and minimum duration. The script defaults to mp3; change it with
  `--stability-format`.

## Desk table

| | ElevenLabs Sound Effects | Stability Stable Audio 2.5 / 3.0 (hosted API) | Stable Audio Open 1.0 / small (open weights; declined) |
|---|---|---|---|
| Price | "Sound Effects ... are each $0.12 per minute" (https://elevenlabs.io/pricing/api). App: "200 per generation or 40 per second with manual duration" (https://elevenlabs.io/pricing). SFX v3's own price: not verified. | "Flat rate of 8 credits per successful result"; 1 credit is $0.01, so $0.08 (https://docs.stability.ai/llms-full.txt, https://platform.stability.ai/pricing). Stable Audio 2.0 is 20 credits. `platform.stability.ai/llms.txt` says 26 and 20 credits: conflict, Owner to check (8 used). | None; own GPU. |
| Free tier | Free: 10k credits a month, about 250 s of SFX. API access on Free: not verified, Owner to check. | "25 free credits", which is 3 generations. Whether they're non-commercial: not verified. | n/a |
| Commercial shipping | "if you access or use our Services free of charge ... you may only use the Services for non-commercial purposes; ... through a paid subscription plan ... you may use the Services for commercial purposes". "you retain all rights in and to your Output." (https://elevenlabs.io/terms-of-use). Starter is $6 a month ($1 first month). Pay-as-you-go without a subscription, and outputs after cancelling: not verified, Owner to check. | "we assign to you all of our right, title, and interest (if any) in the Outputs ... you own the Output" (https://stability.ai/terms-of-service). No plan restriction found. Watermark (the terms ban removing one): not verified. | "limited commercial uses ... free ... less than US $1,000,000" annual revenue; "You own any outputs" (https://stability.ai/community-license-agreement). Model cards point to https://stability.ai/license. Weights gated on Hugging Face. Training data: CC0, CC BY and CC Sampling+ (Freesound, FMA). |
| Credit line | None found. | None found for the hosted API. | If distributing the Model or a Derivative Work: keep the Notice "This Stability AI Model is licensed under the Stability AI Community License, Copyright (c) Stability AI Ltd.", "prominently display 'Powered by Stability AI'", and register. Derivative Works exclude "the output of any Model". Whether shipping outputs alone triggers the line: Owner to check. |
| API | `POST api.elevenlabs.io/v1/sound-generation`: `text`, `duration_seconds` 0.5 to 30, `prompt_influence`, `loop`, `model_id` (`eleven_text_to_sound_v3`). MP3, or WAV 48 kHz. No seed. v2 is removed 2027-03-01. | `POST api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio`: `prompt`, `duration`, `seed`, `steps`, `model=stable-audio-2.5`, `output_format`. 44.1 kHz stereo, up to 3 min. 3.0 is asynchronous. | Up to 47 s (1.0) or 11 s (small). |
| Data use | Content licence "to improve the Services"; opt out in the account's Data use menu; zero retention is Enterprise only. | Content may be used to improve the service, with opt-out. | Local. |

Not checked (pages render with JavaScript or refused): fal.ai and Replicate prices; Sonniss GDC bundles (403).

**Dropped (non-commercial weights, from each model's page):** AudioGen medium (CC-BY-NC 4.0), AudioLDM 2
(CC-BY-NC-SA 4.0), Tango 2 (CC-BY-NC-SA 4.0), MMAudio (CC-BY-NC 4.0), MusicGen (weights CC-BY-NC 4.0).

## Prompts, with the game's needs (`../urban-mystery-club`)

1. `screen_door`: `docs/backlog/m5/0118-m05-laneway-alive.md` lines 23-24 ("a car passing, a streetcar bell far off, a
   dog behind a fence, a screen door"). Not yet in `audio.json`.
2. `dog_far`: the same line of 0118, and `m4/0099-m04-ambient-life.md` ("a neighbour's dog").
3. `bin_lid`: `sfx.bin.lid` in `audio.json`; the boss fight in `m6/0062-m06-props-phases-boss.md` has bins falling.
4. `coin`: named in the ticket. No coin need found in the game's tickets, so it's `sfx.item_get.coin` beside the existing
   `sfx.item_get`. The Owner may want a real need instead.
5. `bin_fall`: `sfx.bin.fall` in `audio.json`. A real need, and the hardest of the five. Spare: the far streetcar bell.

The game's audio skill says CC0 first, "record the tool and plan tier; many free tiers are non-commercial. Ask the founder
first", with an audio budget of $0 (DEC-004). A paid generator needs the Owner to lift that $0 for audio.

## Cost per kept sound

**Cost per keeper = price per generation / keep rate**, plus any plan fee. The keep rate is assumed, not measured: 1 in 3
for a simple one-shot, 1 in 5 for a layered one. For a 2 s sound:

- ElevenLabs: $0.004 per generation, so $0.012 to $0.020 per keeper, plus a paid plan (Starter, $6 a month; 30k credits
  is about 375 generations of 2 s).
- Stability 2.5: $0.08 per generation, so $0.24 to $0.40 per keeper.
- CC0 downloads: $0 plus search time. Kenney: "License: Creative Commons CC0". Freesound: "for the 'zero' license you can
  do pretty much what you want". OpenGameArt's CC0 filter comes from the game's audio skill (no page quote).

40 one-shots at 1 in 4 is 160 generations: about $0.64 with ElevenLabs inside one $6 month, or about $12.80 with
Stability. Only ElevenLabs fits the $10 monthly cap.

## Owner's listening table (to fill)

| Prompt | ElevenLabs kept / 3 | Stability kept / 3 | Notes (did `slice` find the cut, clipping, tails) |
|---|---|---|---|
| screen_door | | | |
| dog_far | | | |
| bin_lid | | | |
| coin | | | |
| bin_fall | | | |

## Draft Provider ticket (only if the listening test passes; not filed)

"M6: an audio Provider for sound effects (ElevenLabs), called only through `gen`."

- `kiripix gen <sound id> "<prompt>" --duration 2 -n 3` stores each generation as a Variant of the Asset's recording.
  Provenance records `author` (Provider and model), `licence` (the plan and the terms' read date) and `url` (the terms
  page).
- Every call is a pending call the Owner approves (0381), with the estimate (`duration x $0.002`) and the budget left
  (0378). Refused past `budget_usd_month`, `max_calls_per_day` and the per-call count.
- The call is pinned (ADR 0002). The key covers the prompt, duration, `prompt_influence`, `loop`, the model ID and the
  Provider. `run` never asks again; `--rerun` lands in needs-review. With no seed, the pin is the file.
- The key comes from `ELEVENLABS_API_KEY` in the environment or `.env`, never from config or logs.
- A plan check refuses with `owner_action` unless `[providers.elevenlabs] plan` names a paid plan, so a Free key can't
  make a shipped sound.
- New settings `[providers.elevenlabs]` (`model`, `plan`, `usd_per_second`) bump `schema_version`, with a migration.
- Tests use a fake Provider with no network.
- Before the build, the Owner confirms with support that API use and outputs after cancelling stay commercial, and lifts
  DEC-004's $0 for audio.
- Acceptance: a fake-Provider CLI test covering pending call, approve, Variant, Provenance, pin and `--rerun`; contract
  samples; spec §10 and the glossary updated.

## Provisional recommendation

1. **Record or download first.** Kenney, Freesound and OpenGameArt filtered to CC0 cost $0, and the game already accepts
   that licence (DEC-004).
2. **If a generator is worth a try: ElevenLabs Sound Effects**, about $0.012 to $0.02 per kept 2 s sound, but commercial
   use only on a paid plan (Starter, $6 a month). The alternative is Stable Audio 2.5 at $0.24 to $0.40 per keeper; the
   user owns the output, and no credit line was found.
3. **Not worth it:** layered sounds such as `bin_fall`. Local models: declined by the Owner (above).
4. **Decide after listening.** If at least 1 in 4 takes is kept for three of the five prompts, file the Provider ticket.
   Otherwise close the trial with "record or download instead".

## Questions for the Owner

- ElevenLabs: do API pay-as-you-go and outputs made on Starter stay commercial after cancelling? Ask support.
- Stability: does Stable Audio output carry a watermark, and is it 8 credits or 26 (`llms.txt`)?
- Game: is the coin a real need? Do you lift DEC-004's $0 for audio?
