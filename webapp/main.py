from __future__ import annotations

import re
from pathlib import Path

import requests as _requests
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import SCRAPER_DIR, SITE_URL
from db.models import Artist, Base, CollectionItem, IsoFile, Release
from db.session import engine, get_db
from webapp.deps import templates
from webapp.routes import admin, admin_links, artists, collection, iso, releases, search, stats

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
app.include_router(stats.router)


# ---------------------------------------------------------------------------
# Images — local first, Wayback proxy+cache for CDN rotation jpgs, remote fallback
# ---------------------------------------------------------------------------
_CDN_ROTATION_RE = re.compile(r'^[0-9a-f]{40}\.(jpg|jpeg|png)$')
_WAYBACK = "https://web.archive.org"
_MIME = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif"}


@app.get("/images/{filename}")
def serve_image(filename: str):
    local = SCRAPER_DIR / "images" / filename
    if local.exists():
        mime = _MIME.get(local.suffix.lstrip("."), "image/webp")
        return FileResponse(local, media_type=mime, headers={"Cache-Control": "max-age=86400"})

    # Prefer webp over jpg when a .jpg is requested but only .webp exists
    if _CDN_ROTATION_RE.match(filename):
        stem = filename.rsplit(".", 1)[0]
        webp = SCRAPER_DIR / "images" / f"{stem}.webp"
        if webp.exists():
            return FileResponse(webp, media_type="image/webp", headers={"Cache-Control": "max-age=86400"})

        # Proxy latest Wayback snapshot and cache locally
        cdn_url = f"http://cdn.helloproject.com/img/rotation/{filename}"
        wb_url = f"{_WAYBACK}/web/20260101000000if_/{cdn_url}"
        try:
            r = _requests.get(wb_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            local.write_bytes(r.content)
            mime = _MIME.get(filename.rsplit(".", 1)[-1], "image/jpeg")
            return Response(r.content, media_type=mime, headers={"Cache-Control": "max-age=86400"})
        except Exception:
            pass

    # Final fallback: redirect to helloproject.com
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
