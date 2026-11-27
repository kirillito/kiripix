"""The OpenAI Provider: GPT Image through the OpenAI Images API (ticket 0379; the Owner's choice, 2026-11-23, ticket 0353).

Generation is `POST /v1/images/generations` (JSON); an edit is `POST /v1/images/edits` (JSON too: `images`, each an
`image_url` holding a base64 data URL, the first being the one edited; `mask`, an `image_url` the same way, applied to the
first image; `input_fidelity`). The JSON body is the one the Images API reference documents for every field used here; the
multipart form's mask field isn't documented. Images come back base64 in `data[].b64_json`, with the call's token `usage`.

Edits, read on 2026-11-23 (the reference and the guide): a mask "must be of the same format and size" as the image it
applies to and "contain an alpha channel"; "masking with GPT Image is entirely prompt-based" and the model "may not follow
its exact shape with complete precision". The meaning of alpha isn't stated now; the earlier GPT Image convention, alpha 0
where the model paints, is the one sent. `input_fidelity` ("high" | "low") is documented for `gpt-image-1.5` (both) and
`gpt-image-1-mini` (low only), and "for `gpt-image-2`, omit this parameter"; nothing is said for 2.5 or 2.6, nor about its
cost, so it is sent only to the models named (`FIDELITIES`) unless `[providers.openai] input_fidelity` forces it, and the
estimate is unchanged. `markup` (2.5, 2.6) can't be combined with a mask and isn't used.

Read on 2026-11-23 from developers.openai.com (the image generation guide, the pricing page, the models catalogue, the
deprecations page and the Images API reference):
- GPT-Image-2.6 Sunburst and Flare are what OpenAI tells new integrations to use; `gpt-image-2` is deprecated (shutdown
  2027-02-10); `gpt-image-1` was shut down on 2026-10-23. The edit endpoint's default model is `gpt-image-2.6-sunburst`.
- Any WIDTHxHEIGHT with both edges multiples of 16, an aspect between 1:3 and 3:1, at most 3840 px on an edge and
  655,360 to 8,294,400 px in all (above 2560 x 1440 is experimental). `n` is 1 to 10; an edit takes up to 16 images.
- Prices are per token only: image output $30, image input $8, text input $5 per million (the 2.5, 2.6 and 2 models alike).
  OpenAI gives no per-image table for these models (its calculator wasn't readable), so the estimate takes the output
  tokens per image from `gpt-image-2`'s last per-image table at 1024 x 1024 ($0.006 low, $0.053 medium, $0.211 high: 200,
  1,767 and 7,033 tokens at $30 a million), scaled by the image's area. The actual cost is priced from the reported usage.

Not tested (the Owner, 2026-11-23: tests cost $0): the tests use a fake Provider. The key comes from core, which reads the
art Project's `.env`; it is sent in the Authorization header and never written anywhere.
"""

from __future__ import annotations

import base64
import json
import math
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from kiripix.providers.base import CheckCancel, Provider, ProviderError, ProviderRequest, ProviderResult, Wait

API = "https://api.openai.com/v1/images"
TIMEOUT_S = 300  # OpenAI: complex prompts may take up to 2 minutes
POLL_S = 0.2

PRICES_DATE = "2026-11-23"
USD_PER_TOKEN = {"text_in": 5.00 / 1e6, "image_in": 8.00 / 1e6, "image_out": 30.00 / 1e6}
OUTPUT_TOKENS_PER_MEGAPIXEL = {"low": 200, "medium": 1767, "high": 7033}  # per 1024 x 1024, see above
IMAGE_IN_TOKENS = 1000  # an estimate per input image; the reported usage gives the real figure
CHARS_PER_TOKEN = 4

FIDELITIES = {"gpt-image-1.5": ("low", "high"), "gpt-image-1-mini": ("low",)}  # by model, dated snapshots included

EDGE_STEP = 16
MIN_PIXELS = 655_360
MAX_PIXELS = 8_294_400
MAX_EDGE = 3840
MAX_RATIO = 3.0


