"""The entry point: the CLI plus the server's launchers (`serve`, `ui`).

It sits outside the layers, so it may import both adapters; each adapter itself imports only `kiripix.commands`.
"""

from kiripix.cli import main as cli_main
from kiripix.server import LAUNCHERS


def main() -> None:
    cli_main(LAUNCHERS)
