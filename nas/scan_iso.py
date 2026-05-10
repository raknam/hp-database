"""Scan NAS directories for ISO/video files and index them in the database.

Usage:
    py -m nas.scan_iso --root "\\\\NAS\\hp" --root "\\\\NAS\\perfume"
    py -m nas.scan_iso --rescan-missing
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import NAS_ROOTS
from db.models import Base, Disc, IsoFile
from db.session import engine

SUPPORTED_EXTENSIONS = {".iso", ".mkv", ".mp4", ".mds", ".mdf"}
CATALOG_NO_RE = re.compile(r"([A-Z]{2,6}-\d{4,6})", re.IGNORECASE)


def autolink_disc(session: Session, iso: IsoFile) -> None:
    filename = Path(iso.nas_path).stem
    m = CATALOG_NO_RE.search(filename)
    if not m:
        return
    catalog_no = m.group(1).upper()
    disc = session.execute(
        select(Disc).where(Disc.catalog_no == catalog_no)
    ).scalar_one_or_none()
    if disc:
        iso.disc_id = disc.id
        print(f"    Auto-linked: {iso.nas_path} → disc {disc.id} ({catalog_no})")


def scan_root(session: Session, root: str, seen_paths: set[str]) -> int:
    root_path = Path(root)
    if not root_path.exists():
        print(f"  WARNING: root does not exist: {root}")
        return 0

    count = 0
    for p in root_path.rglob("*"):
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        nas_path = str(p)
        seen_paths.add(nas_path)

        try:
            size = p.stat().st_size
        except OSError:
            size = None

        iso = session.execute(
            select(IsoFile).where(IsoFile.nas_path == nas_path)
        ).scalar_one_or_none()

        if not iso:
            iso = IsoFile(nas_path=nas_path)
            session.add(iso)
            is_new = True
        else:
            is_new = False

        iso.relative_path = str(p.relative_to(root_path))
        iso.size_bytes = size
        iso.format = p.suffix.lstrip(".").lower()
        iso.last_seen_at = datetime.utcnow()
        iso.present = True

        if is_new or not iso.disc_id:
            session.flush()
            autolink_disc(session, iso)

        count += 1

    return count


def rescan_missing(session: Session) -> None:
    missing = session.execute(
        select(IsoFile).where(IsoFile.present == False)  # noqa: E712
    ).scalars().all()
    print(f"  Rechecking {len(missing)} missing files…")
    for iso in missing:
        if Path(iso.nas_path).exists():
            iso.present = True
            iso.last_seen_at = datetime.utcnow()
            print(f"    Found again: {iso.nas_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan NAS for ISO/video files")
    parser.add_argument("--root", action="append", dest="roots", metavar="PATH",
                        help="Root path(s) to scan (can be repeated)")
    parser.add_argument("--rescan-missing", action="store_true",
                        help="Recheck files previously marked as missing")
    args = parser.parse_args()

    Base.metadata.create_all(engine)

    roots = args.roots or NAS_ROOTS
    if not roots and not args.rescan_missing:
        parser.print_help()
        sys.exit(1)

    with Session(engine) as session:
        if args.rescan_missing:
            rescan_missing(session)
            session.commit()

        if roots:
            seen_paths: set[str] = set()
            total = 0
            for root in roots:
                print(f"  Scanning {root}…")
                n = scan_root(session, root, seen_paths)
                total += n
                print(f"    {n} files found.")

            # Mark files from these roots as absent if not seen this run
            all_iso = session.execute(select(IsoFile).where(IsoFile.present == True)).scalars()  # noqa: E712
            absent = 0
            for iso in all_iso:
                # Only mark absent if it was under one of the scanned roots
                under_root = any(iso.nas_path.startswith(r) for r in roots)
                if under_root and iso.nas_path not in seen_paths:
                    iso.present = False
                    absent += 1

            session.commit()
            print(f"  Total: {total} files indexed, {absent} marked absent.")

    print("Done.")


if __name__ == "__main__":
    main()
