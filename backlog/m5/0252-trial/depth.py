"""Trial 0252 step 2a: Depth Anything V2 Small (ONNX) on a room's Source -> depth.npy (float32, source px).

usage: python depth.py <source.png> <out_dir> [cuda|cpu] [long_side]
Prototype only. Weights: ~/.cache/kiripix-trial-0252/model.onnx (Apache-2.0, onnx-community conversion).
"""
import json, subprocess, sys, threading, time
from pathlib import Path
import numpy as np
import onnxruntime as ort
from PIL import Image

if hasattr(ort, "preload_dlls"):
    ort.preload_dlls()
MODEL = Path.home() / ".cache/kiripix-trial-0252/model.onnx"
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    return int(out.split()[0])


def main(src, out_dir, dev="cuda", long_side=1036):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")
    w, h = img.size
    s = long_side / max(w, h)
    nw, nh = max(14, round(w * s / 14) * 14), max(14, round(h * s / 14) * 14)
    x = np.asarray(img.resize((nw, nh), Image.BICUBIC), np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].astype(np.float32)

    base = gpu_used_mib()
    peak = [base]; stop = [False]
    def poll():
        while not stop[0]:
            peak[0] = max(peak[0], gpu_used_mib()); time.sleep(0.05)
    if dev == "cuda":
        threading.Thread(target=poll, daemon=True).start()
    prov = ["CUDAExecutionProvider"] if dev == "cuda" else ["CPUExecutionProvider"]
    t0 = time.time()
    sess = ort.InferenceSession(str(MODEL), providers=prov)
    t_load = time.time() - t0
    name = sess.get_inputs()[0].name
    t0 = time.time(); d = sess.run(None, {name: x})[0]; t_first = time.time() - t0
    t0 = time.time(); d = sess.run(None, {name: x})[0]; t_run = time.time() - t0
    stop[0] = True; time.sleep(0.15)
    d = d.reshape(d.shape[-2:]).astype(np.float32)          # relative inverse depth: bigger = nearer
    # back to source size
    dd = np.asarray(Image.fromarray(d, "F").resize((w, h), Image.BICUBIC))
    np.save(out / "depth.npy", dd)
    lo, hi = np.percentile(dd, [1, 99])
    Image.fromarray((np.clip((dd - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)).save(out / "depth.png")
    info = dict(device=dev, input=[nw, nh], load_s=round(t_load, 2), first_run_s=round(t_first, 2),
                run_s=round(t_run, 2), vram_baseline_mib=base,
                vram_peak_mib=peak[0] if dev == "cuda" else None,
                vram_delta_mib=peak[0] - base if dev == "cuda" else None,
                providers=sess.get_providers())
    (out / f"depth_{dev}.json").write_text(json.dumps(info, indent=1))
    print(info)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *(sys.argv[3:4] or ["cuda"]), *(int(a) for a in sys.argv[4:5]))
