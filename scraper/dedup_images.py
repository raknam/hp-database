#!/usr/bin/env python3
"""
Delete <hash>.jpg files when a <hash>.webp exists — the webp is authoritative.
Run from scraper/ directory.

    py dedup_images.py          # dry run — shows what would be deleted
    py dedup_images.py --delete # actually delete
"""
import argparse
from pathlib import Path

IMAGES_DIR = Path("images")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Actually delete (default: dry run)")
    args = parser.parse_args()

    webp_stems = {p.stem for p in IMAGES_DIR.glob("*.webp")}

    to_delete = [
        IMAGES_DIR / f"{stem}.jpg"
        for stem in webp_stems
        if (IMAGES_DIR / f"{stem}.jpg").exists()
    ]

    if not to_delete:
        print("Nothing to delete.")
        return

    total = sum(p.stat().st_size for p in to_delete)
    print(f"{'Would delete' if not args.delete else 'Deleting'} {len(to_delete)} .jpg file(s) "
          f"({total / 1024 / 1024:.1f} MB freed)")

    for p in sorted(to_delete):
        print(f"  {p.name}")
        if args.delete:
            p.unlink()

    if not args.delete:
        print("\nRe-run with --delete to apply.")


if __name__ == "__main__":
    main()
