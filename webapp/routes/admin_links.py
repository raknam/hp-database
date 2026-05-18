from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.models import Release, ReleaseGroup, ReleaseGroupDismissal, ReleaseGroupMember
from db.session import get_db
from webapp.deps import templates

router = APIRouter(prefix="/admin/links")


def _proposals(db: Session, same_date: bool = True) -> list[list[Release]]:
    linked_ids = {
        row[0] for row in db.execute(select(ReleaseGroupMember.release_id)).all()
    }
    dismissed_keys = {
        row[0] for row in db.execute(select(ReleaseGroupDismissal.release_ids_key)).all()
    }

    if same_date:
        subq = (
            select(Release.title, Release.artist_id, Release.release_date)
            .where(Release.artist_id.isnot(None), Release.release_date.isnot(None))
            .group_by(Release.title, Release.artist_id, Release.release_date)
            .having(func.count() > 1)
            .subquery()
        )
        candidates = db.execute(
            select(Release)
            .join(subq, (Release.title == subq.c.title)
                  & (Release.artist_id == subq.c.artist_id)
                  & (Release.release_date == subq.c.release_date))
            .where(Release.id.notin_(linked_ids) if linked_ids else True)
            .options(selectinload(Release.images), selectinload(Release.artist))
            .order_by(Release.title, Release.release_date, Release.id)
        ).scalars().all()
        cluster_key = lambda r: (r.title, r.artist_id, r.release_date)
    else:
        subq = (
            select(Release.title, Release.artist_id)
            .where(Release.artist_id.isnot(None))
            .group_by(Release.title, Release.artist_id)
            .having(func.count() > 1)
            .subquery()
        )
        candidates = db.execute(
            select(Release)
            .join(subq, (Release.title == subq.c.title)
                  & (Release.artist_id == subq.c.artist_id))
            .where(Release.id.notin_(linked_ids) if linked_ids else True)
            .options(selectinload(Release.images), selectinload(Release.artist))
            .order_by(Release.title, Release.artist_id, Release.release_date, Release.id)
        ).scalars().all()
        cluster_key = lambda r: (r.title, r.artist_id)

    clusters: dict[tuple, list[Release]] = {}
    for r in candidates:
        clusters.setdefault(cluster_key(r), []).append(r)

    result = []
    for releases in clusters.values():
        key = ",".join(str(r.id) for r in sorted(releases, key=lambda x: x.id))
        if key not in dismissed_keys and len(releases) > 1:
            result.append(releases)
    result.sort(key=lambda rs: max(r.release_date for r in rs if r.release_date) if any(r.release_date for r in rs) else "0", reverse=True)
    return result


@router.get("")
def links_home(request: Request, same_date: bool = True, db: Session = Depends(get_db)):
    proposals = _proposals(db, same_date=same_date)
    links = db.execute(
        select(ReleaseGroup)
        .options(selectinload(ReleaseGroup.members).selectinload(ReleaseGroupMember.release)
                 .selectinload(Release.images))
        .order_by(ReleaseGroup.created_at.desc())
    ).scalars().all()
    dismissals = db.execute(
        select(ReleaseGroupDismissal).order_by(ReleaseGroupDismissal.dismissed_at.desc())
    ).scalars().all()
    dismissals_rich = []
    for d in dismissals:
        ids = [int(i) for i in d.release_ids_key.split(",")]
        releases = db.execute(
            select(Release).where(Release.id.in_(ids)).options(selectinload(Release.images))
        ).scalars().all()
        dismissals_rich.append({"dismissal": d, "releases": releases})
    return templates.TemplateResponse(request, "admin_links.html", {
        "proposals": proposals,
        "links": links,
        "dismissals": dismissals_rich,
        "same_date": same_date,
    })


def _create_link(db: Session, ids: list[int], labels: dict[str, str], primary_id: int) -> None:
    link = ReleaseGroup()
    db.add(link)
    db.flush()
    for rid in ids:
        db.add(ReleaseGroupMember(
            group_id=link.id,
            release_id=rid,
            format_label=labels.get(str(rid), ""),
            is_primary=(rid == primary_id),
        ))
    db.commit()


@router.post("/confirm")
def confirm_proposal(
    request: Request,
    release_ids: str = Form(...),
    format_labels: str = Form(...),
    primary_id: int = Form(...),
    same_date: int = Form(0),
    db: Session = Depends(get_db),
):
    ids = [int(i) for i in release_ids.split(",")]
    labels = dict(zip([str(i) for i in ids], format_labels.split(",")))
    _create_link(db, ids, labels, primary_id)
    return RedirectResponse(f"/admin/links?same_date={same_date}", status_code=303)


@router.post("/manual")
def manual_link(
    release_ids_raw: str = Form(...),
    same_date: int = Form(0),
    db: Session = Depends(get_db),
):
    ids = [int(i) for i in re.split(r"[\s,]+", release_ids_raw.strip()) if i.isdigit()]
    if len(ids) < 2:
        return RedirectResponse(f"/admin/links?same_date={same_date}&error=need_2", status_code=303)
    releases = db.execute(
        select(Release).where(Release.id.in_(ids))
        .options(selectinload(Release.group_member))
    ).scalars().all()
    ids = [r.id for r in releases if not r.group_member]
    if len(ids) < 2:
        return RedirectResponse(f"/admin/links?same_date={same_date}&error=already_linked", status_code=303)
    labels = {str(r.id): (r.release_type or "") for r in releases}
    _create_link(db, ids, labels, ids[0])
    return RedirectResponse(f"/admin/links?same_date={same_date}", status_code=303)


@router.post("/dismiss")
def dismiss_proposal(
    release_ids: str = Form(...),
    same_date: int = Form(0),
    db: Session = Depends(get_db),
):
    key = ",".join(str(i) for i in sorted(int(i) for i in release_ids.split(",")))
    if not db.execute(
        select(ReleaseGroupDismissal).where(ReleaseGroupDismissal.release_ids_key == key)
    ).scalar_one_or_none():
        db.add(ReleaseGroupDismissal(release_ids_key=key))
        db.commit()
    return RedirectResponse(f"/admin/links?same_date={same_date}", status_code=303)


@router.post("/dismissal/{dismissal_id}/restore")
def restore_dismissal(dismissal_id: int, request: Request, db: Session = Depends(get_db)):
    d = db.get(ReleaseGroupDismissal, dismissal_id)
    if d:
        db.delete(d)
        db.commit()
    same_date = request.query_params.get("same_date", "0")
    return RedirectResponse(f"/admin/links?same_date={same_date}", status_code=303)


@router.post("/{link_id}/delete")
def delete_link(link_id: int, request: Request, db: Session = Depends(get_db)):
    link = db.get(ReleaseGroup, link_id)
    if link:
        db.delete(link)
        db.commit()
    same_date = request.query_params.get("same_date", "0")
    return RedirectResponse(f"/admin/links?same_date={same_date}", status_code=303)
