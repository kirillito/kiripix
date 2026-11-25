"""Trial 0354: PixelLab's API, called by hand, every call kept.

Not Kiripix code (the ticket keeps prototype code in this folder). Run from the repository root with the uv environment:

    uv run python backlog/m6/0354-trial/pixellab.py <command> [options]
    uv run python backlog/m6/0354-trial/pixellab.py --help

The key is read from the environment variable PIXELLAB_API_KEY only, sent in the Authorization header, and never written.

Each call that reaches the API gets a folder `runs/<NNN>-<command>-<label>/` beside this file, holding:
- `request.json`: the body sent, each image replaced by the name of the PNG it came from (`"<image: in_first_frame.png>"`),
  the images themselves as `in_*.png`;
- `response.json`: the first response; `job.json`: the background job's final state, when there is one;
- `out_*.png`: every image the responses hold (base64 or a URL), in the order found;
- and a line in `runs/ledger.jsonl`: the endpoint, the HTTP status, `usage` (the jobs' charge, USD or generations; the first
  response's own `usage` is kept beside it as `response_usage`), the estimate, the seed, the job IDs.

The spend cap: before a call, the ledger's USD total plus the call's estimate (PixelLab's own figures, read 2026-11-25) must
stay under PIXELLAB_TRIAL_CAP_USD (default 10: the ticket's $15 for the whole trial, less $5 kept for GPT Image's pose
transfer; check that with `kiripix cost` in the art Project and lower the cap if GPT has spent more). `--dry-run` writes the
run folder with `request.json` and sends nothing.

The API (`https://api.pixellab.ai/v2`, read 2026-11-25 from `/v2/openapi.json`): images go as
`{"type": "base64", "base64": <data>, "format": "png"}`; long calls answer `{"background_job_id"}` and are polled at
`GET /v2/background-jobs/{id}` until `status` is `completed` or `failed`; `DELETE` there cancels (free while queued).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

API = os.environ.get("PIXELLAB_TRIAL_API") or "https://api.pixellab.ai/v2"  # another only for a local fake server
POLL_S = float(os.environ.get("PIXELLAB_TRIAL_POLL_S") or 6.0)
HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("PIXELLAB_TRIAL_RUNS") or HERE / "runs")  # another folder only for trying the script out
LEDGER = RUNS / "ledger.jsonl"
JOB_TIMEOUT_S = 15 * 60

DIRECTIONS = ("south", "south-west", "west", "north-west", "north", "north-east", "east", "south-east")
SHORT = {"s": "south", "sw": "south-west", "w": "west", "nw": "north-west", "n": "north", "ne": "north-east",
         "e": "east", "se": "south-east"}
VIEWS = ("low top-down", "high top-down", "side")
TEMPLATES = ("mannequin", "bear", "cat", "dog", "horse", "lion")

# PixelLab's estimates in USD, from its price list and the OpenAPI descriptions (read 2026-11-25). A generation on prepaid
# credits is priced here at $0.0173 (the 64 px create-character-with-8-directions figure the ticket quotes is "1 generation");
# the ledger records the real charge from each response's `usage`, and only that counts toward the cap once known.
USD_PER_GENERATION = 0.0173
ESTIMATE_USD = {
    "animate-with-text-v3": 0.025,       # about $0.022 at 32 px, 4 frames; more frames or a larger canvas cost more
    "characters/animations": 0.0129,     # v3, per direction, 4 frames at 64 px
    "create-character-v3": 0.0173,       # a full set of direction_images imports for 0.25 generations
    "animate-with-skeleton-v3": 0.0513,  # 8 frames (3 generations); 15 frames are 4
    "estimate-skeleton": 0.005,
    "estimate-custom-skeleton": 0.02,    # not priced in the OpenAPI text; a guess, the ledger has the real one
    "create-character-state": 0.05,      # not priced in the OpenAPI text; a guess (8 rotations edited)
    "generate-image-v2": 0.05,           # not priced in the OpenAPI text; a guess
}


# --- the run folder and the ledger -------------------------------------------------------------------------------------

def _ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]


def spent_usd() -> float:
    """The ledger's USD total: each call's `usage.usd`, its generations priced at USD_PER_GENERATION, and the estimate of
    an accepted call whose charge never came back (a job cancelled, timed out or failed), so the cap stays on the safe side."""
    total = 0.0
    for entry in _ledger():
        usage = entry.get("usage") or {}
        if usage.get("usd") is not None:
            total += float(usage["usd"])
        elif usage.get("generations") is not None:
            total += float(usage["generations"]) * USD_PER_GENERATION
        elif entry.get("http_status") == 200:
            total += float(entry.get("estimated_usd") or 0.0)
    return total


def cap_usd() -> float:
    return float(os.environ.get("PIXELLAB_TRIAL_CAP_USD", "10"))


def new_run(command: str, label: str) -> Path:
    RUNS.mkdir(exist_ok=True)
    numbers = [int(m.group(1)) for p in RUNS.iterdir() if (m := re.match(r"(\d{3})-", p.name))]
    slug = re.sub(r"[^a-z0-9]+", "_", f"{command}-{label}".lower()).strip("_")[:60]
    folder = RUNS / f"{(max(numbers) + 1 if numbers else 1):03d}-{slug}"
    folder.mkdir()
    return folder


def write_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    temp.replace(path)


def append_ledger(entry: dict) -> None:
    RUNS.mkdir(exist_ok=True)
    with LEDGER.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --- images -----------------------------------------------------------------------------------------------------------

class Images:
    """The images of one request: each is sent as base64 and kept in the run folder as `in_<name>.png`."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def add(self, name: str, path: Path, crop: int | None = None) -> dict:
        image = Image.open(path).convert("RGBA")
        if crop:
            image = crop_square(image, crop, path)
        if max(image.size) > 256:
            sys.exit(f"{path}: {image.size[0]}x{image.size[1]}; PixelLab takes at most 256x256")
        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, format="PNG")
        data = buffer.getvalue()
        self.files[f"in_{name}.png"] = data
        encoded = base64.b64encode(data).decode("ascii")
        return {"type": "base64", "base64": encoded, "format": "png", "__file__": f"in_{name}.png"}


