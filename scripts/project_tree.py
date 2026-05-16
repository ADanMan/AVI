"""Generate a repository tree similar to the Unix `tree` command.

Usage:
    python scripts/project_tree.py [--root PATH] [--output FILE]

By default the tree is printed to stdout. Use --output to save it to a file.
Hidden files and directories are skipped by default to keep the listing tidy.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path


SKIP_NAMES = {"__pycache__", ".git"}


def iter_entries(path: Path) -> list[Path]:
    """Return sorted directory entries with folders before files."""
    entries = [
        child
        for child in path.iterdir()
        if child.name not in SKIP_NAMES and not child.name.startswith(".")
    ]
    entries.sort(key=lambda p: (p.is_file(), p.name.lower()))
    return entries


def render_tree(root: Path, buffer: io.StringIO, prefix: str = "") -> None:
    entries = iter_entries(root)
    for index, entry in enumerate(entries):
        connector = "└── " if index == len(entries) - 1 else "├── "
        buffer.write(f"{prefix}{connector}{entry.name}\n")
        if entry.is_dir():
            extension = "    " if index == len(entries) - 1 else "│   "
            render_tree(entry, buffer, prefix + extension)


def build_tree(root: Path) -> str:
    buffer = io.StringIO()
    buffer.write(f"{root.resolve().name}\n")
    render_tree(root, buffer)
    return buffer.getvalue()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Directory to summarise (default: current working directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional file to write the tree output to",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    tree_output = build_tree(root)

    if args.output:
        args.output.write_text(tree_output, encoding="utf-8")
    else:
        print(tree_output, end="")


if __name__ == "__main__":
    main()
