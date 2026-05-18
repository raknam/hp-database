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

BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"


class _Tee:
    """Write to both stdout and a log file simultaneously."""
    def __init__(self, log_path: Path):
        LOG_DIR.mkdir(exist_ok=True)
        self._file = log_path.open("w", encoding="utf-8")
        self._stdout = sys.stdout

    def write(self, data: str):
        self._stdout.write(data)
        self._file.write(data)

    def flush(self):
        self._stdout.flush()
        self._file.flush()

    def close(self):
        self._file.close()
        sys.stdout = self._stdout

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import NAS_ROOTS
from db.models import Base, Disc, IsoFile
from db.session import engine

SUPPORTED_EXTENSIONS = {".iso", ".mkv", ".mp4", ".mds", ".mdf"}
# Matches EPBE-5642 optionally followed by -N (disc index within edition)
CATALOG_NO_RE = re.compile(r"([A-Z]{2,6}-\d{4,6})(?:-(\d+))?", re.IGNORECASE)


def _is_mislinked(iso: IsoFile) -> bool:
    """True if a video file is linked to a CD disc — needs re-linking."""
    if not iso.disc_id:
        return False
    video_exts = {".iso", ".mkv", ".mp4", ".mds", ".mdf"}
    return Path(iso.nas_path).suffix.lower() in video_exts


def autolink_disc(session: Session, iso: IsoFile, debug: bool = False) -> None:
    filename = Path(iso.nas_path).stem
    m = CATALOG_NO_RE.search(filename)
    if not m:
        if debug:
            print(f"    [no catalog#] {filename}")
        return

    catalog_no = m.group(1).upper()
    disc_index = int(m.group(2)) - 1 if m.group(2) else None  # -1 → 0-based

    if debug:
        suffix = f" (disc index {disc_index + 1})" if disc_index is not None else ""
        print(f"    [catalog#] {filename} → {catalog_no}{suffix}")

    if disc_index is not None:
        # Find any disc with this catalog_no to get the edition, then pick the Nth disc by position
        anchor = session.execute(
            select(Disc).where(Disc.catalog_no == catalog_no)
        ).scalar_one_or_none()
        if not anchor:
            if debug:
                print(f"    [no match] {catalog_no} not found in DB")
            return
        disc = session.execute(
            select(Disc)
            .where(Disc.edition_id == anchor.edition_id)
            .order_by(Disc.sort_order)
            .offset(disc_index)
            .limit(1)
        ).scalar_one_or_none()
        if not disc:
            if debug:
                print(f"    [no match] edition {anchor.edition_id} has no disc at position {disc_index}")
            return
    else:
        disc = session.execute(
            select(Disc).where(Disc.catalog_no == catalog_no)
        ).scalar_one_or_none()
        if not disc:
            if debug:
                print(f"    [no match] {catalog_no} not found in DB")
            return

    # If matched disc is audio (CD) but file is video, prefer a video disc in same edition
    video_exts = {".iso", ".mkv", ".mp4", ".mds", ".mdf"}
    file_ext = Path(iso.nas_path).suffix.lower()
    if disc.disc_type and disc.disc_type.upper() == "CD" and file_ext in video_exts:
        video_disc = session.execute(
            select(Disc).where(
                Disc.edition_id == disc.edition_id,
                Disc.disc_type.in_(["DVD", "BD", "VHS"]),
            ).order_by(Disc.sort_order)
        ).scalars().first()
        if video_disc:
            if debug:
                print(f"    [reroute] CD→{video_disc.disc_type} (disc {video_disc.id})")
            disc = video_disc

    iso.disc_id = disc.id
    print(f"    [linked] {Path(iso.nas_path).name} → disc {disc.id} ({disc.disc_type}, {catalog_no})")


def scan_root(session: Session, root: str, seen_paths: set[str], debug: bool = False) -> int:
    root_path = Path(root)
    if not root_path.exists():
        print(f"  WARNING: root does not exist: {root}")
        return 0

    new_count = linked_count = skipped_count = 0

    for p in root_path.iterdir():
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        nas_path = str(p)
        seen_paths.add(nas_path)

        try:
            size = p.stat().st_size
            size_mb = f"{size / 1_048_576:.0f} MB" if size else "?"
        except OSError:
            size = None
            size_mb = "?"

        iso = session.execute(
            select(IsoFile).where(IsoFile.nas_path == nas_path)
        ).scalar_one_or_none()

        if not iso:
            iso = IsoFile(nas_path=nas_path)
            session.add(iso)
            is_new = True
            new_count += 1
            if debug:
                print(f"  [new]  {p.name}  ({size_mb})")
        else:
            is_new = False
            if debug:
                status = f"disc={iso.disc_id}" if iso.disc_id else "unlinked"
                print(f"  [seen] {p.name}  ({size_mb}, {status})")
            skipped_count += 1

        iso.relative_path = str(p.relative_to(root_path))
        iso.size_bytes = size
        iso.format = p.suffix.lstrip(".").lower()
        iso.last_seen_at = datetime.utcnow()
        iso.present = True

        if is_new or not iso.disc_id or _is_mislinked(iso):
            session.flush()
            before = iso.disc_id
            autolink_disc(session, iso, debug=debug)
            if iso.disc_id and not before:
                linked_count += 1

    total = new_count + skipped_count
    print(f"    {total} files — {new_count} new, {linked_count} auto-linked, {skipped_count} already known")
    return total


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
    parser.add_argument("--debug", action="store_true",
                        help="Print per-file details and catalog# matching info")
    args = parser.parse_args()

    log_path = LOG_DIR / f"scan_iso_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    tee = _Tee(log_path)
    sys.stdout = tee
    print(f"Log: {log_path}")

    try:
        _run(args)
    finally:
        tee.close()


def _run(args) -> None:
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
                n = scan_root(session, root, seen_paths, debug=args.debug)
                total += n

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

