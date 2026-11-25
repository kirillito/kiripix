# Trial 0354: the run book

The trial makes the game's real poses: the list in the game's ticket **0106** (`urban-mystery-club/docs/backlog/m5/
0106-m05-creature-and-worker-poses.md`). Each pose is made first by the route 0106 proposed (a PixelLab *state* of the
existing character, all 8 directions in one call); the other routes ticket [0354](../0354-m6-provider-research-actors.md)
tests run on the same poses, so every result is a candidate for the game, not a throwaway. Animations come as extras: they
are what 0354 asks about, and the game can use them later.

Commands are PowerShell, from the Kiripix repository root unless they `cd` to the art Project. Nothing here changes
`kiripix/`.

| File | What it does |
|---|---|
| [pixellab.py](pixellab.py) | PixelLab's API: a subcommand per endpoint, every call kept in `runs/` (request, response, job, PNGs) and in `runs/ledger.jsonl`; a spend cap; `--dry-run`; `pack` makes a ZIP Kiripix imports. |
| [keypoints.py](keypoints.py) | PixelLab's 18-joint skeletons from mc03's render, per clip and direction; `--retarget` moves another sprite (the worker) with mc03's motion; an overlay PNG to check them. |
| [pose_inputs.py](pose_inputs.py) | GPT Image pose transfer's inputs (an enlarged pose frame, a 3x3 direction grid) and its results cut back. |

**Money.** $15 in all. `pixellab.py` refuses a call that would take its ledger past `PIXELLAB_TRIAL_CAP_USD` (default
**$10**, leaving $5 for GPT Image). Estimates are PixelLab's figures where it gives them, guesses where it doesn't (states,
images); the ledger records the real charge from each response's `usage`. `pixellab.py spent` totals PixelLab;
`kiripix cost` in the art Project totals GPT Image. The plan comes to about **$4 on PixelLab and $0.50 on GPT Image**.

**Records.** Every PixelLab call: `backlog/m6/0354-trial/runs/<NNN>-…/`. Commit `runs/` with the results. Put your notes, picks
and minutes in `notes.md` here (a template is at the end).

## 0. Set up (5 min)

1. `git pull`, then `uv sync`.
2. **PixelLab** ([pixellab.ai](https://www.pixellab.ai)): sign in with the account that made the raccoon and the worker. Buy
   **$5 of credits** (prepaid, not a subscription: the tier check comes first). Make an **API token** on your account's
   API page.
3. The token goes in the environment, never in a file:
   ```powershell
   $env:PIXELLAB_API_KEY = "<token>"          # this window only; or setx PIXELLAB_API_KEY "<token>" and a new window
   $T = "backlog\m6\0354-trial\pixellab.py"
   uv run python $T balance                   # free: HTTP 200 and your $5
   uv run python $T get /characters           # free: is the website's raccoon and worker there?
   ```
4. The existing sprites' frames, from their ZIPs in the art Project:
   ```powershell
   $A = "..\urban-mystery-club-art\assets\sprite"
   Expand-Archive "$A\raccoon\src\sheets\c496b6e60d0e5719.zip" backlog\m6\0354-trial\inputs\raccoon
   Expand-Archive (Get-ChildItem "$A\animal_control_worker\src\sheets\*.zip")[0].FullName backlog\m6\0354-trial\inputs\worker
   $R = "backlog\m6\0354-trial\inputs\raccoon\Idle\rotations"
   $W = "backlog\m6\0354-trial\inputs\worker\Idle\rotations"
   ```
5. **The two characters' IDs.** If `get /characters` listed the raccoon and the worker, use their IDs: their states then join
   the same group as the idles, as 0106 planned. If it didn't, import them from their frames (0.25 generations each; the
   frames are used as drawn, nothing regenerated):
   ```powershell
   function Import-Rotations($dir, $desc, $template, $label) {
     uv run python $T character --description $desc --south "$dir\south.png" --template $template --label $label `
       --dir south-west="$dir\south-west.png" --dir west="$dir\west.png" --dir north-west="$dir\north-west.png" `
       --dir north="$dir\north.png" --dir north-east="$dir\north-east.png" --dir east="$dir\east.png" --dir south-east="$dir\south-east.png"
   }
   Import-Rotations $R "North American raccoon, all four paws on the ground, grey, black and white fur" cat raccoon
   Import-Rotations $W "Animal control service worker, cap, overalls, carrying a metal trap" mannequin worker
   ```
   Each prints a run folder; `response.json` there has the `character_id`. Write both IDs in `notes.md`; below they are
   `$RAC` and `$WRK` (`$RAC = "<id>"`).

## 1. Your account of PixelLab's failure (10 min, no money)

In `notes.md`, in your words: what was wrong with PixelLab's sprites last time (identity drift across directions or frames,
the angle, the size, the palette, the animation). Every result below is checked for those.

