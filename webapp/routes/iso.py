from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.models import Disc, Edition, IsoFile, Release
from sqlalchemy import delete
from db.session import get_db
from nas.scan_iso import autolink_disc
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
            .selectinload(Edition.release).selectinload(Release.artist),
            selectinload(IsoFile.disc).selectinload(Disc.edition)
            .selectinload(Edition.release).selectinload(Release.images),
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


@router.post("/iso/purge-absent")
def iso_purge_absent(db: Session = Depends(get_db)):
    result = db.execute(delete(IsoFile).where(IsoFile.present == False))  # noqa: E712
    db.commit()
    return RedirectResponse(f"/iso?msg=purged&count={result.rowcount}", status_code=303)


@router.post("/iso/autolink")
def iso_autolink(db: Session = Depends(get_db)):
    orphans = db.execute(
        select(IsoFile).where(IsoFile.disc_id.is_(None), IsoFile.present == True)  # noqa: E712
    ).scalars().all()
    linked = 0
    for iso in orphans:
        autolink_disc(db, iso)
        if iso.disc_id:
            linked += 1
    db.commit()
    return RedirectResponse(f"/iso?msg=autolink&linked={linked}&checked={len(orphans)}", status_code=303)


@router.get("/iso/{iso_id}/open")
def iso_open(iso_id: int, db: Session = Depends(get_db)):
    iso = db.get(IsoFile, iso_id)
    if not iso:
        return RedirectResponse("/iso")
    path = iso.nas_path.replace("\\", "/").replace("!", "%21")
    vlc_url = "vlc://" + path
    return HTMLResponse(f'<meta http-equiv="refresh" content="0; url={vlc_url}">')
