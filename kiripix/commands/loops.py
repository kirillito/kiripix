"""`loop kit` (ticket 0193): a folder to paint a frame Loop's frames in. `import --loop` takes them back."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import loopkit
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.project import find_project

LOOP_GROUP = "A room's Loops: parts that play by themselves, over and over."


class KitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The room's Asset ID, such as room.queen_west_alley.")
    loop: str = Field(description="The frame Loop's ID (a `loop` Decision of the loops Stage with form frames, and a region).")
    folder: Path = Field(description="Where to write the kit: frame_000.png ... frame_<N-1>.png, palette.gpl, palette.png, "
                                     "README.txt and kit.json.")
    frames: int = Field(4, description=f"How many frames the Loop has, 2 to {loopkit.MAX_FRAMES}: frame 0 is the room's, "
                                       "the others are copies of it to paint on.")
    force: bool = Field(False, description="Write over the frames already in the folder, painted ones too.")


class KitData(BaseModel):
    asset: str
    loop: str
    folder: str
    box: list[int] = Field(description="The region's box [x, y, width, height] in target px: the size of every frame.")
    frames: int
    colours: int = Field(description="How many colours the palette has.")
    files: list[str] = Field(description="The files written, in the folder.")

    def text(self) -> str:
        x, y, width, height = self.box
        return (f"{self.asset}: wrote the kit of Loop {self.loop} to {self.folder}: {self.frames} frames of "
                f"{width}x{height} px (the room at {x}, {y}); paint frame_001 onward, then "
                f"kiripix import {self.asset} {self.folder}/frame_001.png ... --loop {self.loop}")


def _lock(arguments: KitInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


@command(
    "loop kit",
    summary="Write a frame Loop's kit to a folder: frame_000.png (the room inside the Loop's region, at target size, "
            "transparent outside it), copies of it to paint on, the palette (palette.gpl, palette.png) and a README. "
            "Refused when the folder already has frames, unless --force. Import the painted frames with "
            "`import --loop`.",
    input=KitInput,
    output=KitData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "loop", "folder")),
    locks=LockNeeds(asset=_lock),
    group_summary=LOOP_GROUP,
)
def loop_kit(arguments: KitInput, context: Context) -> Outcome[KitData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    written = loopkit.write_kit(project, asset, arguments.loop, context.cwd / arguments.folder, str(arguments.folder),
                                arguments.frames, arguments.force)
    return Outcome(KitData(asset=asset.id, loop=arguments.loop, folder=str(arguments.folder), box=list(written.box),
                           frames=written.frames, colours=written.colours, files=written.files))