## 2. The tier check (about $0.15): stop here if it fails

```powershell
uv run python $T text-anim --frame $R\south.png --action "walking on all fours" --frames 4 --label tier
uv run python $T animate --character $RAC --action "walking on all fours" --directions s --frames 4 --label tier
```
(The ticket asked for 32 px; the raccoon is 48x52 on its 64 canvas and doesn't fit 32 without resampling, so it runs at 64.)
- **Both 200:** credits are enough. Note it, buy up to $10 more if you want headroom, go on.
- **402 or 403 with credits left:** animation needs a subscription. The poses (step 3) don't use the animation endpoints,
  so do step 3 anyway, and decide on a month's Tier 1 for the rest.

## 3. 0106's poses, by PixelLab states (about $1.50: the main deliverable)

One call per pose, 8 directions each, snapped to the source's palette. Look at each run's PNGs before the next; if a pose
is wrong, change the words and run it again (a new run folder; the old one stays as the record).

**Raccoon** (0106's state prompts):
```powershell
uv run python $T state --character $RAC --name hop    --edit "mid-hop, all four paws off the ground, body stretched forward, tail out behind"
uv run python $T state --character $RAC --name swipe  --edit "rearing on its hind legs, one front paw raised high with claws out, mouth open"
uv run python $T state --character $RAC --name hurt   --edit "flinching back, ears flat, eyes squeezed shut, body crouched low"
uv run python $T state --character $RAC --name dazed  --edit "lying flat on its back, all four paws in the air, tongue out, eyes as spirals"
```
**Black squirrel:** a new character from text at 32 px (PixelLab draws the south view, then rotates it), then its states:
```powershell
uv run python $T character --size 32 --template cat --label squirrel --description "Eastern grey squirrel, black morph, all black fur, sitting up on hind legs, big bushy tail curled up behind it. high top-down 3/4 view."
$SQ = "<its character_id, from that run's response.json>"     # look at its 8 rotations first; redo if it's wrong
uv run python $T state --character $SQ --name leap --edit "leaping, body stretched long, tail streaming behind"
uv run python $T state --character $SQ --name bite --edit "lunging forward, mouth open, front paws out"
```
**Worker:**
```powershell
uv run python $T state --character $WRK --name sack_open --edit "holding a large open burlap sack with both hands at waist height, mouth of the sack open and facing forward, no trap"
uv run python $T state --character $WRK --name bag --edit "swinging a large burlap sack down over the ground in front, both arms forward, knees bent, no trap"
```
**The sack with a raccoon** (a prop, `s` only): one call gives a grid of candidates (64 at 32 px); pick one.
```powershell
uv run python $T image --size 32 --style $R\south.png --label sack --description "a closed burlap sack tied at the top, bulging, with a raccoon's striped tail sticking out, high top-down view"
```
**Get the ZIPs** (free): `uv run python $T get /characters/<state id>/zip` for each state. A state's `character_id` is
in its run's `response.json`. A state is its own character in the group, so each ZIP holds one pose. The squirrel's
idle is its own character's ZIP.

## 4. Into the game through Kiripix (0106's process)

In the art Project. Each ZIP goes into its asset as one more sheet; its folder name becomes the clip's name. Rename a clip
with the sheet Decision's `clips` (`kiripix describe sprite`).
```powershell
cd ..\urban-mystery-club-art
uv run --project ..\kiripix kiripix import sprite.raccoon <dazed zip>     # and hop, swipe, hurt
uv run --project ..\kiripix kiripix run sprite.raccoon
uv run --project ..\kiripix kiripix check sprite.raccoon --json
uv run --project ..\kiripix kiripix new sprite black_squirrel             # then set as 0106 says: directions 8,
uv run --project ..\kiripix kiripix new sprite sack_raccoon               #   fit height 18 / 24, the raccoon's finish
```
The new assets start from the raccoon's `asset.toml` settings (0106): `frames directions=8` (the sack: `1`), `fit
mode=downscale height=18` for the squirrel and `24` for the sack, `palette colors=16`, `finish outline_colour=195`. Loose
frames (the sack's pick, `text-anim` and `skeleton` runs) pack first:
`uv run python $T pack <out.zip> <clip>:<direction>=<run folder> ...` (for one picked image, copy it alone into a folder).
Then `kiripix export` as usual. Never hand-edit the exports. For 0354, note each sheet's findings (`frames.*`, `fit.*`,
`sheet.pivot_drift`, `palette.off_palette`), and whether `fit` took PixelLab's frames without resampling.

## 5. Extras: animations, the routes 0354 compares (about $2)

Only if step 2 passed. Each gives frames the game can use later, and answers 0354's text-led against skeleton question.

**Text-led (PixelLab writes the motion):**
```powershell
uv run python $T animate --character $RAC --action "walking on all fours" --frames 8 --color-image $R\south.png --force-colors --label raccoon-walk
uv run python $T animate --character $SQ  --action "running" --frames 8 --label squirrel-run
uv run python $T animate --character $WRK --action "walking" --frames 4 --label worker-walk
uv run python $T get /characters/$RAC/zip                 # the animations come in the character's ZIP
```
**Skeleton (mc03's motion moves the worker).** First mc03's joints, which Kiripix's `render` already records when its
`points` parameter is set, so no Blender script is needed. mc03_male's render is run once with them, copied here, and set
back; a parameter at its default is out of the hash, so mc03_male ends as it was. **Don't `export` mc03_male in between.**
```powershell
cd ..\urban-mystery-club-art
uv run --project ..\kiripix kiripix status
$P = uv run --project ..\kiripix python ..\kiripix\backlog\m6\0354-trial\keypoints.py x --clip x --out x --print-points
uv run --project ..\kiripix kiripix set character.mc03_male render "points=$P"
uv run --project ..\kiripix kiripix run character.mc03_male render
$WR = "assets\character\mc03_male\work\render"; $M = "..\kiripix\backlog\m6\0354-trial\mannequin"
New-Item -ItemType Directory -Force $M | Out-Null; Copy-Item $WR\render.json $M; Copy-Item -Recurse $WR\color $M
uv run --project ..\kiripix kiripix set character.mc03_male render "points="
uv run --project ..\kiripix kiripix run character.mc03_male render
uv run --project ..\kiripix kiripix status                 # mc03_male as before
cd ..\kiripix; $M = "backlog\m6\0354-trial\mannequin"
```
(If `render` stops with `points_unknown`, it lists the rig's bones: set the points back and send me the list.)

Then the worker's own skeleton per direction ($0.005 each), and mc03's walk and its downward attack, which is close to
0106's bag swing, moved onto it:
```powershell
foreach ($d in "s","e","n","w") { uv run python $T estimate --image "$W\$((@{s='south';e='east';n='north';w='west'})[$d]).png" --label "worker-$d" }
uv run python backlog/m6/0354-trial/keypoints.py $M\render.json --clip walk   --first-clip idle --frames 4 --directions s,e,n,w --retarget "backlog/m6/0354-trial/runs/*-estimate_worker_{d}" --out backlog\m6\0354-trial\keypoints\worker
uv run python backlog/m6/0354-trial/keypoints.py $M\render.json --clip attack --first-clip idle --frames 6 --directions s,e,n,w --retarget "backlog/m6/0354-trial/runs/*-estimate_worker_{d}" --out backlog\m6\0354-trial\keypoints\worker
```
**Look at** `keypoints\worker\walk_s_overlay.png`: the first panel is PixelLab's estimate on the worker; its RIGHT side
(red) should be on the image's left in the south view. If the skeletons look right:
```powershell
foreach ($d in "s","e","n","w") {
  $f = "$W\$((@{s='south';e='east';n='north';w='west'})[$d]).png"
  uv run python $T skeleton --frame $f --keypoints backlog\m6\0354-trial\keypoints\worker\walk_$d.json --direction $d --description "animal control service worker, cap, overalls" --action walk --label "worker-skel-walk-$d"
  uv run python $T skeleton --frame $f --keypoints backlog\m6\0354-trial\keypoints\worker\attack_$d.json --direction $d --description "animal control service worker, cap, overalls, swinging a burlap sack" --action "swing down" --label "worker-skel-bag-$d"
}
```
The bag frames are candidates for 0106's `bag` beside step 3's state: pick whichever reads better at 1×.

**A pigeon and an ambient loop** (0354's list, not 0106's; cheap):
```powershell
uv run python $T character --size 32 --template cat --label pigeon --description "city pigeon, grey with an iridescent neck, high top-down view"
uv run python $T animate --character <pigeon_id> --action "pecking at the ground and hopping" --frames 8 --directions s,e,n,w --label pigeon-idle
uv run python $T text-anim --frame <one loop frame.png> --last <the same frame> --action "a flag flapping in the wind" --frames 8 --label loop
```

## 6. GPT Image pose transfer: the 30° camera test (about $0.50)

PixelLab's poses keep PixelLab's angle (about 35°, not mc03's 30°). This is the one route that takes the angle from mc03.
Two calls, through Kiripix (its ledger and `approve`):
```powershell
uv run python backlog/m6/0354-trial/pose_inputs.py pose $M\color\attack\s\006.png backlog\m6\0354-trial\pose\pose_bag_s.png
uv run python backlog/m6/0354-trial/pose_inputs.py grid $R - 0 backlog\m6\0354-trial\pose\grid_raccoon.png
cd ..\urban-mystery-club-art
uv run --project ..\kiripix kiripix new prop trial0354_pose
uv run --project ..\kiripix kiripix gen prop.trial0354_pose --reference ..\kiripix\backlog\m6\0354-trial\pose\pose_bag_s.png --reference ..\kiripix\backlog\m6\0354-trial\inputs\worker\Idle\rotations\south.png --prompt "<prompt 1>"
uv run --project ..\kiripix kiripix gen prop.trial0354_pose --reference ..\kiripix\backlog\m6\0354-trial\pose\grid_raccoon.png --reference <the squirrel's south from step 3> --prompt "<prompt 2>"
```
(Pick a frame of the attack clip where the arms are down; `006` is a guess.)
1. "Image 1 is a pose reference: a plain mannequin seen from above at a 30-degree angle on a flat green background. Image 2
   is the character. Redraw the character from image 2 in exactly the pose, angle, size and position of the mannequin in
   image 1, swinging a large burlap sack down in both hands instead of the metal trap, as pixel art with clean edges on the
   same flat green background. Transfer the pose WITHOUT MIRRORING: the mannequin's right arm is the character's right arm.
   Keep every asymmetric detail on the same side of the body. Non-sexual, fully clothed work uniform."
2. "Image 1 is a 3x3 sheet: a raccoon in 8 directions around an empty centre cell, seen from above, on flat green. Image 2
   is a black squirrel. Redraw image 1 with the squirrel in every cell, in exactly that cell's direction, size and place, in
   the raccoon's pixel-art style; leave the centre empty green. Rotate between cells; do not horizontally flip any cell.
   Keep every asymmetric feature on the same side in every view. Flat green background. Non-sexual."

`pose_inputs.py split <sheet> <dir>` cuts prompt 2's sheet into 8 directions. Count any calls the moderation refused.

## 7. Hand back

Commit `backlog/m6/0354-trial/` (with `runs/`, `keypoints/`, `pose/`, `notes.md`) and the art Project's assets and exports
as usual, and tell me. I'll write 0354's Result (scores, cost per pose, the recommendation per actor) and 0106's progress,
and file the follow-ups. Remove `prop.trial0354_pose` from the art Project at the end.

### notes.md template

```markdown
# 0354 / 0106 notes
PixelLab's failure last time (my words):
Character IDs: raccoon , worker , squirrel , pigeon
Tier check: credits enough? yes / no (HTTP …)

| Pose | Route | Run folder(s) | Tries | Minutes (generate + pick + Kiripix) | Usable? What's wrong |
|---|---|---|---|---|---|
| raccoon hop | state | | | | |
| raccoon swipe | state | | | | |
| raccoon hurt | state | | | | |
| raccoon dazed | state | | | | reads at 1×? |
| squirrel idle | character | | | | |
| squirrel leap | state | | | | |
| squirrel bite | state | | | | |
| worker sack_open | state | | | | |
| worker bag | state / skeleton / GPT | | | | reads at 1×? |
| worker walk | text / skeleton | | | | |
| sack with raccoon | image | | | | |
| raccoon walk (extra) | text | | | | |
| pigeon idle, loop (extra) | text | | | | |
```
