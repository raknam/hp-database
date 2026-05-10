from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import NAS_ROOTS
from db.models import Artist, CollectionItem, IsoFile, Release
from db.session import get_db
from webapp.deps import templates

router = APIRouter(prefix="/admin")

BASE_DIR = Path(__file__).parent.parent.parent


@router.get("")
def admin_home(request: Request, db: Session = Depends(get_db)):
    stats = {
        "releases": db.execute(select(func.count(Release.id))).scalar(),
        "artists": db.execute(select(func.count(Artist.id))).scalar(),
        "owned": db.execute(
            select(func.count(CollectionItem.id)).where(CollectionItem.owned == True)  # noqa: E712
        ).scalar(),
        "iso": db.execute(select(func.count(IsoFile.id))).scalar(),
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
