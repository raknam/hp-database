from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import NAS_ROOTS, SCRAPER_DIR
from db.models import Artist, CollectionItem, IsoFile, Release
from db.session import get_db
from webapp.deps import templates

router = APIRouter(prefix="/admin")

BASE_DIR = Path(__file__).parent.parent.parent
_GROUP_OVERRIDES_PATH = SCRAPER_DIR / "groups" / "overrides.json"


def _read_group_overrides() -> dict:
    if _GROUP_OVERRIDES_PATH.exists():
        try:
            return json.loads(_GROUP_OVERRIDES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_group_overrides(data: dict) -> None:
    _GROUP_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GROUP_OVERRIDES_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


@router.get("")
def admin_home(request: Request, db: Session = Depends(get_db)):
    iso_total = db.execute(select(func.count(IsoFile.id))).scalar() or 0
    iso_linked = db.execute(select(func.count(IsoFile.id)).where(IsoFile.disc_id.isnot(None))).scalar() or 0
    iso_absent = db.execute(select(func.count(IsoFile.id)).where(IsoFile.present == False)).scalar() or 0  # noqa: E712
    stats = {
        "releases": db.execute(select(func.count(Release.id))).scalar(),
        "artists": db.execute(select(func.count(Artist.id))).scalar(),
        "owned": db.execute(
            select(func.count(CollectionItem.id)).where(CollectionItem.owned == True)  # noqa: E712
        ).scalar(),
        "iso": iso_total,
        "iso_linked": iso_linked,
        "iso_orphan": iso_total - iso_linked,
        "iso_absent": iso_absent,
    }
    return templates.TemplateResponse(request, "admin.html", {
        "stats": stats,
        "nas_roots": NAS_ROOTS,
    })


@router.post("/import")
def trigger_import(request: Request):
    subprocess.Popen(
        [sys.executable, "-m", "importer.import_scraper", "--all"],
        cwd=str(BASE_DIR),
    )
    return RedirectResponse("/admin?msg=import_started", status_code=303)


@router.post("/scan-nas")
def trigger_scan(request: Request):
    cmd = [sys.executable, "-m", "nas.scan_iso"]
    for root in NAS_ROOTS:
        cmd += ["--root", root]
    if NAS_ROOTS:
        subprocess.Popen(cmd, cwd=str(BASE_DIR))
        return RedirectResponse("/admin?msg=scan_started", status_code=303)
    return RedirectResponse("/admin?msg=no_roots", status_code=303)


@router.get("/artists")
def admin_artists(request: Request, db: Session = Depends(get_db)):
    groups = db.execute(
        select(Artist).where(Artist.source == "hp_official", Artist.kind == "group")
    ).scalars().all()
    groups = sorted(groups, key=lambda g: (g.extra or {}).get("sort_order", 9999))
    overrides = _read_group_overrides()
    return templates.TemplateResponse(request, "admin_artists.html", {
        "groups": groups,
        "overrides": overrides,
    })


@router.post("/artists/{slug}")
def update_artist_override(
    slug: str,
    hidden: str | None = Form(None),
    display_hint: str = Form(""),
    image: str = Form(""),
    db: Session = Depends(get_db),
):
    overrides = _read_group_overrides()
    entry: dict = {}
    if hidden is not None:
        entry["hidden"] = True
    if display_hint:
        entry["display_hint"] = display_hint
    if image.strip():
        entry["image"] = image.strip()
    if entry:
        overrides[slug] = entry
    else:
        overrides.pop(slug, None)
    _write_group_overrides(overrides)
    return RedirectResponse("/admin/artists?msg=saved", status_code=303)
