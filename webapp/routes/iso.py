from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.models import Disc, Edition, IsoFile, Release
from db.session import get_db
from webapp.deps import templates

router = APIRouter()


@router.get("/iso")
def iso_list(
    request: Request,
    db: Session = Depends(get_db),
    orphans_only: bool = False,
):
    q = select(IsoFile).order_by(IsoFile.present.desc(), IsoFile.nas_path)
    if orphans_only:
        q = q.where(IsoFile.disc_id.is_(None))

    iso_files = db.execute(
        q.options(
            selectinload(IsoFile.disc).selectinload(Disc.edition)
            .selectinload(Edition.release).selectinload(Release.artist)
        )
    ).scalars().all()

    total = db.execute(select(func.count(IsoFile.id))).scalar() or 0
    linked = db.execute(select(func.count(IsoFile.id)).where(IsoFile.disc_id.isnot(None))).scalar() or 0
    absent = db.execute(select(func.count(IsoFile.id)).where(IsoFile.present == False)).scalar() or 0  # noqa: E712

    return templates.TemplateResponse(request, "iso.html", {
        "iso_files": iso_files,
        "orphans_only": orphans_only,
        "stats": {"total": total, "linked": linked, "orphan": total - linked, "absent": absent},
    })


@router.get("/iso/{iso_id}/open")
def iso_open(iso_id: int, db: Session = Depends(get_db)):
    iso = db.get(IsoFile, iso_id)
    if not iso:
        return RedirectResponse("/iso")
    path = iso.nas_path.replace("\\", "/").replace("!", "%21")
    vlc_url = "vlc://" + path
    return HTMLResponse(f'<meta http-equiv="refresh" content="0; url={vlc_url}">')
