from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from db.models import Artist, CollectionItem, Disc, Edition, IsoFile, Release, ReleaseGroup, ReleaseGroupMember, ReleaseImage
from db.session import get_db
from webapp.deps import templates

router = APIRouter()


@router.get("/releases")
def releases_list(
    request: Request,
    db: Session = Depends(get_db),
    year: str | None = None,
    category: str | None = None,
    artist: str | None = None,
    owned: bool = False,
    expand_links: bool = False,
    page: int = 1,
    hx_request: str | None = None,
):
    PAGE_SIZE = 60

    q = select(Release).order_by(Release.release_date.desc().nullslast(), Release.id.desc())

    year_int = int(year) if year else None
    if year_int:
        from sqlalchemy import extract
        q = q.where(extract("year", Release.release_date) == year_int)
    if category:
        q = q.where(Release.release_type == category)
    if artist:
        q = q.join(Artist, Release.artist_id == Artist.id).where(
            (Artist.name_ja == artist) | (Artist.name_en == artist)
        )
    if owned:
        q = (
            q.join(Edition, Edition.release_id == Release.id)
            .join(CollectionItem, CollectionItem.edition_id == Edition.id)
            .where(CollectionItem.owned == True)  # noqa: E712
            .distinct()
        )

    if not expand_links:
        RGM1 = aliased(ReleaseGroupMember, name="rgm1")
        RGM2 = aliased(ReleaseGroupMember, name="rgm2")
        has_primary = exists(
            select(RGM2.id).where(
                RGM2.group_id == RGM1.group_id,
                RGM2.is_primary == True,  # noqa: E712
            )
        )
        non_rep = (
            select(RGM1.release_id)
            .where(
                or_(
                    # not primary but a primary exists in the group
                    and_(RGM1.is_primary == False, has_primary),  # noqa: E712
                    # no primary in group but a lower-id member exists
                    and_(
                        ~has_primary,
                        exists(
                            select(RGM2.id).where(
                                RGM2.group_id == RGM1.group_id,
                                RGM2.id < RGM1.id,
                            )
                        ),
                    ),
                )
            )
        ).subquery()
        q = q.where(Release.id.not_in(select(non_rep.c.release_id)))

    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    releases = db.execute(
        q.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
        .options(
            selectinload(Release.images),
            selectinload(Release.artist),
            selectinload(Release.group_member)
                .selectinload(ReleaseGroupMember.group)
                .selectinload(ReleaseGroup.members)
                .selectinload(ReleaseGroupMember.release)
                .selectinload(Release.images),
        )
    ).scalars().all()

    # Available filter values
    categories = [
        r[0] for r in db.execute(
            select(Release.release_type).distinct().where(Release.release_type.isnot(None)).order_by(Release.release_type)
        ).all()
    ]
    years = [
        r[0] for r in db.execute(
            select(func.strftime("%Y", Release.release_date))
            .where(Release.release_date.isnot(None))
            .distinct()
            .order_by(func.strftime("%Y", Release.release_date).desc())
        ).all()
        if r[0]
    ]

    ctx = {
        "releases": releases,
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "pages": (total + PAGE_SIZE - 1) // PAGE_SIZE,
        "filter_year": year_int,
        "filter_category": category,
        "filter_artist": artist,
        "filter_owned": owned,
        "filter_expand_links": expand_links,
        "categories": categories,
        "years": years,
    }
    is_htmx = request.headers.get("HX-Request")
    template = "releases_partial.html" if is_htmx else "releases.html"
    return templates.TemplateResponse(request, template, ctx)


@router.get("/release/{release_id}")
def release_detail(request: Request, release_id: int, db: Session = Depends(get_db)):
    _opts = [
        selectinload(Release.artist),
        selectinload(Release.images),
        selectinload(Release.editions).selectinload(Edition.discs).selectinload(Disc.tracks),
        selectinload(Release.editions).selectinload(Edition.discs).selectinload(Disc.iso_files),
        selectinload(Release.editions).selectinload(Edition.collection_item),
        selectinload(Release.group_member).selectinload(ReleaseGroupMember.group)
            .selectinload(ReleaseGroup.members).selectinload(ReleaseGroupMember.release)
            .selectinload(Release.images),
    ]
    release = db.execute(
        select(Release).where(Release.id == release_id).options(*_opts)
    ).scalar_one_or_none()

    if not release:
        release = db.execute(
            select(Release).where(Release.external_id == str(release_id)).options(*_opts)
        ).scalar_one_or_none()

    if not release:
        return templates.TemplateResponse(request, "404.html", {}, status_code=404)

    return templates.TemplateResponse(request, "release_detail.html", {
        "release": release,
    })
