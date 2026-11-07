"""Command-line entry point."""

from __future__ import annotations

import argparse

from mhp3ass import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mhp3ass",
        description="Armor set search for Monster Hunter Portable 3rd.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
