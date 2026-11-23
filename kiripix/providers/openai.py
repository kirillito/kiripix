"""The OpenAI Provider: GPT Image through the OpenAI Images API (ticket 0379; the Owner's choice, 2026-11-23, ticket 0353).

Generation is `POST /v1/images/generations` (JSON); an edit is `POST /v1/images/edits` (multipart, one `image[]` part per
input image, the first being the one edited). Images come back base64 in `data[].b64_json`, with the call's token `usage`.

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
import uuid
from typing import Any

from kiripix.providers.base import CheckCancel, Provider, ProviderError, ProviderRequest, ProviderResult

API = "https://api.openai.com/v1/images"
TIMEOUT_S = 300  # OpenAI: complex prompts may take up to 2 minutes
POLL_S = 0.2

PRICES_DATE = "2026-11-23"
USD_PER_TOKEN = {"text_in": 5.00 / 1e6, "image_in": 8.00 / 1e6, "image_out": 30.00 / 1e6}
OUTPUT_TOKENS_PER_MEGAPIXEL = {"low": 200, "medium": 1767, "high": 7033}  # per 1024 x 1024, see above
IMAGE_IN_TOKENS = 1000  # an estimate per input image; the reported usage gives the real figure
CHARS_PER_TOKEN = 4

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

    def call(self, request: ProviderRequest, key: str | None, check_cancel: CheckCancel) -> ProviderResult:
        if not key:
            raise ProviderError("no OpenAI key was given")
        size = f"{request.size[0]}x{request.size[1]}"
        if request.images:
            boundary = uuid.uuid4().hex
            fields: list[tuple[str, str]] = [("model", request.model), ("prompt", request.prompt), ("n", str(request.count)),
                                             ("size", size), ("quality", request.quality), ("output_format", "png")]
            body = _multipart(boundary, fields, [("image[]", image.name, image.png) for image in request.images])
            built = urllib.request.Request(f"{API}/edits", data=body, method="POST", headers={
                "Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
        else:
            payload = {"model": request.model, "prompt": request.prompt, "n": request.count, "size": size,
                       "quality": request.quality, "output_format": "png"}
            built = urllib.request.Request(f"{API}/generations", data=json.dumps(payload).encode("utf-8"), method="POST",
                                           headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        answer = _send_cancellable(built, check_cancel)
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


def _multipart(boundary: str, fields: list[tuple[str, str]], files: list[tuple[str, str, bytes]]) -> bytes:
    parts: list[bytes] = []
    for name, value in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
                     + value.encode("utf-8") + b"\r\n")
    for name, filename, data in files:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                     f"Content-Type: image/png\r\n\r\n".encode("utf-8") + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts)


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


def _error_message(error: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(error.read().decode("utf-8"))
        return str(body.get("error", {}).get("message", "")) or error.reason
    except (ValueError, OSError, AttributeError):
        return str(error.reason)
