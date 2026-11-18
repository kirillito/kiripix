"""Ticket 0241 step 8: the set beside mc03 at 52 px and a ch01 room, at 1x and 3x, and a GIF that flips the emotion.

Needs out/portraits/ (run portrait_set.py on input/ first) and the art repo's sprite and plate.
Run: uv run python backlog/m5/0241-trial/layout.py [_locked]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from kiripix.ops import upscale  # noqa: E402

HERE = Path(__file__).parent
ART = Path("c:/Homespace/urban-mystery-club-art/assets")
SUFFIX = sys.argv[1] if len(sys.argv) > 1 else ""  # "_locked" lays out out/portraits_locked
PORTRAITS = HERE / "out" / f"portraits{SUFFIX}"
ORDER = ["neutral", "happy", "angry", "surprised", "sad", "worried"]
VIEW = (160, 100, 640, 360)  # the plate's crop: x, y, width, height (the game's 640 x 360)
FEET = (400, 170)  # the sprite's feet in the crop, on the laneway
PANEL = (28, 24, 34)


def rgba(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGBA"))


def paste(dst: np.ndarray, src: np.ndarray, x: int, y: int) -> None:
    h, w = src.shape[:2]
    y0, x0 = max(y, 0), max(x, 0)
    y1, x1 = min(y + h, dst.shape[0]), min(x + w, dst.shape[1])
    if y1 <= y0 or x1 <= x0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    d = dst[y0:y1, x0:x1]
    d[s[..., 3] == 255] = s[s[..., 3] == 255]


def scene(portrait: np.ndarray, sprite: np.ndarray, plate: np.ndarray) -> np.ndarray:
    """A 640 x 360 dialogue frame: the room, the sprite on the laneway, a dialogue box, the portrait standing on it."""
    x, y, w, h = VIEW
    frame = plate[y:y + h, x:x + w].copy()
    frame[..., 3] = 255
    paste(frame, sprite, FEET[0] - 39, FEET[1] - 68)
    box = np.zeros((86, 640 - 2 * 8, 4), np.uint8)
    box[...] = (*PANEL, 255)
    box[:2] = (200, 190, 170, 255)
    box[-2:] = (200, 190, 170, 255)
    box[:, :2] = (200, 190, 170, 255)
    box[:, -2:] = (200, 190, 170, 255)
    paste(frame, box, 8, 360 - 8 - 86)
    for i, width in enumerate((250, 300, 170)):  # grey bars for the text
        frame[360 - 8 - 86 + 16 + i * 16:360 - 8 - 86 + 22 + i * 16, 8 + 176:8 + 176 + width] = (150, 146, 156, 255)
    paste(frame, portrait, 12, 360 - 8 - 224 - 4 + 0)  # standing on the box's bottom edge (anchor: bottom centre)
    return frame


def main() -> None:
    meta = json.loads((PORTRAITS / "portrait.json").read_text())
    emotions = [e for e in ORDER if e in meta["emotions"]]
    ports = {e: rgba(PORTRAITS / meta["emotions"][e]) for e in emotions}
    sheet = rgba(ART / "character/mc03_female/out/export/color.png")
    character = json.loads((ART / "character/mc03_female/out/export/character.json").read_text())
    idle = next(c for c in character["clips"] if c["name"] == "idle")["directions"]["s"][0]["rect"]
    sprite = sheet[idle["y"]:idle["y"] + idle["height"], idle["x"]:idle["x"] + idle["width"]].copy()
    ys, _ = np.nonzero(sprite[..., 3])
    print("sprite opaque rows", ys.min(), ys.max(), "height", ys.max() - ys.min() + 1)
    plate = rgba(ART / "room/ch01_002_laneway/out/export/plate.png")

    frames = {e: scene(ports[e], sprite, plate) for e in emotions}
    # the sheet: the dialogue frame with the neutral, then the whole set in a row
    row_w = max(640, 160 * len(emotions) + 8 * (len(emotions) + 1))
    height = 360 + 8 + 224 + 8 + 14
    sheet_img = np.zeros((height, row_w, 4), np.uint8)
    sheet_img[...] = (*PANEL, 255)
    paste(sheet_img, frames["neutral"], (row_w - 640) // 2, 0)
    for i, e in enumerate(emotions):
        paste(sheet_img, ports[e], 8 + i * 168, 360 + 8)
    out = HERE / "out"
    for factor in (1, 3):
        im = Image.fromarray(upscale(sheet_img, factor)[..., :3])
        d = ImageDraw.Draw(im)
        for i, e in enumerate(emotions):
            d.text(((8 + i * 168) * factor + 4, (360 + 8 + 224 + 8) * factor - (4 if factor > 1 else 0)), e,
                   fill=(220, 220, 220))
        im.save(out / f"sheet_{factor}x{SUFFIX}.png")

    # the flipping GIF: the dialogue frame at 2x, the emotion changes in place every 0.9 s, the neutral first and last
    seq = emotions + ["neutral"]
    gif = [Image.fromarray(upscale(frames[e], 2)[..., :3]).quantize(colors=255, dither=Image.Dither.NONE) for e in seq]
    gif[0].save(out / f"flip_2x{SUFFIX}.gif", save_all=True, append_images=gif[1:], duration=900, loop=0, disposal=1)
    # and the portraits alone, in place at 3x, every 0.6 s
    solo = []
    for e in seq:
        canvas = np.zeros((224, 160, 4), np.uint8)
        canvas[...] = (*PANEL, 255)
        paste(canvas, ports[e], 0, 0)
        solo.append(Image.fromarray(upscale(canvas, 3)[..., :3]).quantize(colors=255, dither=Image.Dither.NONE))
    solo[0].save(out / f"flip_portrait_3x{SUFFIX}.gif", save_all=True, append_images=solo[1:], duration=600, loop=0, disposal=1)
    print("wrote", sorted(p.name for p in out.glob("*") if p.suffix in (".png", ".gif")))


if __name__ == "__main__":
    main()
