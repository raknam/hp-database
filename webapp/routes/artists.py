from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.models import Artist, ArtistRelation, Release
from db.session import get_db
from webapp.deps import templates

router = APIRouter()


def _resolve_members(session: Session, artist_id: int, depth: int = 0) -> list[Artist]:
    if depth > 2:
        return []
    result = []
    rels = session.execute(
        select(ArtistRelation)
        .where(ArtistRelation.parent_id == artist_id)
        .options(selectinload(ArtistRelation.child))
    ).scalars().all()
    for rel in rels:
        if rel.kind == "member":
            result.append(rel.child)
        elif rel.kind == "unit":
            result.extend(_resolve_members(session, rel.child_id, depth + 1))
    return result


@router.get("/artists")
def artists_list(request: Request, db: Session = Depends(get_db)):
    # Groups only, with their members
    groups = db.execute(
        select(Artist)
        .where(Artist.source == "hp_official", Artist.kind == "group")
        .options(selectinload(Artist.parent_relations).selectinload(ArtistRelation.child))
    ).scalars().all()

    # Sort by the artistOrder stored in extra.sort_order
    groups = sorted(groups, key=lambda g: (g.extra or {}).get("sort_order", 9999))

    group_data = []
    for g in groups:
        members = _resolve_members(db, g.id)
        group_data.append({"artist": g, "members": members})

    return templates.TemplateResponse(request, "artists.html", {
        "groups": group_data,
    })


@router.get("/artists/{slug}")
def artist_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    artist = db.execute(
        select(Artist).where(Artist.slug == slug)
    ).scalar_one_or_none()

    if not artist:
        return templates.TemplateResponse(request, "404.html", {}, status_code=404)

    releases = db.execute(
        select(Release)
        .where(Release.artist_id == artist.id)
        .order_by(Release.release_date.desc().nullslast())
        .options(selectinload(Release.images))
    ).scalars().all()

    members = _resolve_members(db, artist.id) if artist.kind in ("group", "unit") else []

    parent_groups = db.execute(
        select(Artist)
        .join(ArtistRelation, ArtistRelation.parent_id == Artist.id)
        .where(ArtistRelation.child_id == artist.id, ArtistRelation.kind == "member")
        .order_by(Artist.id)
    ).scalars().all()

    return templates.TemplateResponse(request, "artist_detail.html", {
        "artist": artist,
        "releases": releases,
        "members": members,
        "parent_groups": parent_groups,
    })
