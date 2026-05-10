from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from db.models import Artist, CollectionItem, Disc, Edition, IsoFile, Release, Track
from db.session import get_db
from webapp.deps import templates

router = APIRouter()


@router.get("/stats")
def stats_page(request: Request, db: Session = Depends(get_db)):
    # Releases by category
    by_category = db.execute(
        select(Release.category, func.count(Release.id).label("n"))
        .where(Release.category.isnot(None))
        .group_by(Release.category)
        .order_by(func.count(Release.id).desc())
    ).all()

    # Discs by type
    by_disc_type = db.execute(
        select(Disc.disc_type, func.count(Disc.id).label("n"))
        .where(Disc.disc_type.isnot(None))
        .group_by(Disc.disc_type)
        .order_by(func.count(Disc.id).desc())
    ).all()

    # Releases by year
    by_year = db.execute(
        select(
            func.strftime("%Y", Release.release_date).label("year"),
            func.count(Release.id).label("n"),
        )
        .where(Release.release_date.isnot(None))
        .group_by(func.strftime("%Y", Release.release_date))
        .order_by(func.strftime("%Y", Release.release_date))
    ).all()

    # Top artists by release count
    top_artists = db.execute(
        select(Artist.name_ja, Artist.name_en, Artist.slug, func.count(Release.id).label("n"))
        .join(Release, Release.artist_id == Artist.id)
        .group_by(Artist.id)
        .order_by(func.count(Release.id).desc())
        .limit(15)
    ).all()

    # Totals
    total_releases = db.execute(select(func.count(Release.id))).scalar() or 0
    total_editions = db.execute(select(func.count(Edition.id))).scalar() or 0
    total_tracks = db.execute(select(func.count(Track.id))).scalar() or 0
    total_duration = db.execute(select(func.sum(Track.duration_seconds))).scalar() or 0
    total_artists = db.execute(select(func.count(Artist.id)).where(Artist.kind == "member")).scalar() or 0
    total_groups = db.execute(select(func.count(Artist.id)).where(Artist.kind == "group")).scalar() or 0
    owned = db.execute(
        select(func.count(CollectionItem.id)).where(CollectionItem.owned == True)  # noqa: E712
    ).scalar() or 0

    iso_total = db.execute(select(func.count(IsoFile.id))).scalar() or 0
    iso_linked = db.execute(select(func.count(IsoFile.id)).where(IsoFile.disc_id.isnot(None))).scalar() or 0

    hours = total_duration // 3600
    minutes = (total_duration % 3600) // 60

    return templates.TemplateResponse(request, "stats.html", {
        "by_category": by_category,
        "by_disc_type": by_disc_type,
        "by_year": by_year,
        "top_artists": top_artists,
        "totals": {
            "releases": total_releases,
            "editions": total_editions,
            "tracks": total_tracks,
            "duration_h": hours,
            "duration_m": minutes,
            "members": total_artists,
            "groups": total_groups,
            "owned": owned,
            "iso_total": iso_total,
            "iso_linked": iso_linked,
        },
    })
