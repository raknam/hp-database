from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import SCRAPER_DIR, SITE_URL
from db.models import Artist, Base, CollectionItem, IsoFile, Release
from db.session import engine, get_db
from webapp.deps import templates
from webapp.routes import admin, admin_links, artists, collection, iso, releases, search

app = FastAPI(title="HP Database")

# Ensure tables on startup
@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(releases.router)
app.include_router(artists.router)
app.include_router(collection.router)
app.include_router(iso.router)
app.include_router(search.router)
app.include_router(admin.router)
app.include_router(admin_links.router)


# ---------------------------------------------------------------------------
# Images — local first, remote fallback
# ---------------------------------------------------------------------------
@app.get("/images/{filename}")
def serve_image(filename: str):
    local = SCRAPER_DIR / "images" / filename
    if local.exists():
        suffix = local.suffix.lstrip(".")
        mime = {
            "webp": "image/webp",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
        }.get(suffix, "image/webp")
        return FileResponse(local, media_type=mime, headers={"Cache-Control": "max-age=86400"})
    # Redirect to remote
    remote = f"{SITE_URL}/upload/images/{filename}"
    return RedirectResponse(remote)


# ---------------------------------------------------------------------------
# Home / dashboard
# ---------------------------------------------------------------------------
@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    stats = {
        "releases": db.execute(select(func.count(Release.id))).scalar() or 0,
        "artists": db.execute(select(func.count(Artist.id))).scalar() or 0,
        "owned": db.execute(
            select(func.count(CollectionItem.id)).where(CollectionItem.owned == True)  # noqa: E712
        ).scalar() or 0,
        "iso": db.execute(
            select(func.count(IsoFile.id)).where(IsoFile.present == True)  # noqa: E712
        ).scalar() or 0,
    }

    # Latest releases
    latest = db.execute(
        select(Release)
        .order_by(Release.release_date.desc().nullslast(), Release.id.desc())
        .limit(24)
    ).scalars().all()

    return templates.TemplateResponse(request, "home.html", {
        "stats": stats,
        "latest": latest,
    })
