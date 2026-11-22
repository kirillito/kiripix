"""The names of the files that go out to be painted and come back (ticket 0349), in one place for `to-paint`, which writes
them, and `inbox` (ticket 0350), which files what comes back (`inbox.parse` reads the names).

A room's image comes back as `<room>.png` (its Source), a side piece of a room mid-`extend` as `<room>.<side>.png`, where
`<room>` is the Asset's name without its Kind prefix. What goes out is numbered in the order to paint:
`<nn>-<room>.prompt.txt` and `<nn>-<room>.<side>.png` (the canvas).
"""

from kiripix.core.assets import Asset

INDEX = "index.md"
PROMPT_SUFFIX = ".prompt.txt"
SIDES = ("east", "south", "west", "north")


def return_name(asset: Asset, sides: list[str] | None = None) -> str:
    """The name the image made for `asset` comes back under; `sides` for a piece of a room mid-`extend`."""
    return f"{asset.name}.png" if not sides else f"{asset.name}.{'+'.join(sides)}.png"


def prompt_name(number: int, asset: Asset) -> str:
    return f"{number:02d}-{asset.name}{PROMPT_SUFFIX}"


def canvas_name(number: int, asset: Asset, sides: list[str]) -> str:
    return f"{number:02d}-{asset.name}.{'+'.join(sides)}.png"
