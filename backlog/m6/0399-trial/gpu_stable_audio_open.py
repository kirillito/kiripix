#!/usr/bin/env python3
"""TO RUN ON THE GPU MACHINE ONLY. Never run on the machine without a GPU (Owner, 2026-11-27); it has not been run.

Generates the five trial prompts with Stable Audio Open 1.0 (open weights, Stability AI Community License) so the
Owner can compare them with the paid providers' outputs. It spends no money, but it downloads the weights
(gated on Hugging Face: accept the licence on the model page and `huggingface-cli login` first) and uses the GPU.

    pip install torch diffusers transformers accelerate soundfile      # in a throwaway venv, not the Project's
    python gpu_stable_audio_open.py --takes 3

Outputs: out/stable-audio-open/<prompt id>_<n>.wav (44.1 kHz stereo), then slice-and-sheet.sh as for the others.
It prints the peak VRAM and the seconds per generation: copy them into findings.md section 8.
Not verified: the diffusers pipeline arguments below follow the model card read on 2026-11-27 (use
`StableAudioPipeline.from_pretrained("stabilityai/stable-audio-open-1.0")`); if one changed, the model card wins.
Output limit of the model: up to 47 s. Weights: ~ several GB (size not read from the page; it prints what it fetched).
The Kiripix rules for a Runner would apply if this became one: weights into .kiripix/weights/, one model loaded at a
time, unload after use, 8 GB VRAM shared with Blender, CPU fallback (slow).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "stabilityai/stable-audio-open-1.0"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes", type=int, default=3)
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    ap.add_argument("--weights-dir", default=None, help="cache dir for the weights (default: the Hugging Face cache)")
    a = ap.parse_args()

    import soundfile as sf
    import torch
    from diffusers import StableAudioPipeline

    dtype = torch.float16 if a.device == "cuda" else torch.float32
    pipe = StableAudioPipeline.from_pretrained(MODEL, torch_dtype=dtype, cache_dir=a.weights_dir).to(a.device)
    prompts = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))["prompts"]
    outdir = HERE / "out" / "stable-audio-open"
    outdir.mkdir(parents=True, exist_ok=True)
    if a.device == "cuda":
        torch.cuda.reset_peak_memory_stats()
    for p in prompts:
        for n in range(1, a.takes + 1):
            gen = torch.Generator(a.device).manual_seed(1000 * n)
            t0 = time.time()
            audio = pipe(
                prompt=p["text"],
                negative_prompt="low quality, music, speech",
                audio_end_in_s=float(p["duration_s"]),
                num_inference_steps=a.steps,
                num_waveforms_per_prompt=1,
                generator=gen,
            ).audios[0]
            dt = time.time() - t0
            # diffusers returns (channels, samples); soundfile wants (samples, channels).
            sf.write(outdir / f"{p['id']}_{n}.wav", audio.T.float().cpu().numpy(), pipe.vae.sampling_rate)
            print(f"{p['id']}_{n}: {dt:.1f} s")
    if a.device == "cuda":
        print(f"peak VRAM: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB")


if __name__ == "__main__":
    main()
