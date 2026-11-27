---
status: done
milestone: M6
agent: ml-engineer
type: ticket
parent: 0386-m6-pixellab-provider.md
depends_on: [0386-m6-pixellab-provider.md]
---

# M6: the PixelLab Provider: jobs, operations that aren't image edits, and charges in generations

Spec §8 and §10 ("Spend"). Part of [0386](0386-m6-pixellab-provider.md): read its Decisions first. Core's side (`gen` for a
sprite, the pending call, the ledger) is [0388](0388-m6-gen-paints-a-sprite.md); this ticket is `kiripix/providers/` and the
fake transport, and changes nothing a Command returns except what `generate-image-v2` adds through the existing `gen`.

The API as 0354 used it is in `backlog/m6/0354-trial/pixellab.py` (throw-away; read it for the request bodies, the job
polling and the ZIP, and re-read `https://api.pixellab.ai/v2/openapi.json` and the price list, and date the table).

## What to build

1. **`kiripix/providers/pixellab.py`**, `PixelLabProvider` (`id = "pixellab"`, `key_name = "PIXELLAB_API_KEY"`), registered with
   the built-in Providers. Bearer token; images as `{"type": "base64", "base64": ..., "format": "png"}`.
2. **The plain `call`** is `generate-image-v2` (answers 202, then a job): a prompt, an optional style image, `size` up to
   256 px, and its candidates as the result's images, so `gen prop.x --provider pixellab --prompt ...` works with no core change.
   `fit_size`, `estimate_usd`, `max_count` say what that endpoint takes (a call gives the candidates PixelLab's grid gives; the
   count asked for is the most kept).
3. **Jobs, for every endpoint that answers a `background_job_id`** (or `background_job_ids`): polled at
   `GET /background-jobs/{id}` every 5 s, then every 10 s after a minute, until `completed` or `failed`, through a
   `wait(seconds)` callable that `call` is given (core binds it to `kiripix.core.cancel.sleep`; the Provider never sleeps).
   On cancel, `DELETE` the job and re-raise. A job that fails is a `ProviderError` with `billed_usd` from its `usage` when it
   has one.
4. **Operations, beside `call`:** a Provider may declare operations (`create_character`, `create_state`, `estimate_rig`,
   `estimate_skeleton`, `animate_skeleton`), each with typed inputs that aren't only images (a character ID, a description,
   per-direction images, keypoints, a rig, a frame count, a canvas, a direction, a `state_name`) and a typed result:
   - `create_character` and `create_state`: the character ID and the character's ZIP, fetched from `GET /characters/{id}/zip`
     (free; retried while PixelLab still builds it), as bytes. Unpacking and choosing what to keep is core's (0388).
   - `estimate_rig` and `estimate_skeleton`: the rig or keypoints, as data.
   - `animate_skeleton`: the frames, as PNG bytes in order (with `keep_first_frame`, the first frame is ours: say so in the result).
   Keep the shapes small and Provider-neutral where they can be (a dataclass per operation in `base.py`, or one
   `OperationRequest` with a name and a dict, whichever reads better; say which in the Result). OpenAI declares none.
5. **Charges:** each result carries `usd` (PixelLab's `usd`, or its `generations` priced at the table's dated rate per
   generation) and `generations` (as charged, a float: 0.25 is common) beside the existing token `usage`. A job's `usage`
   wins over the first answer's, as in the trial.
6. **The price table** per endpoint and canvas (the trial's `ESTIMATE_USD`, the state's 84/112/168 px steps, the skeleton's
   frame-count steps), with `prices_date`, and `estimate` per operation.
7. **`terms`** on `Provider` (a line, empty by default), PixelLab's as in 0386. `describe` shows it where it shows the
   Provider's other fields.
8. **The fake transport** for tests, as OpenAI's (`openai-requests/`): every request kept as JSON in the test Project, jobs that
   queue then complete, a job that fails with a charge, one that is cancelled (and its `DELETE` recorded), a ZIP with three
   states, answers in `usd` and in `generations`. `tests/conftest.py` drops `PIXELLAB_API_KEY` from the environment.

## Acceptance criteria

- [x] CLI seam (written, not run): `gen prop.x --provider pixellab` with the fake transport stores the candidates as Variants and a ledger line with
      the charged `usd`; a 402 and a failed job are `provider.call_failed`, with the charge recorded when there is one.
- [x] (written, not run) A cancelled `gen` during a queued job sends `DELETE` and leaves no Variant (cancel through the Command's token, as the
      OpenAI tests do).
- [x] The fake transport answers every operation above, ready for 0388's tests. The operations are reached only through `gen`,
      so their CLI tests are 0388's; nothing here imports the Provider to test it.
