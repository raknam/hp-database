from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

import requests as _requests
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import SCRAPER_DIR, SITE_URL
from db.models import Artist, Base, CollectionItem, IsoFile, Release
from db.session import engine, get_db
from webapp.deps import templates
from webapp.routes import admin, admin_links, artists, collection, iso, photoboard, releases, search, stats

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
app.include_router(photoboard.router)


# ---------------------------------------------------------------------------
# Images — local first, Wayback proxy+cache for CDN rotation jpgs, remote fallback
# ---------------------------------------------------------------------------
_CDN_ROTATION_RE = re.compile(r'^[0-9a-f]{40}\.(jpg|jpeg|png)$')
_MIME = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif"}


def _image_subpath(filename: str) -> Path:
    return Path(filename[:2]) / filename[2:4] / filename[4:]


@app.get("/images/{filename}")
def serve_image(filename: str):
    local = SCRAPER_DIR / "images" / _image_subpath(filename)
    if local.exists():
        mime = _MIME.get(local.suffix.lstrip("."), "image/webp")
        return FileResponse(local, media_type=mime, headers={"Cache-Control": "max-age=86400"})

    # Prefer webp over jpg when a .jpg is requested but only .webp exists
    if _CDN_ROTATION_RE.match(filename):
        stem = filename.rsplit(".", 1)[0]
        webp = SCRAPER_DIR / "images" / _image_subpath(f"{stem}.webp")
        if webp.exists():
            return FileResponse(webp, media_type="image/webp", headers={"Cache-Control": "max-age=86400"})

    # Try webp variant on live site before falling back to jpg redirect
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        stem = filename.rsplit(".", 1)[0]
        webp_remote = f"{SITE_URL}/upload/images/{stem}.webp"
        try:
            r = _requests.get(webp_remote, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                webp_local = SCRAPER_DIR / "images" / _image_subpath(f"{stem}.webp")
                webp_local.parent.mkdir(parents=True, exist_ok=True)
                webp_local.write_bytes(r.content)
                logger.info("cached %s from live site", f"{stem}.webp")
                return Response(r.content, media_type="image/webp", headers={"Cache-Control": "max-age=86400"})
        except Exception:
            pass

    # Final fallback: redirect to helloproject.com
    logger.warning("image not found locally, redirecting: %s", filename)
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
