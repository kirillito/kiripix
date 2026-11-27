"""The PixelLab Provider: pixel-art sprites, their states and motion, through the PixelLab API v2 (tickets 0386, 0387; the
Owner approved it on 2026-11-25 after the trial of ticket 0354, `backlog/m6/0354-trial/pixellab.py`).

The API, as the trial used it (`https://api.pixellab.ai/v2`; request bodies from its `/openapi.json`, read 2026-11-25):
- Bearer token. Images go as `{"type": "base64", "base64": <data>, "format": "png"}`; none is over 256 x 256 px.
- Long calls answer `{"background_job_id": ...}` (or `background_job_ids`), 202 or 200; `GET /background-jobs/{id}` gives
  `{"status": queued | processing | completed | failed, "usage", "last_response"}`; `DELETE` there cancels (free while queued).
- A charge is `usage`: `{"type": "usd", "usd": ...}` or `{"type": "generations", "generations": ...}` (0.25 is common). A
  job's `usage` wins over the first answer's.
- Image URLs in answers refuse downloads and the terms let code call `api.pixellab.ai` only, so a character's frames come
  as its ZIP (`GET /characters/{id}/zip`, free; 423 while PixelLab still builds it) and the plain image call's as base64
  in the job's `last_response`.

Not tested against the network (the Owner, 2026-11-23: tests cost $0): the tests run over a fake transport. The shape of
`generate-image-v2`'s and `animate-with-skeleton-v3`'s `last_response` (where the base64 images sit) is taken from the
trial's `save_images`, which finds every base64 image in the answer in order; `keep_first_frame` and the exact name of
`estimate-skeleton`'s keypoints field were not seen in a real answer. A real run of 0388's tests-by-hand would settle them.

Plain call (`call`): `generate-image-v2`, the candidates of PixelLab's grid as the result's images; the first input image,
if any, is the style image (pixel size, palette, outline, shading), at most 256 px.

Operations (`operate`; `OperationRequest(name, params, images)`), each params key is optional unless marked `*`:

`create_character`: a character in 4 or 8 directions, then its ZIP.
    params: `description*` (str), `canvas` (int px, a square, 32 to 256: from text), `n_directions` (4 or 8, default 8),
    `view` (default "high top-down"), `template` (default "mannequin"), `seed`.
    images: `reference` (our south frame) with `east`, `north`... (every other direction's frame, all the reference's canvas,
    never `south`: it is the reference) imports the character as drawn, nothing is made (0.25 generations; $0.0043 measured
    2026-11-27). Core never sends a reference alone: the missing facings come from `generate_rotations` first (ticket 0390).
    Without a reference it is drawn from the description.
    `view` is one of VIEWS.
    result: `character_id`, `archive` (the ZIP).
`generate_rotations`: the 8 rotations of a south frame, which come back clockwise from `first_frame_direction` (here south).
    params: `view`, `description`, `first_frame_direction`. images: `first_frame*`, `south-east`... (directions already drawn).
    result: `images` (8 PNGs, in the order south, south-east, east, north-east, north, north-west, west, south-west).
`create_state`: a pose of an existing character in all its directions, a new character in its group, then its ZIP.
    params: `character_id*`, `description*` (the edit), `state_name*`, `canvas` (int px, a larger square for a pose that
    needs room), `free_colours` (bool: don't snap to the source's palette), `seed`.
    result: `character_id` (the new one), `archive` (holds every state of the group: core keeps only the new one).
`estimate_rig`: a rig for an animal, placed on its frames.
    params: `direction*`, `view`, `description`, `action`. images: `frame_0`, `frame_1`... (same size).
    result data: `rig`, `frames` (a list of keypoint lists), `raw` (the whole answer).
`estimate_skeleton`: the 18 humanoid joints of one sprite. images: `image*`. result data: `keypoints`, `raw`.
`animate_skeleton`: frames from keypoints, or written by PixelLab from the action.
    params: `description*`, `action*`, `direction*`, `first_frame_keypoints*`, `keypoints` (a list per frame) or
    `write_motion_frames` (int, 1 to 15), `rig`, `view`, `template`, `keep_first_frame` (bool), `seed`.
    images: `first_frame*`.
    result: `images` (the frames as PNG bytes, in order); with `keep_first_frame`, the first one is the `first_frame` sent
    (ours) and `data["first_frame_is_ours"]` is true.

`animate_keyframes`: frames between two of the sprite's own (`animate-with-text-v3` with `first_frame` and `last_frame`, ticket
    0391; text alone is never sent: `first_frame` and `last_frame` are both needed). The text only names the action.
    params: `action*` (str, at most 1000 characters), `frame_count` (an even 4 to 16, default 8), `seed`. images: `first_frame*`,
    `last_frame*` (at most 256 px, equal in size; width x height x frame_count at most 524288).
    result: `images` (the frames as PNG bytes, in order, stored as they came). `interpolation-v2` (Pro, 14 frames up to 64 px, 2
    from 65, no frame count, at most 128 px) is not wired: the OpenAPI's text puts it out of reach of a 8-frame clip.

Every result carries `usd` (PixelLab's, or its generations priced at `USD_PER_GENERATION`; None when nothing was
reported) and `generations` (as charged). PixelLab says its prices "vary with GPU time": the charge counts once known.
"""

