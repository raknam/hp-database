from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Artist
from db.session import get_db
from webapp.deps import templates

router = APIRouter()

BATCH = 60


def _collect_photos(db: Session) -> list[dict]:
    artists = db.execute(
        select(Artist).where(Artist.kind == "member", Artist.extra.isnot(None))
    ).scalars().all()
    photos: list[dict] = []
    for a in artists:
        for img in (a.extra or {}).get("images", []):
            url = img if isinstance(img, str) else img.get("url", "")
            if not url:
                continue
            photos.append({
                "filename": url.split("/")[-1],
                "slug": a.slug or str(a.id),
                "name": a.name_ja or a.name_en or "",
            })
    return photos


@router.get("/photoboard")
def photoboard(request: Request, db: Session = Depends(get_db)):
    photos = _collect_photos(db)
    seed = random.randint(0, 2 ** 31)
    random.Random(seed).shuffle(photos)
    return templates.TemplateResponse(request, "photoboard.html", {
        "photos": photos[:BATCH],
        "seed": seed,
        "offset": BATCH,
        "total": len(photos),
        "has_more": len(photos) > BATCH,
    })


@router.get("/photoboard/more")
def photoboard_more(request: Request, offset: int = 0, seed: int = 0,
                    db: Session = Depends(get_db)):
    photos = _collect_photos(db)
    random.Random(seed).shuffle(photos)
    batch = photos[offset:offset + BATCH]
    return templates.TemplateResponse(request, "photoboard_more.html", {
        "photos": batch,
        "seed": seed,
        "offset": offset + BATCH,
        "has_more": offset + BATCH < len(photos),
    })
