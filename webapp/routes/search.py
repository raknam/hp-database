from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from db.models import Artist, Release
from db.session import get_db
from webapp.deps import templates

router = APIRouter()


@router.get("/search")
def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    q = q.strip()
    releases: list[Release] = []
    artists: list[Artist] = []

    if q:
        like = f"%{q}%"

        releases = db.execute(
            select(Release)
            .where(
                or_(Release.title.ilike(like), Release.artist_label_raw.ilike(like))
            )
            .order_by(Release.release_date.desc().nullslast())
            .limit(100)
            .options(selectinload(Release.images), selectinload(Release.artist))
        ).scalars().all()

        artists = db.execute(
            select(Artist)
            .where(
                or_(
                    Artist.name_ja.ilike(like),
                    Artist.name_en.ilike(like),
                    Artist.name_kana.ilike(like),
                )
            )
            .limit(50)
        ).scalars().all()

    return templates.TemplateResponse(request, "search.html", {
        "q": q,
        "releases": releases,
        "artists": artists,
    })
