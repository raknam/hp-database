#!/usr/bin/env python3
"""
Move images from flat images/ to aa/bb/rest hierarchy.

    py migrate_images.py          # dry-run
    py migrate_images.py --apply  # move files
"""
import argparse
from pathlib import Path

from image_path import image_subpath

IMAGES_DIR = Path("images")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually move files (default: dry-run)")
    args = parser.parse_args()

    to_move = [
        p for p in IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix in {".jpg", ".jpeg", ".webp", ".png", ".gif"}
    ]

    if not to_move:
        print("Nothing to move.")
        return

    print(f"{'Moving' if args.apply else 'Would move'} {len(to_move)} file(s)")
    for src in sorted(to_move):
        dest = IMAGES_DIR / image_subpath(src.name)
        print(f"  {src.name} -> {dest.relative_to(IMAGES_DIR)}")
        if args.apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)

    if not args.apply:
        print("\nRe-run with --apply to move.")


if __name__ == "__main__":
    main()