from __future__ import annotations

import base64
import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from kiripix.providers.base import (
    CheckCancel, InputImage, OperationRequest, OperationResult, Provider, ProviderError, ProviderRequest,
    ProviderResult, Wait,
)

API = "https://api.pixellab.ai/v2"
TIMEOUT_S = 300
THREAD_POLL_S = 0.2
POLL_S = 5.0  # between polls of a job, for its first minute
POLL_LATE_S = 10.0  # then
LATE_AFTER_S = 60.0
JOB_TIMEOUT_S = 15 * 60
ZIP_TRIES = 12  # a character's ZIP answers 423 while it is built

PRICES_DATE = "2026-11-27"
# PixelLab's estimates in USD (its price list and the OpenAPI text, read 2026-11-25; 0354's charges for the figures it
# measured). A generation on prepaid credits is priced at USD_PER_GENERATION, the "1 generation" of a 64 px
# create-character-with-8-directions. PixelLab's charge, not these, counts once known.
USD_PER_GENERATION = 0.0173
IMAGE_USD = 0.082  # generate-image-v2, up to 256 x 256, however many candidates (0354: $0.164 for two calls)
CHARACTER_FROM_FRAMES_USD = 0.0043  # create-character-v3 from all the frames, measured 2026-11-27: $0.004325 (0.25 generations)
ROTATIONS_USD = 0.0203  # generate-8-rotations-v3 at 32 px, measured 2026-11-27: $0.020301
RIG_USD = 0.006  # estimate-custom-skeleton (0354: about $0.005)
SKELETON_USD = 0.005  # estimate-skeleton
STATE_USD = ((84, 0.075), (112, 0.115), (168, 0.15), (256, 0.20))  # by the canvas's longer edge; 0.20 isn't listed, a guess
ANIMATE_USD = ((8, 0.016), (15, 0.024))  # by frame count, per direction; 0.016 measured at 4 and 8 frames, 0.024 a guess
KEYFRAMES_USD = ((4, 0.022), (8, 0.03), (16, 0.045))  # animate-with-text-v3 by frame count; 0.022 at 32 px and 4 frames
# (the ticket 0391 text, 2026-11-25), 0.019 measured at 8 (run 112 of 0354); the rest guesses on the cap-safe side
KEYFRAMES_FRAMES = (4, 16)  # even
KEYFRAMES_PIXELS = 524_288  # width x height x frame_count
MAX_PX = 256
DIRECTIONS = ("south", "south-west", "west", "north-west", "north", "north-east", "east", "south-east")
FOUR = ("south", "west", "north", "east")
ROTATION_ORDER = ("south", "south-east", "east", "north-east", "north", "north-west", "west", "south-west")  # clockwise
VIEWS = ("low top-down", "high top-down", "side")  # PixelLab's `CameraView` (OpenAPI, 2026-11-26)

