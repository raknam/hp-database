from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
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

    return templates.TemplateResponse(request, "iso.html", {
        "iso_files": iso_files,
        "orphans_only": orphans_only,
    })


@router.get("/iso/{iso_id}/open")
def iso_open(iso_id: int, db: Session = Depends(get_db)):
    iso = db.get(IsoFile, iso_id)
    if not iso:
        return RedirectResponse("/iso")
    # Open as file:// URL (works for local desktop use)
    file_url = "file:///" + iso.nas_path.replace("\\", "/")
    return RedirectResponse(file_url)
