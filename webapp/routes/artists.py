from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from config import SCRAPER_DIR
from db.models import Artist, ArtistRelation, Release
from db.session import get_db
from webapp.deps import templates

_GROUP_OVERRIDES_PATH = SCRAPER_DIR / "groups" / "overrides.json"


def _load_group_overrides() -> dict:
    if _GROUP_OVERRIDES_PATH.exists():
        try:
            return json.loads(_GROUP_OVERRIDES_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

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
    overrides = _load_group_overrides()

    groups = db.execute(
        select(Artist)
        .where(Artist.source == "hp_official", Artist.kind == "group")
        .options(selectinload(Artist.parent_relations).selectinload(ArtistRelation.child))
    ).scalars().all()

    groups = sorted(groups, key=lambda g: (g.extra or {}).get("sort_order", 9999))

    group_data = []
    for g in groups:
        ov = overrides.get(g.slug or "", {})
        if ov.get("hidden"):
            continue

        active_ext_ids = set((g.extra or {}).get("active_member_ids", []))

        unit_rels = db.execute(
            select(ArtistRelation)
            .where(ArtistRelation.parent_id == g.id, ArtistRelation.kind == "unit")
            .options(selectinload(ArtistRelation.child))
        ).scalars().all()

        graduated: list[Artist] = []
        units = []
        for rel in unit_rels:
            all_unit_members = _resolve_members(db, rel.child_id)
            active = [m for m in all_unit_members if m.external_id in active_ext_ids]
            grad = [m for m in all_unit_members if m.external_id not in active_ext_ids]
            units.append({"unit": rel.child, "members": active})
            graduated.extend(grad)

        members = _resolve_members(db, g.id)
        unit_member_ids = {m.id for u in units for m in u["members"]} | {m.id for m in graduated}
        non_unit = [m for m in members if m.id not in unit_member_ids]
        direct_members = [m for m in non_unit if m.external_id in active_ext_ids]
        graduated.extend(m for m in non_unit if m.external_id not in active_ext_ids)

        group_data.append({
            "artist": g,
            "members": members,
            "units": units,
            "direct_members": direct_members,
            "graduated": graduated,
            "display_hint": ov.get("display_hint", ""),
            "image_override": ov.get("image", ""),
        })

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

    members: list[Artist] = []
    units: list[dict] = []
    direct_members: list[Artist] = []
    graduated: list[Artist] = []

    if artist.kind in ("group", "unit"):
        members = _resolve_members(db, artist.id)
        active_ext_ids = set((artist.extra or {}).get("active_member_ids", []))

        if active_ext_ids:
            unit_rels = db.execute(
                select(ArtistRelation)
                .where(ArtistRelation.parent_id == artist.id, ArtistRelation.kind == "unit")
                .options(selectinload(ArtistRelation.child))
            ).scalars().all()

            for rel in unit_rels:
                all_unit_members = _resolve_members(db, rel.child_id)
                active = [m for m in all_unit_members if m.external_id in active_ext_ids]
                grad = [m for m in all_unit_members if m.external_id not in active_ext_ids]
                units.append({"unit": rel.child, "members": active})
                graduated.extend(grad)

            unit_member_ids = {m.id for u in units for m in u["members"]} | {m.id for m in graduated}
            non_unit = [m for m in members if m.id not in unit_member_ids]
            direct_members = [m for m in non_unit if m.external_id in active_ext_ids]
            graduated.extend(m for m in non_unit if m.external_id not in active_ext_ids)
        else:
            direct_members = members

    # Direct parents (member → unit or group)
    direct_parents = db.execute(
        select(Artist)
        .join(ArtistRelation, ArtistRelation.parent_id == Artist.id)
        .where(ArtistRelation.child_id == artist.id, ArtistRelation.kind == "member")
        .order_by(Artist.id)
    ).scalars().all()

    # Also resolve grandparent groups (unit → group), so sub-unit members show the main group
    unit_ids = [p.id for p in direct_parents if p.kind == "unit"]
    grandparent_groups: list[Artist] = []
    if unit_ids:
        grandparent_groups = db.execute(
            select(Artist)
            .join(ArtistRelation, ArtistRelation.parent_id == Artist.id)
            .where(ArtistRelation.child_id.in_(unit_ids), ArtistRelation.kind == "unit")
            .order_by(Artist.id)
        ).scalars().all()

    seen_ids: set[int] = set()
    parent_groups: list[Artist] = []
    for g in grandparent_groups + direct_parents:
        if g.id not in seen_ids:
            seen_ids.add(g.id)
            parent_groups.append(g)

    return templates.TemplateResponse(request, "artist_detail.html", {
        "artist": artist,
        "releases": releases,
        "members": members,
        "units": units,
        "direct_members": direct_members,
        "graduated": graduated,
        "parent_groups": parent_groups,
    })