class OpenAI(Provider):
    id = "openai"
    description = "OpenAI's GPT Image, through the OpenAI Images API (paid, per token)."
    key_name = "OPENAI_API_KEY"
    default_model = "gpt-image-2.6-sunburst"
    default_quality = "medium"
    qualities = ("low", "medium", "high")
    max_count = 10
    max_images_in = 16
    prices_date = PRICES_DATE
    rerenders_kept_strip = True

    def fidelities(self, model: str) -> tuple[str, ...]:
        for name, values in FIDELITIES.items():
            if model == name or model.startswith(f"{name}-20"):
                return values
        return ()

    def estimate_usd(self, model: str, size: tuple[int, int], quality: str, count: int, images_in: int,
                     prompt_chars: int) -> float:
        area = size[0] * size[1] / (1024 * 1024)
        out = OUTPUT_TOKENS_PER_MEGAPIXEL[quality] * area * count * USD_PER_TOKEN["image_out"]
        text = math.ceil(prompt_chars / CHARS_PER_TOKEN) * USD_PER_TOKEN["text_in"]
        images = images_in * IMAGE_IN_TOKENS * USD_PER_TOKEN["image_in"]
        return out + text + images

    def fit_size(self, model: str, wanted: tuple[int, int]) -> tuple[int, int]:
        width, height = (max(1, int(v)) for v in wanted)
        ratio = width / height
        if ratio > MAX_RATIO:
            width = round(height * MAX_RATIO)
        elif ratio < 1 / MAX_RATIO:
            height = round(width * MAX_RATIO)
        scale = 1.0
        if width * height < MIN_PIXELS:
            scale = math.sqrt(MIN_PIXELS / (width * height))
        elif width * height > MAX_PIXELS:
            scale = math.sqrt(MAX_PIXELS / (width * height))
        scale = min(scale, MAX_EDGE / max(width * scale, height * scale) * scale)
        w = max(EDGE_STEP, round(width * scale / EDGE_STEP) * EDGE_STEP)
        h = max(EDGE_STEP, round(height * scale / EDGE_STEP) * EDGE_STEP)
        while w * h < MIN_PIXELS:  # rounding down may leave it a step short
            w, h = (w + EDGE_STEP, h) if w <= h else (w, h + EDGE_STEP)
        while w * h > MAX_PIXELS:
            w, h = (w - EDGE_STEP, h) if w >= h else (w, h - EDGE_STEP)
        return w, h

    def call(self, request: ProviderRequest, key: str | None, check_cancel: CheckCancel,
             wait: Wait | None = None) -> ProviderResult:
        if not key:
            raise ProviderError("no OpenAI key was given")
        size = f"{request.size[0]}x{request.size[1]}"
        payload: dict[str, Any] = {"model": request.model, "prompt": request.prompt, "n": request.count, "size": size,
                                   "quality": request.quality, "output_format": "png"}
        if request.images:
            payload["images"] = [{"image_url": _data_url(image.png)} for image in request.images]
            if request.mask is not None:
                payload["mask"] = {"image_url": _data_url(request.mask)}
            if request.input_fidelity is not None:
                payload["input_fidelity"] = request.input_fidelity
        built = urllib.request.Request(f"{API}/{'edits' if request.images else 'generations'}",
                                       data=json.dumps(payload).encode("utf-8"), method="POST",
                                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        answer = _transport(built, check_cancel)
        images = [base64.b64decode(item["b64_json"]) for item in answer.get("data", []) if item.get("b64_json")]
        usage = answer.get("usage") or {}
        usd = _priced(usage) if usage else None
        if not images:
            raise ProviderError("OpenAI answered with no images", billed_usd=usd)
        return ProviderResult(images=images, usd=usd, usage=_flat_usage(usage))


def _flat_usage(usage: dict[str, Any]) -> dict[str, int]:
    """The reported token counts, flat: `input_tokens`, `output_tokens`, `total_tokens`, and the details as
    `input_text_tokens`, `input_image_tokens`, `output_text_tokens`, `output_image_tokens`."""
    flat = {k: int(v) for k, v in usage.items() if isinstance(v, int)}
    for side in ("input", "output"):
        details = usage.get(f"{side}_tokens_details") or {}
        for kind in ("text", "image"):
            if isinstance(details.get(f"{kind}_tokens"), int):
                flat[f"{side}_{kind}_tokens"] = int(details[f"{kind}_tokens"])
    return flat


def _priced(usage: dict[str, Any]) -> float:
    """A call's cost from its reported usage: text and image input tokens, and output tokens at the image rate."""
    details = usage.get("input_tokens_details") or {}
    text_in = int(details.get("text_tokens", 0))
    image_in = int(details.get("image_tokens", max(0, int(usage.get("input_tokens", 0)) - text_in)))
    out = int(usage.get("output_tokens", 0))
    return text_in * USD_PER_TOKEN["text_in"] + image_in * USD_PER_TOKEN["image_in"] + out * USD_PER_TOKEN["image_out"]


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _send_cancellable(request: urllib.request.Request, check_cancel: CheckCancel) -> dict[str, Any]:
    """Send the request on a thread and wait for it, checking the cancel token every `POLL_S`. On a cancel the thread is
    left to finish on its own; what `check_cancel` raises goes up (core records the call's estimate: it may be billed)."""
    box: dict[str, Any] = {}

    def send() -> None:
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310 (a fixed https URL)
                box["answer"] = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            box["error"] = ProviderError(f"OpenAI refused the call (HTTP {error.code}): {_error_message(error)}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            box["error"] = ProviderError(f"the call to OpenAI failed: {error}")

    worker = threading.Thread(target=send, daemon=True)
    worker.start()
    while worker.is_alive():
        check_cancel()
        worker.join(POLL_S)
    if "error" in box:
        raise box["error"]
    answer: dict[str, Any] = box["answer"]
    return answer


Transport = Callable[[urllib.request.Request, CheckCancel], dict[str, Any]]
_transport: Transport = _send_cancellable


def set_transport(transport: Transport) -> None:
    """Replace how a request reaches OpenAI. For the test harness only (`KIRIPIX_TEST_RECIPES`): its fake answers from
    the request and keeps what was sent, so no test reaches the network (the Owner, 2026-11-23: tests cost $0)."""
    global _transport
    _transport = transport


def _error_message(error: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(error.read().decode("utf-8"))
        return str(body.get("error", {}).get("message", "")) or error.reason
    except (ValueError, OSError, AttributeError):
        return str(error.reason)
