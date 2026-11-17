"""The clip table as the Commands show it: one row (`describe project`, `clips-add`) and the example that explains it."""

from pydantic import BaseModel, Field

from kiripix.core.settings import ClipSpec

CLIPS_EXAMPLE = "kiripix clips-add character.hero --clips idle,walk"


class ClipRow(BaseModel):
    name: str
    frames: int
    fps: int
    loop: bool
    foot: bool = Field(description="Whether the clip must have foot frames.")

    @classmethod
    def from_spec(cls, clip: ClipSpec) -> "ClipRow":
        return cls(name=clip.name, frames=clip.frames, fps=clip.fps, loop=clip.loop, foot=clip.foot)