TERMS = ("output is the Project's for commercial use; no training of models on it; code may call only api.pixellab.ai "
         "(the Owner, 2026-11-25)")

JOB_STATES_END = ("completed", "failed")


class PixelLab(Provider):
    id = "pixellab"
    description = ("PixelLab, through the PixelLab API v2: pixel-art images, sprite characters, their poses and their motion "
                   "(paid, per generation or in USD).")
    key_name = "PIXELLAB_API_KEY"
    default_model = "generate-image-v2"
    max_count = 64
    max_images_in = 1  # the style image, sent as a `--reference`
    edits = False  # generate-image-v2 takes no image to edit and no mask: gen refuses --look, --state, --emotion, --side
    prices_date = PRICES_DATE
    terms = TERMS
    operations = ("create_character", "generate_rotations", "create_state", "estimate_rig", "estimate_skeleton",
                  "animate_skeleton", "animate_keyframes")
    endpoints = {"create_character": "create-character-v3", "generate_rotations": "generate-8-rotations-v3",
                 "create_state": "create-character-state",
                 "estimate_rig": "estimate-custom-skeleton", "estimate_skeleton": "estimate-skeleton",
                 "animate_skeleton": "animate-with-skeleton-v3",
                 "animate_keyframes": "animate-with-text-v3"}

    def estimate_usd(self, model: str, size: tuple[int, int], quality: str, count: int, images_in: int,
                     prompt_chars: int) -> float:
        return IMAGE_USD  # whatever the number of candidates: the grid is one call

    def fit_size(self, model: str, wanted: tuple[int, int]) -> tuple[int, int]:
        width, height = (max(1, int(v)) for v in wanted)
        scale = min(1.0, MAX_PX / max(width, height))
        return max(16, round(width * scale)), max(16, round(height * scale))

    # --- the plain call: generate-image-v2 ------------------------------------------------------------------------

    def call(self, request: ProviderRequest, key: str | None, check_cancel: CheckCancel,
             wait: Wait | None = None) -> ProviderResult:
        key = _need_key(key)
        if wait is None:
            raise ProviderError("the PixelLab Provider needs a `wait` to poll its jobs")
        body: dict[str, Any] = {"description": request.prompt,
                                "image_size": {"width": request.size[0], "height": request.size[1]}, "no_background": True}
        if request.images:
            style = request.images[0]
            width, height = _png_size(style)
            body["style_image"] = {"image": _image(style.png), "size": {"width": width, "height": height}}
            body["style_options"] = {"color_palette": True, "outline": True, "detail": True, "shading": True}
        done = _post("generate-image-v2", body, key, check_cancel, wait)
        images = _images_in(done.payload)[:request.count]
        if not images:
            raise ProviderError("PixelLab answered with no images",
                                billed_usd=done.usd, billed_generations=done.generations)
        return ProviderResult(images=images, usd=done.usd, generations=done.generations)

    # --- operations -----------------------------------------------------------------------------------------------

    def estimate_operation(self, request: OperationRequest) -> float:
        p = request.params
        if request.name == "create_character":
            if "reference" in request.images:
                return CHARACTER_FROM_FRAMES_USD  # every facing is ours: it is only imported
            canvas = int(p.get("canvas") or 32)
            return USD_PER_GENERATION * (1 + -(-canvas * canvas * int(p.get("n_directions") or 8) // 65536))
        if request.name == "generate_rotations":
            return ROTATIONS_USD
        if request.name == "create_state":
            edge = int(p.get("canvas") or 64)
            return next((usd for limit, usd in STATE_USD if edge <= limit), STATE_USD[-1][1])
        if request.name == "estimate_rig":
            return RIG_USD
        if request.name == "estimate_skeleton":
            return SKELETON_USD
        if request.name == "animate_skeleton":
            frames = len(p.get("keypoints") or ()) or int(p.get("write_motion_frames") or 4)
            return next((usd for limit, usd in ANIMATE_USD if frames <= limit), ANIMATE_USD[-1][1])
        if request.name == "animate_keyframes":
            frames = int(p.get("frame_count") or 8)
            return next((usd for limit, usd in KEYFRAMES_USD if frames <= limit), KEYFRAMES_USD[-1][1])
        return super().estimate_operation(request)

    def operate(self, request: OperationRequest, key: str | None, check_cancel: CheckCancel,
                wait: Wait) -> OperationResult:
        key = _need_key(key)
        p, images = request.params, request.images
        if request.name == "create_character":
            return self._create_character(request, key, check_cancel, wait)
        if request.name == "generate_rotations":
            return self._rotations(request, key, check_cancel, wait)
        if request.name == "create_state":
            body: dict[str, Any] = {"character_id": _need(p, "character_id"), "edit_description": _need(p, "description"),
                                    "state_name": _need(p, "state_name"), "no_background": True,
                                    "use_color_palette_from_reference": not p.get("free_colours", False),
                                    "seed": int(p.get("seed") or 0)}
            if p.get("canvas"):
                body["override_frame_size"] = {"width": int(p["canvas"]), "height": int(p["canvas"])}
            done = _post("create-character-state", body, key, check_cancel, wait)
            return _with_zip(request.name, done, done.character_id or str(body["character_id"]), key, check_cancel, wait)
        if request.name == "estimate_rig":
            frames = [_image(images[name]) for name in sorted(images, key=_frame_number) if name.startswith("frame_")]
            if not frames:
                raise ProviderError("estimate_rig needs images frame_0, frame_1...")
            body = {"images": frames, "direction": _direction(_need(p, "direction")), "view": _view(p),
                    "description": p.get("description", ""), "action": p.get("action", "")}
            done = _post("estimate-custom-skeleton", body, key, check_cancel, wait)
            answer = done.payload if isinstance(done.payload, dict) else {}
            frames_out = answer.get("frames") or answer.get("keypoints") or []
            frames_out = [f.get("keypoints", f) if isinstance(f, dict) else f for f in frames_out]
            data = {"rig": answer.get("rig"), "frames": frames_out, "raw": answer}
            return OperationResult(name=request.name, usd=done.usd, generations=done.generations, data=data,
                                   job_ids=done.job_ids)
        if request.name == "estimate_skeleton":
            if "image" not in images:
                raise ProviderError("estimate_skeleton needs the image `image`")
            done = _post("estimate-skeleton", {"image": _image(images["image"])}, key, check_cancel, wait)
            answer = done.payload if isinstance(done.payload, dict) else {}
            return OperationResult(name=request.name, usd=done.usd, generations=done.generations,
                                   data={"keypoints": answer.get("keypoints"), "raw": answer}, job_ids=done.job_ids)
        if request.name == "animate_skeleton":
            return self._animate(request, key, check_cancel, wait)
        if request.name == "animate_keyframes":
            return self._keyframes(request, key, check_cancel, wait)
        raise ProviderError(f"the pixellab Provider has no operation '{request.name}'")

    def _create_character(self, request: OperationRequest, key: str, check_cancel: CheckCancel,
                          wait: Wait) -> OperationResult:
        p, images = request.params, request.images
        body: dict[str, Any] = {"description": _need(p, "description"), "view": _view(p),
                                "template_id": p.get("template", "mannequin"), "no_background": True,
                                "seed": int(p.get("seed") or 0)}
        n_directions = int(p.get("n_directions") or 8)
        if "reference" in images:
            body["reference_image"] = _image(images["reference"])
            body["n_directions"] = n_directions
            others = {name: _image(png) for name, png in images.items() if name not in ("reference", "south")}
            if others:
                body["direction_images"] = {_direction(name): image for name, image in others.items()}
        else:
            canvas = int(p.get("canvas") or 32)
            body["image_size"] = {"width": canvas, "height": canvas}
            if n_directions != 8:
                body["n_directions"] = n_directions
        done = _post("create-character-v3", body, key, check_cancel, wait)
        if not done.character_id:
            raise ProviderError("PixelLab answered with no character ID",
                                billed_usd=done.usd, billed_generations=done.generations)
        return _with_zip(request.name, done, done.character_id, key, check_cancel, wait)

    def _rotations(self, request: OperationRequest, key: str, check_cancel: CheckCancel, wait: Wait) -> OperationResult:
        p, images = request.params, request.images
        if "first_frame" not in images:
            raise ProviderError("generate_rotations needs the image `first_frame`")
        # No `view` for a lone frame: PixelLab rotates it as drawn and refuses `view` without `direction_images` (HTTP 422,
        # 0390's trial); the character call that follows carries the view.
        body: dict[str, Any] = {"first_frame": _image(images["first_frame"]), "no_background": True,
                                "first_frame_direction": _direction(str(p.get("first_frame_direction", "south"))),
                                "seed": int(p.get("seed") or 0)}
        if p.get("description"):
            body["description"] = p["description"]
        drawn = {_direction(name): _image(png) for name, png in images.items() if name != "first_frame"}
        if drawn:
            body["direction_images"] = drawn
            body["view"] = _view(p)
        done = _post("generate-8-rotations-v3", body, key, check_cancel, wait)
        out = _images_in(done.payload)
        if len(out) != len(ROTATION_ORDER):
            raise ProviderError(f"PixelLab answered with {len(out)} rotations, not {len(ROTATION_ORDER)}",
                                billed_usd=done.usd, billed_generations=done.generations)
        return OperationResult(name=request.name, usd=done.usd, generations=done.generations, images=out,
                               data={"directions": list(ROTATION_ORDER)}, job_ids=done.job_ids)

    def _animate(self, request: OperationRequest, key: str, check_cancel: CheckCancel, wait: Wait) -> OperationResult:
        p, images = request.params, request.images
        if "first_frame" not in images:
            raise ProviderError("animate_skeleton needs the image `first_frame`")
        body: dict[str, Any] = {"description": _need(p, "description"), "action": _need(p, "action"),
                                "direction": _direction(_need(p, "direction")), "view": _view(p),
                                "first_frame": _image(images["first_frame"]),
                                "first_frame_keypoints": _need(p, "first_frame_keypoints"),
                                "template_id": p.get("template", "mannequin"), "seed": int(p.get("seed") or 0),
                                "no_background": True}
        if p.get("rig"):
            body["rig"] = p["rig"]
        if p.get("write_motion_frames"):
            body["write_motion_frames"] = int(p["write_motion_frames"])
            frames = int(p["write_motion_frames"])
        else:
            body["keypoints"] = _need(p, "keypoints")
            frames = len(body["keypoints"])
        if not (1 if p.get("rig") else 3) <= frames <= 15:
            raise ProviderError(f"{frames} frames: PixelLab takes 3 to 15 (1 to 15 with a rig)")
        keep = bool(p.get("keep_first_frame", False))
        if keep:
            body["keep_first_frame"] = True
        done = _post("animate-with-skeleton-v3", body, key, check_cancel, wait)
        out = _images_in(done.payload)
        if not out:
            raise ProviderError("PixelLab answered with no frames",
                                billed_usd=done.usd, billed_generations=done.generations)
        return OperationResult(name=request.name, usd=done.usd, generations=done.generations, images=out,
                               data={"first_frame_is_ours": keep}, job_ids=done.job_ids)

    def _keyframes(self, request: OperationRequest, key: str, check_cancel: CheckCancel, wait: Wait) -> OperationResult:
        p, images = request.params, request.images
        for role in ("first_frame", "last_frame"):
            if role not in images:
                raise ProviderError(f"animate_keyframes needs the image `{role}`: motion is never made from text alone")
        frames = int(p.get("frame_count") or 8)
        if frames % 2 or not KEYFRAMES_FRAMES[0] <= frames <= KEYFRAMES_FRAMES[1]:
            raise ProviderError(f"{frames} frames: PixelLab takes an even {KEYFRAMES_FRAMES[0]} to {KEYFRAMES_FRAMES[1]}")
        width, height = _png_size(InputImage("first_frame", images["first_frame"]))
        if width * height * frames > KEYFRAMES_PIXELS:
            raise ProviderError(f"{width}x{height} px at {frames} frames is over PixelLab's budget of {KEYFRAMES_PIXELS} pixels")
        body: dict[str, Any] = {"first_frame": _image(images["first_frame"]), "last_frame": _image(images["last_frame"]),
                                "action": _need(p, "action"), "frame_count": frames, "no_background": True,
                                "seed": int(p.get("seed") or 0)}
        done = _post("animate-with-text-v3", body, key, check_cancel, wait)
        out = _images_in(done.payload)
        if not out:
            raise ProviderError("PixelLab answered with no frames", billed_usd=done.usd, billed_generations=done.generations)
        return OperationResult(name=request.name, usd=done.usd, generations=done.generations, images=out, job_ids=done.job_ids)


# --- jobs and charges ---------------------------------------------------------------------------------------------

class _Done:
    """What a POST came to: the first answer, its jobs' final states, the payload (the last job's `last_response`, else
    the answer itself) and the charge."""

    def __init__(self, answer: dict[str, Any], jobs: list[dict[str, Any]]) -> None:
        self.answer = answer
        self.jobs = jobs
        self.job_ids = [str(job.get("id", "")) for job in jobs if job.get("id")]
        self.payload: Any = jobs[-1].get("last_response") if jobs and jobs[-1].get("last_response") is not None else answer
        self.usd, self.generations = _charge(answer, jobs)
        self.character_id = _character_id(answer, jobs)


def _post(endpoint: str, body: dict[str, Any], key: str, check_cancel: CheckCancel, wait: Wait) -> _Done:
    status, answer = _transport("POST", f"/{endpoint}", body, key, check_cancel)
    if not 200 <= status < 300 or not isinstance(answer, dict):
        raise ProviderError(_refusal(endpoint, status, answer))
    ids = [str(i) for i in answer.get("background_job_ids") or []]
    if answer.get("background_job_id"):
        ids.append(str(answer["background_job_id"]))
    jobs: list[dict[str, Any]] = []
    try:
        for job_id in ids:
            jobs.append(_poll(job_id, key, check_cancel, wait))
    except BaseException:  # a cancel (or any exit) while jobs are in flight: DELETE every one not finished
        finished = {job.get("id") for job in jobs}
        for job_id in ids:
            if job_id not in finished:
                _delete(job_id, key)
        raise
    done = _Done(answer, jobs)
    for job in jobs:
        if job.get("status") == "failed":
            raise ProviderError(f"a PixelLab job for {endpoint} failed: {_job_error(job)}",
                                billed_usd=done.usd, billed_generations=done.generations)
    return done


def _poll(job_id: str, key: str, check_cancel: CheckCancel, wait: Wait) -> dict[str, Any]:
    """Poll a job until it ends. The wait is the caller's (cancellable); the time is the sum of the waits."""
    waited = 0.0
    while True:
        check_cancel()
        status, job = _transport("GET", f"/background-jobs/{job_id}", None, key, check_cancel)
        if status != 200 or not isinstance(job, dict):
            raise ProviderError(_refusal(f"background-jobs/{job_id}", status, job))
        job.setdefault("id", job_id)
        if job.get("status") in JOB_STATES_END:
            return job
        if waited >= JOB_TIMEOUT_S:
            raise ProviderError(f"PixelLab job {job_id} did not end in {JOB_TIMEOUT_S // 60} minutes")
        seconds = POLL_S if waited < LATE_AFTER_S else POLL_LATE_S
        wait(seconds)
        waited += seconds


def _delete(job_id: str, key: str) -> None:
    """Cancel a job at PixelLab (free while queued). Best effort: the cancel that got us here goes on."""
    try:
        _transport("DELETE", f"/background-jobs/{job_id}", None, key, lambda: None)
    except Exception:  # noqa: BLE001 - the original cancel must not be replaced
        pass


def _with_zip(name: str, done: _Done, character_id: str, key: str, check_cancel: CheckCancel,
              wait: Wait) -> OperationResult:
    """The operation's result with the character's ZIP, fetched (free) once PixelLab has built it.

    The character is made and charged by now, so this never raises: when the ZIP can't be had (refused, still building
    after ZIP_TRIES, a network error, or a cancel while waiting) the result has `archive` None and says why in
    `data["zip_missing"]` (`data["cancelled"]` True for a cancel), so core keeps the character's ID and the real charge.
    Core stops after a cancel."""

    def partial(why: str, cancelled: bool = False) -> OperationResult:
        data: dict[str, Any] = {"zip_missing": why}
        if cancelled:
            data["cancelled"] = True
        return OperationResult(name=name, usd=done.usd, generations=done.generations, character_id=character_id,
                               archive=None, data=data, job_ids=done.job_ids)

    try:
        for attempt in range(ZIP_TRIES):
            check_cancel()
            status, content = _transport("GET", f"/characters/{character_id}/zip", None, key, check_cancel)
            if status == 200 and isinstance(content, bytes):
                return OperationResult(name=name, usd=done.usd, generations=done.generations,
                                       character_id=character_id, archive=content, job_ids=done.job_ids)
            if status not in (202, 423):
                return partial(_refusal(f"characters/{character_id}/zip", status, content))
            if attempt + 1 < ZIP_TRIES:
                wait(POLL_S)
    except Exception as error:  # noqa: BLE001 - a network error: the character is made all the same
        return partial(f"the ZIP couldn't be fetched: {error}")
    except BaseException as stop:  # a cancel (core's, or Ctrl+C) while the ZIP was built
        if isinstance(stop, (SystemExit, GeneratorExit)):
            raise
        return partial("cancelled while PixelLab built the ZIP", cancelled=True)
    return partial(f"PixelLab was still building the ZIP after {ZIP_TRIES} tries")


def _charge(answer: dict[str, Any], jobs: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    """`(usd, generations)` charged: the jobs' `usage` summed when they have one, else the first answer's; generations
    priced at USD_PER_GENERATION when there is no USD."""
    usages = [j["usage"] for j in jobs if isinstance(j.get("usage"), dict)]
    if not usages and isinstance(answer.get("usage"), dict):
        usages = [answer["usage"]]
    usd: float | None = None
    generations: float | None = None
    for usage in usages:
        if usage.get("usd") is not None:
            usd = round((usd or 0.0) + float(usage["usd"]), 6)
        if usage.get("generations") is not None:
            generations = round((generations or 0.0) + float(usage["generations"]), 6)
    if usd is None and generations is not None:
        usd = round(generations * USD_PER_GENERATION, 6)
    return usd, generations


def _character_id(answer: dict[str, Any], jobs: list[dict[str, Any]]) -> str | None:
    for source in (answer, *(j.get("last_response") for j in jobs)):
        if isinstance(source, dict) and source.get("character_id"):
            return str(source["character_id"])
    return None


def _job_error(job: dict[str, Any]) -> str:
    for source in (job, job.get("last_response")):
        if isinstance(source, dict):
            for field_name in ("error", "message", "detail"):
                if source.get(field_name):
                    return str(source[field_name])[:300]
    return "no reason given"


def _refusal(what: str, status: int, answer: Any) -> str:
    text = answer.decode("utf-8", "replace") if isinstance(answer, bytes) else json.dumps(answer)
    hint = {401: " (the key was refused)", 402: " (out of credits, or an endpoint that needs a subscription)",
            403: " (an endpoint that needs a subscription)"}.get(status, "")
    return f"PixelLab refused {what} (HTTP {status}){hint}: {text[:300]}"


# --- images -------------------------------------------------------------------------------------------------------

def _image(png: bytes) -> dict[str, str]:
    width, height = _png_size(InputImage("image", png))
    if max(width, height) > MAX_PX:
        raise ProviderError(f"an image of {width}x{height} px: PixelLab takes at most {MAX_PX}x{MAX_PX}")
    return {"type": "base64", "base64": base64.b64encode(png).decode("ascii"), "format": "png"}


def _png_size(image: InputImage) -> tuple[int, int]:
    if image.png[:8] != b"\x89PNG\r\n\x1a\n" or len(image.png) < 24:
        raise ProviderError(f"{image.name} is not a PNG")
    return int.from_bytes(image.png[16:20], "big"), int.from_bytes(image.png[20:24], "big")


def _images_in(value: Any) -> list[bytes]:
    """Every base64 image in an answer, in order (a bare string or a data URL)."""
    found: list[bytes] = []
    if isinstance(value, dict):
        if isinstance(value.get("base64"), str):
            found.append(base64.b64decode(value["base64"].split(",", 1)[-1]))
        else:
            for item in value.values():
                found.extend(_images_in(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_images_in(item))
    elif isinstance(value, str) and value.startswith("data:image/"):
        found.append(base64.b64decode(value.split(",", 1)[1]))
    return found


# --- the request layer --------------------------------------------------------------------------------------------

def _need_key(key: str | None) -> str:
    if not key:
        raise ProviderError("no PixelLab key was given")
    return key


def _need(params: dict[str, Any], name: str) -> Any:
    if params.get(name) in (None, ""):
        raise ProviderError(f"the operation needs the parameter '{name}'")
    return params[name]


def _view(params: dict[str, Any]) -> str:
    view = str(params.get("view") or "high top-down")
    if view not in VIEWS:
        raise ProviderError(f"'{view}' is not a camera view: {', '.join(VIEWS)}")
    return view


def _frame_number(name: str) -> int:
    match = re.search(r"(\d+)$", name)
    return int(match.group(1)) if match else 0


def _direction(name: str) -> str:
    if name not in DIRECTIONS:
        raise ProviderError(f"'{name}' is not a direction: {', '.join(DIRECTIONS)}")
    return name


# `transport(method, path, body, key, check_cancel)` -> `(HTTP status, JSON answer or ZIP bytes)`; the path is under API.
Transport = Callable[[str, str, dict[str, Any] | None, str, CheckCancel], tuple[int, Any]]


def _send_cancellable(method: str, path: str, body: dict[str, Any] | None, key: str,
                      check_cancel: CheckCancel) -> tuple[int, Any]:
    """Send on a thread and wait for it, checking the cancel token every THREAD_POLL_S. The key goes in the Authorization
    header only."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    built = urllib.request.Request(f"{API}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "kiripix"})
    box: dict[str, Any] = {}

    def send() -> None:
        try:
            with urllib.request.urlopen(built, timeout=TIMEOUT_S) as response:  # noqa: S310 (a fixed https URL)
                box["answer"] = (response.status, response.headers.get("Content-Type", ""), response.read())
        except urllib.error.HTTPError as error:
            box["answer"] = (error.code, error.headers.get("Content-Type", "") if error.headers else "", error.read())
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            box["error"] = ProviderError(f"the call to PixelLab failed: {error}")

    worker = threading.Thread(target=send, daemon=True)
    worker.start()
    while worker.is_alive():
        check_cancel()
        worker.join(THREAD_POLL_S)
    if "error" in box:
        raise box["error"]
    status, content_type, raw = box["answer"]
    if "zip" in content_type or "octet-stream" in content_type or raw[:2] == b"PK":
        return status, raw
    try:
        return status, json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, ValueError):
        return status, {"raw": raw[:300].decode("utf-8", "replace")}


_transport: Transport = _send_cancellable


def set_transport(transport: Transport) -> None:
    """Replace how a request reaches PixelLab. For the test harness only (`KIRIPIX_TEST_RECIPES`): its fake answers from
    the request and keeps what was sent, so no test reaches the network."""
    global _transport
    _transport = transport
