from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models import CollectionItem, Disc, Edition, Release
from db.session import get_db
from webapp.deps import templates

router = APIRouter()


@router.get("/collection")
def collection_view(request: Request, db: Session = Depends(get_db)):
    items = db.execute(
        select(CollectionItem)
        .where(CollectionItem.owned == True)  # noqa: E712
        .options(
            selectinload(CollectionItem.edition).selectinload(Edition.release)
            .selectinload(Release.images),
            selectinload(CollectionItem.edition).selectinload(Edition.release)
            .selectinload(Release.artist),
        )
    ).scalars().all()

    return templates.TemplateResponse(request, "collection.html", {
        "items": items,
    })


@router.post("/collection/toggle/{edition_id}")
def toggle_owned(edition_id: int, request: Request, db: Session = Depends(get_db)):
    edition = db.get(Edition, edition_id)
    if not edition:
        return HTMLResponse("", status_code=404)

    ci = db.execute(
        select(CollectionItem).where(CollectionItem.edition_id == edition_id)
    ).scalar_one_or_none()

    if not ci:
        ci = CollectionItem(edition_id=edition_id, owned=True)
        db.add(ci)
    else:
        ci.owned = not ci.owned

    db.commit()

    # Return just the button fragment for HTMX swap
    owned = ci.owned
    label = "✓ Owned" if owned else "Add to collection"
    btn_class = "owned-btn" if owned else "owned-btn not-owned"
    html = (
        f'<button class="{btn_class}" '
        f'hx-post="/collection/toggle/{edition_id}" '
        f'hx-swap="outerHTML">'
        f'{label}</button>'
    )
    return HTMLResponse(html)