- [x] `uv run mypy`, `uv run lint-imports` (`providers` imports no core). The full suite: the main session runs it (the owner's
      instruction for this batch: no pytest from the ticket's agent).

Budget: 150–250k tokens.

## Result

Built `kiripix/providers/pixellab.py` (`PixelLab`, `id = "pixellab"`, `key_name = "PIXELLAB_API_KEY"`, registered after OpenAI).

- **Plain `call`** is `generate-image-v2`: `description`, `image_size`, `no_background`; the first input image, if any, is the
  `style_image` (with `style_options` all on); the candidates are the result's images, cut to the count asked for. `fit_size`
  scales down to 256 px (min 16), `estimate_usd` is one flat price whatever the count, `max_count` 64, `max_images_in` 1.
- **`wait`**: `Provider.call` takes an optional `wait: Wait | None` (`Callable[[float], None]`), as does `operate`. `OpenAI`
  ignores it. The one core change: `kiripix/core/gen.py` passes `cancel.sleep` (`provider.call(request, key, cancel.check,
  cancel.sleep)`); the test FakeProvider's `call` takes it too. Polling: 5 s, then 10 s after 60 s (the time is the sum of
  the waits, so a fake `wait` is deterministic), `JOB_TIMEOUT_S` 15 min; module constants `POLL_S`, `POLL_LATE_S` that the test
  harness sets to 0.05. On a cancel (or any exit) every unfinished job is `DELETE`d and the exception goes on. A failed job is
  a `ProviderError` with `billed_usd` from its `usage`.
- **Operations**: one `OperationRequest(name, params: dict, images: dict[str, bytes])` and one `OperationResult(name, usd,
  generations, character_id, archive, images, data, job_ids)` in `base.py`, rather than a class per operation (core's plan
  and the pending call's JSON stay one shape). `Provider.operations` names them, `estimate_operation(request)` prices one,
  `operate(request, key, check_cancel, wait)` sends one; the defaults raise `ProviderError`. The params and image roles of
  each of `create_character`, `create_state`, `estimate_rig`, `estimate_skeleton`, `animate_skeleton` are in
  `pixellab.py`'s docstring (0388 reads it): a character from our frames is `images["reference"]` plus one image per
  direction named `south`, `east`...; `estimate_rig` takes `frame_0`, `frame_1`...; `animate_skeleton` takes `first_frame`
  and gives `images` (PNG frames in order) with `data["first_frame_is_ours"]` true when `keep_first_frame` was sent.
  `create_*` give `character_id` and `archive` (the ZIP bytes, fetched from `GET /characters/{id}/zip`, retried 12 times
  at 423 or 202, the waits through `wait`; a charge with no ZIP is a `ProviderError` with `billed_usd`). `estimate_rig` gives
  `data = {rig, frames, raw}`, `estimate_skeleton` `data = {keypoints, raw}`.
- **Charges**: `ProviderResult` gains `generations: float | None`; `OperationResult` has both. `usd` is `usage.usd`, or the
  generations at `USD_PER_GENERATION` = 0.0173; the jobs' `usage` is summed and wins over the first answer's. Core does not
  yet write `generations` to the ledger (0388).
- **Price table** (`prices_date = "2026-11-25"`, per endpoint and canvas): image $0.082; character from frames $0.005 (cap-safe;
  0.25 generations); character from text 0.0173 x (1 + ceil(canvas^2 x directions / 65536)); state $0.075 to 84 px, $0.115 to
  112, $0.15 to 168, $0.20 beyond (a guess); rig $0.006; skeleton $0.005; animate $0.016 to 8 frames, $0.024 to 15 (a guess).
- **`terms`** is a `Provider` attribute (empty by default), PixelLab's as in 0386. Nothing lists a Provider's fields today
  (`describe` shows Kinds and Commands, `cost` only the spend), so there was no place to show it: 0388 shows it with the
  estimate or in `cost`.
- **Fake transport** (`tests/fixtures/kiripix_test_recipes.py`, `pixellab-requests/NNN.json`: method, path, bearer, body;
  polls and DELETEs included). Markers in the body: `FAIL`, `FAIL-BILLED` (a $0.01 charge), `402` (POST refused),
  `GENERATIONS` (charged 1.0 generation), `HOLD` (stays queued while `pixellab-hold` exists, writes `pixellab-holding`). Jobs queue
  one poll, process one, then end. A character from our frames is charged 0.25 generations, the rest in USD. Every POST to a
  character endpoint answers a `character_id` (`char-NNN`); its ZIP answers 423 once, then holds three states (`idle`, `hop`,
  `swipe`) as `<state>/rotations/<direction>.png` (4 or 8 directions, the canvas square) plus `metadata.json`. Skeleton
  frames come in the first frame's size; with `keep_first_frame` frame 0 is the one sent.
- `tests/conftest.py` drops `PIXELLAB_API_KEY`. Tests: `tests/cli/test_pixellab.py` (candidates and ledger, style image, 402,
  failed job free and billed, generations priced, missing key, cancel with `DELETE`). Written, **not run** (the owner's
  instruction for this batch).

Not re-checked: no network, so the figures are the trial's and 0354's notes, dated 2026-11-25 (the OpenAPI and the price list
were not re-read today's session). Also unseen in a real answer: where `generate-image-v2` and `animate-with-skeleton-v3` put
their base64 images (the code takes every base64 image in `last_response`, in order, as the trial's `save_images` did),
the `keep_first_frame` field's name and effect, and `estimate-skeleton`'s keypoints field. A first real call in 0388 or 0389
settles them. No `[providers.pixellab]` settings table was added (`model`, `quality`, `size` mean nothing to PixelLab's
calls); `gen` reads a missing one as the defaults. `describe`/`schema` text of `gen --provider` still says "openai" (0388).
