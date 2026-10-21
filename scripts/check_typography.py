"""Enforce project typography rules across tracked repository files."""

from __future__ import annotations

import subprocess
from pathlib import Path

FORBIDDEN_SEQUENCE = bytes((0xE2, 0x80, 0x94))


def tracked_files() -> list[Path]:
    """Return all files currently tracked by Git."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return [
        Path(raw_path.decode("utf-8"))
        for raw_path in result.stdout.split(b"\0")
        if raw_path
    ]


def find_offenders() -> list[Path]:
    """Return tracked files containing the forbidden UTF-8 byte sequence."""
    offenders: list[Path] = []

    for path in tracked_files():
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            continue

        if FORBIDDEN_SEQUENCE in content:
            offenders.append(path)

    return offenders


def main() -> int:
    """Run the repository typography check."""
    offenders = find_offenders()

    if offenders:
        print("Typography check failed: forbidden punctuation found in tracked files:")
        for path in offenders:
            print(f"- {path}")
        print('Replace each occurrence with the ASCII hyphen-minus "-" character.')
        return 1

    print("Typography check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
