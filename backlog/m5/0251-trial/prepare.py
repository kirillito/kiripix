"""Ticket 0251, step 2a: turn the image model's pictures into clean Sources at exactly 3 source px per game px.

Kiripix's `fit` downscales at one integer scale, so each Source is resampled here first so that its walls and floor
land on whole 16 px tiles at scale 3 (48 source px a tile). The output goes to `work/src_*.png`; `fit` and `palette`
then run in a scratch copy of the art Project (see README.md).

- grid4 (a room): cut on its own wall lines into a 9-slice, each band resampled to whole tiles: left and right walls
  2 tiles, top wall 3 tiles (its face shows), bottom wall 2 tiles, floor 16 x 15 tiles. 20 x 20 tiles in all.
- grid5 (a junction): its wall bands are about 95 px wide, as grid4's, so it is resampled whole, 1024 -> 960 (20 x 20).
- grid2 (a sheet): the floor row's 4 cells, cut between the magenta lines and resampled to 1 tile each.
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
IN = HERE / "input"
WORK = HERE / "work"
T = 48  # source px per 16 px tile at scale 3

# grid4's wall lines, measured on brightness profiles (source px): outer wall edge, floor edge
G4_X = [32, 125, 895, 990]
G4_Y = [32, 170, 896, 990]
G4_TX = [2, 16, 2]  # tiles per band, left to right
G4_TY = [3, 15, 2]  # top to bottom

# grid2's floor row, between the magenta lines (measured)
G2_X = [(0, 221), (225, 446), (450, 671), (675, 896)]
G2_Y = (2, 223)


def slice9(im: Image.Image, xs: list[int], ys: list[int], tx: list[int], ty: list[int]) -> Image.Image:
    out = Image.new("RGB", (sum(tx) * T, sum(ty) * T))
    oy = 0
    for j in range(3):
        ox = 0
        for i in range(3):
            box = (xs[i], ys[j], xs[i + 1], ys[j + 1])
            piece = im.crop(box).resize((tx[i] * T, ty[j] * T), Image.Resampling.LANCZOS)
            out.paste(piece, (ox, oy))
            ox += tx[i] * T
        oy += ty[j] * T
    return out


def main() -> None:
    WORK.mkdir(exist_ok=True)
    g4 = Image.open(IN / "grid4.jpg").convert("RGB")
    slice9(g4, G4_X, G4_Y, G4_TX, G4_TY).save(WORK / "src_g4.png")

    g5 = Image.open(IN / "grid5.jpg").convert("RGB")
    g5.resize((20 * T, 20 * T), Image.Resampling.LANCZOS).save(WORK / "src_g5.png")

    g2 = Image.open(IN / "grid2.jpg").convert("RGB")
    floor = Image.new("RGB", (4 * T, T))
    for i, (x0, x1) in enumerate(G2_X):
        floor.paste(g2.crop((x0, G2_Y[0], x1, G2_Y[1])).resize((T, T), Image.Resampling.LANCZOS), (i * T, 0))
    floor.save(WORK / "src_g2floor.png")
    print("wrote", sorted(p.name for p in WORK.glob("src_*.png")))


if __name__ == "__main__":
    main()
