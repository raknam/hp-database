"""
Backfill missing `ts` fields in members/*.json images.

Priority:
  1. Extract from Wayback URL  (web/<14-digit-ts>if_/)
  2. Fallback: version timestamp from releases/version.json

Usage:
    py backfill_image_ts.py          # dry-run
    py backfill_image_ts.py --write  # apply changes
    py backfill_image_ts.py --check  # report images still missing ts after write
"""
import json
import re
import sys
from pathlib import Path

MEMBERS_DIR = Path("members")
WAYBACK_RE  = re.compile(r"/web/(\d{14})if_/")

write = "--write" in sys.argv
check = "--check" in sys.argv


def _version_ts() -> str | None:
    vf = Path("releases/version.json")
    if not vf.exists():
        return None
    v = json.loads(vf.read_text(encoding="utf-8")).get("version", "")
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})-\w+", v)
    return f"20{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}{m.group(5)}00" if m else None


def _ts_for(url: str, fallback: str | None) -> str | None:
    m = WAYBACK_RE.search(url)
    return m.group(1) if m else fallback


fallback_ts = _version_ts()
print(f"Fallback version ts: {fallback_ts}")

files_changed = 0
images_fixed  = 0
still_missing: list[tuple[str, str]] = []

for f in sorted(MEMBERS_DIR.glob("*.json")):
    if not re.fullmatch(r"\d+", f.stem):
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    images = data.get("images")
    if not images:
        continue

    changed    = False
    new_images = []
    for img in images:
        obj = {"url": img} if isinstance(img, str) else dict(img)
        if not obj.get("ts"):
            ts = _ts_for(obj.get("url", ""), fallback_ts)
            if ts:
                obj["ts"] = ts
                changed = True
                images_fixed += 1
            elif check:
                still_missing.append((f.name, obj.get("url", "")[-60:]))
        new_images.append(obj)

    if changed:
        files_changed += 1
        if write:
            data["images"] = new_images
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            fixed = sum(1 for o in new_images if o.get("ts"))
            print(f"  {f.name}: {fixed}/{len(new_images)} images would get ts")

mode = "Written" if write else "Would fix"
print(f"\n{mode}: {images_fixed} images in {files_changed} files")

if check:
    if still_missing:
        print(f"\nImages still without ts: {len(still_missing)}")
        for fname, url in still_missing[:20]:
            print(f"  {fname}: ...{url}")
    else:
        print("\nAll images now have ts.")
