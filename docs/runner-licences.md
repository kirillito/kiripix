# Runner licences

Checked at M0 (2026-11-02), against the upstream LICENSE files and READMEs. Kiripix may use a Runner only when its
code **and its weights** allow commercial use. Check again before upgrading any Runner's weights.

| Runner | Sizes | Code | Weights | Usable |
|---|---|---|---|---|
| SAM 2 / SAM 2.1 | tiny, small, base_plus, large | Apache-2.0 | Apache-2.0 (the README names the checkpoints explicitly) | **Yes**, every size |
| BiRefNet | — | MIT | MIT (the model card's licence tag; nothing says otherwise) | **Yes** |
| Depth Anything V2 | Small | Apache-2.0 | Apache-2.0 | **Yes** |
| Depth Anything V2 | Base, Large, Giant | Apache-2.0 | **CC-BY-NC-4.0** (non-commercial) | **Yes, non-commercial only** (owner's decision below) |
| LaMa (big-lama) | — | Apache-2.0 | Not stated upstream; the weights mirror the README links to is tagged Apache-2.0 | **Yes, with a caveat** |

**Owner's decision (2026-11-02):** Kiripix won't be sold, so non-commercial weights are allowed. Selling a game made
with Kiripix is a distant possibility. Before that happens, check every Asset built with a non-commercial Runner:
Kiripix's pinned calls record which Runner made each result, so those Assets can be found and rebuilt.

Notes:
- **Depth Anything V2:** Base, Large and Giant are non-commercial; Small is Apache-2.0. Prefer Small where its quality
  is enough (M5's depth-assisted parallax split), so fewer Assets would need rebuilding before a sale.
- **SAM 2, as Kiripix downloads it:** the upstream checkpoints are Apache-2.0, but Kiripix needs ONNX, and Meta publishes
  none. `runners/sam2.py` pins the conversion `onnx-community/sam2.1-hiera-small-ONNX` at one commit, by each file's
  hash. That repo (2026-11-03) states no licence of its own; a conversion of Apache-2.0 weights stays under Apache-2.0.
  The Owner accepted this for now (2026-11-03). It isn't a lasting choice: spec §8 says how to replace a Runner.
- **SAM 2:** the demo code's fonts (Inter, Noto Color Emoji) are SIL OFL 1.1, and a bundled `cc_torch` component is
  BSD-3-Clause. Neither affects the checkpoints, and both licences allow commercial use.
- **LaMa:** the repo (Samsung Research, 2021) is Apache-2.0. Its README links the big-lama weights from
  `huggingface.co/smartywu/big-lama`, which is tagged Apache-2.0, but the upstream repo never states the weights'
  licence itself. Big-lama is trained on Places2; a third-party packaging asks for Places2 attribution. Treat it as
  usable with attribution, and record the weights' hash when M2 pins it.
- **BiRefNet, as Kiripix downloads it:** `runners/birefnet.py` (ticket 0041) pins the ONNX conversion
  `onnx-community/BiRefNet-ONNX` at commit `534d3c82d3bb8b2f0867db6dfbc3a525b8e42f67`: the fp32 `onnx/model.onnx`
  (972,666,916 bytes, sha256 `58f621f00f5d756097615970a88a791584600dcf7c45b18a0a6267535a1ebd3c`, checked by downloading
  it 2026-11-04). That repo's card is tagged MIT, like `ZhengPeng7/BiRefNet` it was converted from; it states no licence
  text of its own. Only this full-size model is used, not the `lite` one or the fp16 file. Like SAM 2's conversion, it
  is not a lasting choice (spec §8). The Owner accepted this (2026-11-04).
- **LaMa, as Kiripix downloads it:** `runners/lama.py` (ticket 0040) pins the ONNX conversion `Carve/LaMa-ONNX` at
  commit `c3c0c9e468934d62e79c329e35d82dd09ff8c444`: the fp32 `lama_fp32.onnx` (208,044,816 bytes, sha256
  `1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6`, checked by downloading it 2026-11-04). It is the
  card's recommended file, a fixed 512 x 512 export of big-lama with opset 17, made with Carve's own FourierUnitJIT
  (the card says its result is identical to the original). The card is tagged Apache-2.0 and states no licence text of its
  own, like the other conversions. The `lama.onnx` (dynamo export) is not used. Not a lasting choice (spec §8). Places2
  attribution (above) still applies. The Owner accepted this (2026-11-04).
- **BiRefNet:** a Hugging Face discussion asked for an explicit statement that MIT covers the weights; the model card is
  tagged MIT and nothing says otherwise.

Sources: [SAM 2](https://github.com/facebookresearch/sam2),
[BiRefNet LICENSE](https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE),
[BiRefNet model card](https://huggingface.co/ZhengPeng7/BiRefNet),
[Depth Anything V2](https://github.com/DepthAnything/Depth-Anything-V2),
[LaMa LICENSE](https://github.com/advimman/lama/blob/main/LICENSE), [LaMa README](https://github.com/advimman/lama),
[big-lama weights](https://huggingface.co/smartywu/big-lama),
[Carve/LaMa-ONNX](https://huggingface.co/Carve/LaMa-ONNX).
