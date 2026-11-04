"""Ships the built UI in the wheel as `kiripix/web`, the last place `serve` looks for it.

A hook, not a plain `force-include`, because `web/dist` is a build output: `uv sync` builds Kiripix for development on
machines with no Node, which must still work, while a real wheel without the UI must not be built by accident.
"""

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class ShipTheUi(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if version == "editable":
            return
        built = Path(self.root) / "web" / "dist"
        if not (built / "index.html").is_file():
            raise FileNotFoundError(f"{built} has no built UI; run `npm ci && npm run build` in web/ first")
        build_data["force_include"][str(built)] = "kiripix/web"