def crop_square(image: Image.Image, size: int, path: Path) -> Image.Image:
    """A size x size canvas cut around the sprite's opaque pixels, nothing resampled; refused if the sprite doesn't fit."""
    box = image.getchannel("A").getbbox()
    if box is None:
        sys.exit(f"{path}: fully transparent")
    left, top, right, bottom = box
    if right - left > size or bottom - top > size:
        sys.exit(f"{path}: the sprite is {right - left}x{bottom - top}, past a {size}x{size} canvas")
    x = min(max(0, (left + right - size) // 2), max(0, image.width - size))
    y = min(max(0, (top + bottom - size) // 2), max(0, image.height - size))
    canvas = Image.new("RGBA", (size, size))
    canvas.alpha_composite(image.crop((x, y, x + size, y + size)))
    return canvas


def _sent(body: Any) -> Any:
    """The body as sent: without the `__file__` names."""
    if isinstance(body, dict):
        return {k: _sent(v) for k, v in body.items() if k != "__file__"}
    if isinstance(body, list):
        return [_sent(v) for v in body]
    return body


def _kept(body: Any) -> Any:
    """The body as kept in request.json: each image replaced by its file's name."""
    if isinstance(body, dict):
        if "__file__" in body:
            return f"<image: {body['__file__']}>"
        return {k: _kept(v) for k, v in body.items()}
    if isinstance(body, list):
        return [_kept(v) for v in body]
    return body


def save_images(value: Any, folder: Path, found: list[str] | None = None, key: str = "") -> list[str]:
    """Saves every image in a response, in order: a base64 string (bare or a data URL) or an http(s) URL to a PNG."""
    found = [] if found is None else found
    if isinstance(value, dict):
        if isinstance(value.get("base64"), str):
            _save_bytes(base64.b64decode(value["base64"].split(",", 1)[-1]), folder, found, key)
            return found
        for k, v in value.items():
            save_images(v, folder, found, f"{key}_{k}" if key else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            save_images(v, folder, found, f"{key}_{i:03d}" if key else f"{i:03d}")
    elif isinstance(value, str):
        if value.startswith("data:image/"):
            _save_bytes(base64.b64decode(value.split(",", 1)[1]), folder, found, key)
        elif re.match(r"https://\S+\.(png|gif|webp)(\?\S*)?$", value):
            try:
                with urllib.request.urlopen(value, timeout=60) as response:
                    _save_bytes(response.read(), folder, found, key)
            except (urllib.error.URLError, TimeoutError) as error:
                print(f"  could not download {value}: {error}", file=sys.stderr)
    return found


def _save_bytes(data: bytes, folder: Path, found: list[str], key: str) -> None:
    name = f"out_{len(found):03d}_{re.sub(r'[^a-zA-Z0-9]+', '_', key).strip('_')[:50] or 'image'}.png"
    try:
        Image.open(io.BytesIO(data)).save(folder / name)
    except OSError:
        (folder / name).with_suffix(".bin").write_bytes(data)
    found.append(name)


# --- HTTP -------------------------------------------------------------------------------------------------------------

def _key() -> str:
    key = os.environ.get("PIXELLAB_API_KEY", "").strip()
    if not key:
        sys.exit("PIXELLAB_API_KEY is not set (PixelLab: Account → API). It is read from the environment only.")
    return key


def http(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{API}{path}", data=data, method=method, headers={
        "Authorization": f"Bearer {_key()}", "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "kiripix-trial-0354"})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    try:
        return status, json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return status, {"raw": raw[:2000].decode("utf-8", "replace")}


def poll(job_id: str, folder: Path) -> dict:
    """Polls a background job until it ends; Ctrl+C cancels it (DELETE), free while it is queued."""
    started = time.monotonic()
    try:
        while True:
            status, job = http("GET", f"/background-jobs/{job_id}")
            if status != 200:
                return {"http_status": status, "body": job}
            write_json(folder / "job.json", job)
            state = job.get("status")
            print(f"  job {job_id}: {state} ({time.monotonic() - started:.0f} s)", file=sys.stderr)
            if state in ("completed", "failed"):
                return job
            if time.monotonic() - started > JOB_TIMEOUT_S:
                return {"status": "timeout", "id": job_id}
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        status, body = http("DELETE", f"/background-jobs/{job_id}")
        print(f"  cancelled job {job_id}: HTTP {status} {body}", file=sys.stderr)
        return {"status": "cancelled", "id": job_id, "http_status": status, "body": body}


def call(command: str, label: str, endpoint: str, body: dict, images: Images, args: argparse.Namespace,
         estimate_usd: float) -> dict:
    """Sends one POST, polls its jobs, saves its images and appends the ledger. Refuses a call past the cap."""
    folder = new_run(command, label)
    write_json(folder / "request.json", {"endpoint": f"POST {API}/{endpoint}", "body": _kept(body)})
    for name, data in images.files.items():
        (folder / name).write_bytes(data)
    spent, cap = spent_usd(), cap_usd()
    print(f"{folder.name}: estimate ${estimate_usd:.4f}; spent ${spent:.4f} of ${cap:.2f}", file=sys.stderr)
    if args.dry_run:
        print(f"  dry run: nothing sent; the body is in {folder / 'request.json'}", file=sys.stderr)
        return {"folder": str(folder), "dry_run": True}
    if spent + estimate_usd > cap:
        sys.exit(f"  refused: ${spent:.4f} spent + ${estimate_usd:.4f} would pass the cap ${cap:.2f} "
                 "(PIXELLAB_TRIAL_CAP_USD)")
    status, response = http("POST", f"/{endpoint}", _sent(body))
    write_json(folder / "response.json", {"http_status": status, "body": response})
    jobs: list[dict] = []
    if status == 200 and isinstance(response, dict):
        ids = response.get("background_job_ids") or ([response["background_job_id"]]
                                                       if response.get("background_job_id") else [])
        for job_id in ids:
            jobs.append(poll(job_id, folder))
        if len(jobs) > 1:
            write_json(folder / "job.json", jobs)
    saved = save_images(response, folder) if status == 200 else []
    for i, job in enumerate(jobs):
        save_images(job.get("last_response"), folder, saved, f"job{i}")
    usage = _usage(response, jobs)
    entry = {"run": folder.name, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "endpoint": endpoint, "http_status": status,
             "usage": usage, "response_usage": response.get("usage") if isinstance(response, dict) else None,
             "estimated_usd": round(estimate_usd, 4), "seed": body.get("seed"), "job_ids": [j.get("id") for j in jobs],
             "job_status": [j.get("status") for j in jobs], "images": len(saved)}
    append_ledger(entry)
    print(json.dumps(entry, indent=1))
    if status in (402, 403):
        print(f"  HTTP {status}: {json.dumps(response)[:600]}\n  Read the body: 402 is out of credits, or (like 403) an "
              "endpoint that needs a subscription. On an animation endpoint with credits left, that is the tier "
              "check's answer: stop, and the Owner decides.", file=sys.stderr)
    elif status != 200:
        print(f"  HTTP {status}: {json.dumps(response)[:1200]}", file=sys.stderr)
    return {"folder": str(folder), **entry}


def _usage(response: Any, jobs: list[dict]) -> dict:
    """The charge: the jobs' `usage` summed when they have one, else the first response's."""
    usages = [j["usage"] for j in jobs if isinstance(j.get("usage"), dict)]
    if not usages and isinstance(response, dict) and isinstance(response.get("usage"), dict):
        usages = [response["usage"]]
    total: dict = {}
    for usage in usages:
        for key in ("usd", "generations"):
            if usage.get(key) is not None:
                total[key] = round(total.get(key, 0.0) + float(usage[key]), 6)
        total.setdefault("type", usage.get("type"))
    return total


# --- the commands -----------------------------------------------------------------------------------------------------

def direction(value: str) -> str:
    value = SHORT.get(value, value)
    if value not in DIRECTIONS:
        raise argparse.ArgumentTypeError(f"{value}: one of {', '.join(DIRECTIONS)} (or s, sw, w, nw, n, ne, e, se)")
    return value


def cmd_balance(args: argparse.Namespace) -> None:
    status, body = http("GET", "/balance")
    print(json.dumps({"http_status": status, "body": body, "ledger_spent_usd": round(spent_usd(), 4),
                      "cap_usd": cap_usd()}, indent=1))


def cmd_spent(args: argparse.Namespace) -> None:
    entries = _ledger()
    for e in entries:
        print(f"{e['run']:<48} {e['endpoint']:<28} HTTP {e['http_status']}  {e.get('usage')}")
    print(f"total ${spent_usd():.4f} of the cap ${cap_usd():.2f} (generations priced at ${USD_PER_GENERATION})")


def cmd_text_anim(args: argparse.Namespace) -> None:
    images = Images()
    body: dict = {"first_frame": images.add("first_frame", args.frame, args.crop), "action": args.action,
                  "frame_count": args.frames, "seed": args.seed, "no_background": True}
    if args.last:
        body["last_frame"] = images.add("last_frame", args.last, args.crop)
    width, height = (args.crop, args.crop) if args.crop else Image.open(args.frame).size
    if width * height * args.frames > 524_288:
        sys.exit(f"{width}x{height} x {args.frames} frames is past PixelLab's pixel budget of 524,288")
    estimate = ESTIMATE_USD["animate-with-text-v3"] * max(1.0, args.frames / 4) * max(1.0, width * height / 1024)
    call("text-anim", args.label or args.action, "animate-with-text-v3", body, images, args, estimate)


def cmd_character(args: argparse.Namespace) -> None:
    images = Images()
    body: dict = {"description": args.description, "view": args.view, "template_id": args.template,
                  "no_background": True, "seed": args.seed}
    if not args.south:  # from scratch: Pixen draws the south frame from the description, then v3 rotates it
        if args.dir:
            sys.exit("--dir needs --south (PixelLab's reference mode)")
        body["image_size"] = {"width": args.size, "height": args.size}
        call("character", args.label or args.description[:30], "create-character-v3", body, images, args,
             USD_PER_GENERATION * (1 + -(-args.size * args.size * 8 // 65536)))
        return
    body |= {"reference_image": images.add("south", args.south), "n_directions": 8}
    others: dict = {}
    size = Image.open(args.south).size
    for spec in args.dir or []:
        name, _, path = spec.partition("=")
        name = direction(name)
        if Image.open(path).size != size:
            sys.exit(f"{path}: every direction image needs the south one's canvas, {size[0]}x{size[1]}")
        others[name] = images.add(name, Path(path))
    if others:
        body["direction_images"] = others
    call("character", args.label or args.description[:30], "create-character-v3", body, images, args,
         ESTIMATE_USD["create-character-v3"])


def cmd_animate(args: argparse.Namespace) -> None:
    images = Images()
    body: dict = {"character_id": args.character, "frame_count": args.frames, "seed": args.seed}
    if args.template_animation:
        body |= {"mode": "template", "template_animation_id": args.template_animation}
    else:
        body |= {"mode": "v3", "action_description": args.action}
    if args.directions:
        body["directions"] = [direction(d) for d in args.directions.split(",")]
    if args.color_image:
        body |= {"color_image": images.add("color_image", args.color_image), "force_colors": args.force_colors}
    if args.palette:
        body["target_palette"] = {"colors": args.palette.split(","), "max_colors": args.max_colors}
    count = len(body.get("directions") or DIRECTIONS)
    estimate = ESTIMATE_USD["characters/animations"] * count * max(1.0, args.frames / 4)
    call("animate", args.label or args.action or args.template_animation, "characters/animations", body, images, args,
         estimate)


def cmd_estimate(args: argparse.Namespace) -> None:
    images = Images()
    body = {"image": images.add("image", args.image)}
    call("estimate", args.label or args.image.stem, "estimate-skeleton", body, images, args, ESTIMATE_USD["estimate-skeleton"])


def cmd_estimate_rig(args: argparse.Namespace) -> None:
    images = Images()
    body = {"images": [images.add(f"image{i}", p) for i, p in enumerate(args.image)], "direction": args.direction,
            "view": args.view, "description": args.description, "action": args.action}
    call("estimate-rig", args.label or args.description[:30], "estimate-custom-skeleton", body, images, args,
         ESTIMATE_USD["estimate-custom-skeleton"])


def cmd_skeleton(args: argparse.Namespace) -> None:
    """animate-with-skeleton-v3. --keypoints is a JSON file: {"first_frame_keypoints": [...], "keypoints": [[...], ...]},
    optionally with "rig"; keypoints.py writes one per clip and direction from a Kiripix render."""
    images = Images()
    plan = json.loads(args.keypoints.read_text(encoding="utf-8"))
    body: dict = {"description": args.description, "action": args.action, "direction": args.direction,
                  "view": args.view, "first_frame": images.add("first_frame", args.frame),
                  "first_frame_keypoints": plan["first_frame_keypoints"], "template_id": args.template,
                  "seed": args.seed, "no_background": True}
    if plan.get("rig"):
        body["rig"] = plan["rig"]
    if args.write_motion:
        body["write_motion_frames"] = args.write_motion
        frames = args.write_motion
    else:
        body["keypoints"] = plan["keypoints"]
        frames = len(plan["keypoints"])
    if not (1 if plan.get("rig") else 3) <= frames <= 15:
        sys.exit(f"{frames} frames: PixelLab takes 3 to 15 (1 to 15 with a rig); cut the clip (keypoints.py --frames)")
    generations = 2 if frames <= 3 else 3 if frames <= 8 else 4
    call("skeleton", args.label or f"{args.action}-{args.direction}", "animate-with-skeleton-v3", body, images, args,
         generations * USD_PER_GENERATION)


def cmd_state(args: argparse.Namespace) -> None:
    """create-character-state: one text edit applied to every rotation of an existing character, saved as a new
    character in its group. A pose in 8 directions in one call (game ticket 0106's route)."""
    images = Images()
    body: dict = {"character_id": args.character, "edit_description": args.edit, "state_name": args.name,
                  "no_background": True, "seed": args.seed,
                  "use_color_palette_from_reference": not args.free_colours}
    if args.canvas:
        width, _, height = args.canvas.partition("x")
        body["override_frame_size"] = {"width": int(width), "height": int(height or width)}
    call("state", args.label or args.name, "create-character-state", body, images, args, ESTIMATE_USD["create-character-state"])


def cmd_image(args: argparse.Namespace) -> None:
    """generate-image-v2: one image from a description, as many candidates as PixelLab's grid gives at that size (64 at
    up to 32 px), with an optional style image (pixel size, palette, outline) and subject references."""
    images = Images()
    body: dict = {"description": args.description, "image_size": {"width": args.size, "height": args.size},
                  "no_background": True, "seed": args.seed}
    if args.style:
        width, height = Image.open(args.style).size
        body |= {"style_image": {"image": images.add("style", args.style), "size": {"width": width, "height": height}},
                 "style_options": {"color_palette": True, "outline": True, "detail": True, "shading": True}}
    if args.reference:
        body["reference_images"] = [{"image": images.add(f"reference{i}", p), "size": dict(zip(
            ("width", "height"), Image.open(p).size))} for i, p in enumerate(args.reference)]
    call("image", args.label or args.description[:30], "generate-image-v2", body, images, args, ESTIMATE_USD["generate-image-v2"])


def cmd_rig_plan(args: argparse.Namespace) -> None:
    """An estimate-rig run's rig and placed frames as a keypoints file for `skeleton`: the first frame's joints are
    first_frame_keypoints, the rest (if any) the motion. With one frame, send `skeleton --write-motion N`."""
    job = json.loads((args.folder / "job.json").read_text(encoding="utf-8"))
    answer = job.get("last_response") or {}
    rig = answer.get("rig")
    frames = answer.get("frames") or answer.get("keypoints") or []
    frames = [f.get("keypoints", f) if isinstance(f, dict) else f for f in frames]
    if not rig or not frames:
        sys.exit(f"{args.folder / 'job.json'}: no `rig` and `frames` in last_response; keys are {sorted(answer)}")
    write_json(args.out, {"rig": rig, "first_frame_keypoints": frames[0], "keypoints": frames[1:],
                          "meta": {"from": str(args.folder)}})
    print(f"{args.out}: a rig of {len(rig)} joints, {len(frames)} frame(s)")


def cmd_pack(args: argparse.Namespace) -> None:
    """Run folders' frames as a ZIP the `sprite` Kind reads by its naming rule (`walk/south/frame_003.png`), for
    `kiripix import sprite.<name> <zip>`. Each CLIP:DIRECTION=RUN takes that run's out_*.png in order."""
    import zipfile
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as archive:
        for spec in args.frames:
            target, _, run = spec.partition("=")
            clip, _, side = target.partition(":")
            frames = sorted(Path(run).glob("out_*.png"))
            if not clip or not frames:
                sys.exit(f"{spec}: CLIP:DIRECTION=RUN_FOLDER, and the run folder needs out_*.png frames")
            for i, frame in enumerate(frames):
                archive.write(frame, f"{clip}/{direction(side)}/frame_{i:03d}.png")
            print(f"{clip}/{direction(side)}: {len(frames)} frames from {run}")
    print(args.out)


def cmd_job(args: argparse.Namespace) -> None:
    folder = new_run("job", args.job_id[:8])
    job = poll(args.job_id, folder)
    saved = save_images(job.get("last_response"), folder)
    print(json.dumps({"folder": str(folder), "status": job.get("status"), "usage": job.get("usage"), "images": saved}, indent=1))


def cmd_get(args: argparse.Namespace) -> None:
    """GET a resource (a character, its zip, its animations) into a run folder; costs nothing."""
    folder = new_run("get", args.path.strip("/").replace("/", "_"))
    if args.path.endswith("/zip"):
        request = urllib.request.Request(f"{API}{args.path}", headers={"Authorization": f"Bearer {_key()}"})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                (folder / "export.zip").write_bytes(response.read())
            print(f"{folder / 'export.zip'}")
        except urllib.error.HTTPError as error:
            print(f"HTTP {error.code}: {error.read()[:600]!r} (423: the character is still being made; try again)")
        return
    status, body = http("GET", args.path)
    write_json(folder / "response.json", {"http_status": status, "body": body})
    saved = save_images(body, folder) if status == 200 else []
    print(json.dumps({"folder": str(folder), "http_status": status, "images": saved}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="write the run folder and request.json; send nothing")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("balance", help="GET /v2/balance (free), and the ledger's total").set_defaults(run=cmd_balance)
    sub.add_parser("spent", help="the ledger, call by call, and its total").set_defaults(run=cmd_spent)

    p = sub.add_parser("text-anim", help="animate-with-text-v3: frames from one first frame and an action")
    p.add_argument("--frame", type=Path, required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--frames", type=int, default=4, help="4 to 16, even")
    p.add_argument("--last", type=Path, help="a last_frame, to close a loop")
    p.add_argument("--crop", type=int, help="cut the frames to this square around the sprite (the tier check: 32)")
    p.set_defaults(run=cmd_text_anim)

    p = sub.add_parser("character", help="create-character-v3 from our own frames (south + up to 7 more)")
    p.add_argument("--description", required=True)
    p.add_argument("--south", type=Path, help="our south frame (reference mode); leave out to draw from the description")
    p.add_argument("--dir", action="append", metavar="DIRECTION=PNG", help="another direction's frame; repeat")
    p.add_argument("--size", type=int, default=64, help="from scratch only: the canvas, 32 to 256")
    p.add_argument("--view", choices=VIEWS, default="high top-down")
    p.add_argument("--template", choices=TEMPLATES, default="mannequin", help="the body its skeleton is fitted to")
    p.set_defaults(run=cmd_character)

    p = sub.add_parser("animate", help="characters/animations in v3 (an action) or template mode, one job a direction")
    p.add_argument("--character", required=True)
    p.add_argument("--action", help="v3's action_description")
    p.add_argument("--template-animation", help="template mode: a template_animation_id such as walk")
    p.add_argument("--frames", type=int, default=4)
    p.add_argument("--directions", help="comma-separated, such as s,e,n,w; all of the character's by default")
    p.add_argument("--color-image", type=Path)
    p.add_argument("--force-colors", action="store_true")
    p.add_argument("--palette", help="target_palette colours, comma-separated #rrggbb")
    p.add_argument("--max-colors", type=int)
    p.set_defaults(run=cmd_animate)

    p = sub.add_parser("estimate", help="estimate-skeleton: the 18 humanoid joints of one sprite")
    p.add_argument("--image", type=Path, required=True)
    p.set_defaults(run=cmd_estimate)

    p = sub.add_parser("estimate-rig", help="estimate-custom-skeleton: a rig for an animal, placed on its frames")
    p.add_argument("--image", type=Path, action="append", required=True, help="repeat for several frames, same size")
    p.add_argument("--direction", type=direction, required=True)
    p.add_argument("--view", choices=VIEWS, default="high top-down")
    p.add_argument("--description", default="")
    p.add_argument("--action", default="")
    p.set_defaults(run=cmd_estimate_rig)

    p = sub.add_parser("skeleton", help="animate-with-skeleton-v3 from a keypoints file (keypoints.py)")
    p.add_argument("--frame", type=Path, required=True, help="the actor's frame, the size the keypoints are fractions of")
    p.add_argument("--keypoints", type=Path, required=True)
    p.add_argument("--direction", type=direction, required=True)
    p.add_argument("--description", required=True, help="what the actor looks like, a noun phrase")
    p.add_argument("--action", required=True)
    p.add_argument("--view", choices=VIEWS, default="high top-down")
    p.add_argument("--template", choices=TEMPLATES, default="mannequin")
    p.add_argument("--write-motion", type=int, help="let PixelLab write this many frames from --action instead")
    p.set_defaults(run=cmd_skeleton)

    p = sub.add_parser("state", help="create-character-state: a pose of an existing character, all its directions")
    p.add_argument("--character", required=True, help="the source character's id (`get /characters` lists them)")
    p.add_argument("--edit", required=True, help="the edit, such as 'lying flat on its back, paws in the air'")
    p.add_argument("--name", required=True, help="the state's name; it becomes the clip's folder in the ZIP")
    p.add_argument("--canvas", help="a larger canvas WxH (multiples of 4, 32 to 256) for a pose that needs room")
    p.add_argument("--free-colours", action="store_true", help="don't snap to the source's palette (it does by default)")
    p.set_defaults(run=cmd_state)

    p = sub.add_parser("image", help="generate-image-v2: candidates for one image, such as a prop")
    p.add_argument("--description", required=True)
    p.add_argument("--size", type=int, default=32)
    p.add_argument("--style", type=Path, help="a style image: pixel size, palette, outline, shading")
    p.add_argument("--reference", type=Path, action="append", help="a subject reference; up to 4")
    p.set_defaults(run=cmd_image)

    p = sub.add_parser("rig-plan", help="an estimate-rig run folder into a keypoints file for skeleton (no call)")
    p.add_argument("folder", type=Path, help="the estimate-rig run folder")
    p.add_argument("out", type=Path)
    p.set_defaults(run=cmd_rig_plan)

    p = sub.add_parser("pack", help="run folders' frames as a ZIP for `kiripix import` (no call)")
    p.add_argument("out", type=Path)
    p.add_argument("frames", nargs="+", metavar="CLIP:DIRECTION=RUN_FOLDER")
    p.set_defaults(run=cmd_pack)

    p = sub.add_parser("job", help="poll a background job again and save its images")
    p.add_argument("job_id")
    p.set_defaults(run=cmd_job)

    p = sub.add_parser("get", help="GET a path such as /characters/<id> or /characters/<id>/zip (free)")
    p.add_argument("path")
    p.set_defaults(run=cmd_get)

    for name in ("text-anim", "character", "animate", "estimate", "estimate-rig", "skeleton", "state", "image"):
        sub.choices[name].add_argument("--seed", type=int, default=0, help="0 is random; the ledger keeps it")
        sub.choices[name].add_argument("--label", help="a few words for the run folder's name")

    args = parser.parse_args()
    if args.command == "animate" and not (args.action or args.template_animation):
        parser.error("animate needs --action (v3) or --template-animation")
    args.run(args)


if __name__ == "__main__":
    main()
