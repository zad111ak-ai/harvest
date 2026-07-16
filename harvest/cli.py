"""
Harvest CLI — Universal Web Collection Engine

Thin wrapper — all logic lives in harvest/commands/.
"""

from harvest.commands import main
from harvest.commands.parser import build_parser

__all__ = ["main", "build_parser"]

if __name__ == "__main__":
    main()
