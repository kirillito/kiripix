#!/usr/bin/env python3
"""Generate the five trial prompts with each shortlisted provider. The Owner runs this (ticket 0399, 0381).

    python generate.py --provider elevenlabs --provider stability --takes 3

Nothing is sent until the estimated cost is printed and you type "yes". Keys come from the environment only
(ELEVENLABS_API_KEY, STABILITY_API_KEY); they are never written anywhere. Python 3.10+, standard library only.
Outputs: out/<provider>/<prompt id>_<n>.<ext>, plus out/<provider>/calls.jsonl (what was sent, the cost estimate;
no key). --dry-run prints the plan and the estimate and exits without asking for a key.

Prices are the ones read on 2026-11-27 (findings.md section 3). Check them against your account before you say yes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ElevenLabs: Sound Effects API $0.12 per minute (elevenlabs.io/pricing/api, 2026-11-27) = $0.002 per second.
EL_USD_PER_SECOND = 0.12 / 60
# Stability: Stable Audio 2.5 flat 8 credits per successful result, 1 credit = $0.01 (docs.stability.ai, 2026-11-27).
STABILITY_USD_PER_CALL = 8 * 0.01

PROVIDERS = {
    "elevenlabs": {"env": "ELEVENLABS_API_KEY", "ext": "mp3"},
    "stability": {"env": "STABILITY_API_KEY", "ext": "mp3"},
}


def estimate(provider: str, prompt: dict) -> float:
    if provider == "elevenlabs":
        return prompt["duration_s"] * EL_USD_PER_SECOND
    return STABILITY_USD_PER_CALL


def elevenlabs(key: str, prompt: dict, model: str) -> bytes:
    body = json.dumps({
        "text": prompt["text"],
        "duration_seconds": prompt["duration_s"],
        "prompt_influence": 0.3,
        "model_id": model,
    }).encode()
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/sound-generation?output_format=mp3_44100_128",
        data=body, method="POST",
        headers={"xi-api-key": key, "content-type": "application/json", "accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def stability(key: str, prompt: dict, fmt: str) -> bytes:
    # Stable Audio 2.5, synchronous: multipart form, accept audio/*.
    boundary = uuid.uuid4().hex
    fields = {"prompt": prompt["text"], "duration": str(prompt["duration_s"]),
              "model": "stable-audio-2.5", "output_format": fmt}
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')
    body = ("".join(parts) + f"--{boundary}--\r\n").encode()
    req = urllib.request.Request(
        "https://api.stability.ai/v2beta/audio/stable-audio-2/text-to-audio",
        data=body, method="POST",
        headers={"authorization": f"Bearer {key}", "accept": "audio/*",
                 "content-type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", action="append", choices=sorted(PROVIDERS), required=True)
    ap.add_argument("--takes", type=int, default=3, help="generations per prompt (default 3)")
    ap.add_argument("--only", action="append", help="a prompt id from prompts.json (repeatable); default all five")
    ap.add_argument("--elevenlabs-model", default="eleven_text_to_sound_v3",
                    help="v2 is deprecated and removed 2027-03-01 (docs, 2026-11-27)")
    ap.add_argument("--stability-format", default="mp3",
                    help="output_format for Stability; its accepted values were not read (check the API reference)")
    ap.add_argument("--max-usd", type=float, default=5.0, help="refuse a plan that costs more than this (default 5)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    prompts = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))["prompts"]
    if a.only:
        prompts = [p for p in prompts if p["id"] in a.only]
    total = 0.0
    print("Plan:")
    for prov in a.provider:
        sub = sum(estimate(prov, p) * a.takes for p in prompts)
        total += sub
        print(f"  {prov}: {len(prompts)} prompts x {a.takes} takes = {len(prompts) * a.takes} calls, about ${sub:.2f}")
    print(f"Estimated total: ${total:.2f}  (cap for this run: ${a.max_usd:.2f})")
    print("This spends real money or credits. It also needs a plan that allows commercial use of the output")
    print("if you mean to ship what comes out (ElevenLabs: a paid plan; see findings.md).")
    if total > a.max_usd:
        print("Refused: over --max-usd.", file=sys.stderr)
        return 3
    if a.dry_run:
        return 0
    if not sys.stdin.isatty():
        print("Refused: this needs an interactive terminal (ticket 0381: the Owner approves each call).", file=sys.stderr)
        return 3
    keys = {}
    for prov in a.provider:
        env = PROVIDERS[prov]["env"]
        if not os.environ.get(env):
            print(f"Refused: {env} is not set in the environment.", file=sys.stderr)
            return 1
        keys[prov] = os.environ[env]
    if input('Type "yes" to send these calls: ').strip() != "yes":
        print("Nothing sent.")
        return 0

    spent = 0.0
    for prov in a.provider:
        outdir = HERE / "out" / prov
        outdir.mkdir(parents=True, exist_ok=True)
        for p in prompts:
            for n in range(1, a.takes + 1):
                dest = outdir / f"{p['id']}_{n}.{PROVIDERS[prov]['ext']}"
                if dest.exists():
                    print(f"  skip {dest.name} (exists)")
                    continue
                cost = estimate(prov, p)
                try:
                    if prov == "elevenlabs":
                        data = elevenlabs(keys[prov], p, a.elevenlabs_model)
                    else:
                        data = stability(keys[prov], p, a.stability_format)
                except urllib.error.HTTPError as e:
                    # The body can say why (plan, credits, parameter); it never contains our key.
                    print(f"  FAILED {prov} {p['id']} {n}: HTTP {e.code} {e.read()[:300]!r}", file=sys.stderr)
                    continue
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(data)
                tmp.replace(dest)
                spent += cost
                with (outdir / "calls.jsonl").open("a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provider": prov,
                                        "prompt_id": p["id"], "take": n, "file": dest.name, "bytes": len(data),
                                        "estimated_usd": round(cost, 4), "text": p["text"],
                                        "duration_s": p["duration_s"]}) + "\n")
                print(f"  ok {dest.relative_to(HERE)} ({len(data)} bytes, about ${cost:.3f})")
    print(f"Done. Estimated spend this run: ${spent:.2f}. Check the real balance on each provider's dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
