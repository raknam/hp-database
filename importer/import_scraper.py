"""Import scraper JSON data into the database.

Usage:
    py -m importer.import_scraper --all
    py -m importer.import_scraper --releases
    py -m importer.import_scraper --members
    py -m importer.import_scraper --release 7506
    py -m importer.import_scraper --year 2025
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import SCRAPER_DIR
from db.models import (
    Artist, ArtistRelation, Base, CollectionItem, Disc, Edition,
    Release, ReleaseImage, Song, Track, TrackCredit,
)
from db.session import engine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


_barcodes: dict[str, dict] | None = None


def load_barcodes() -> dict[str, dict]:
    global _barcodes
    if _barcodes is None:
        path = SCRAPER_DIR / "releases" / "barcodes.json"
        data = load_json(path)
        _barcodes = data if isinstance(data, dict) else {}
    return _barcodes


def lookup_jan(catalog_no: str | None) -> str | None:
    if not catalog_no:
        return None
    return load_barcodes().get(catalog_no, {}).get("jan")


def parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    raw = raw.strip()
    # "2025.10.8" or "2025.10.08"
    m = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # "1998-12-12"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    # "1999年3月12日"
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def parse_price(raw: str | None) -> int | None:
    if not raw:
        return None
    # Match the first ￥XXXX,XXX pattern (outermost price)
    m = re.search(r"[¥￥]([\d,]+)", raw)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def parse_duration(raw: str | None) -> int | None:
    if not raw:
        return None
    m = re.fullmatch(r"(\d+):(\d{2})", raw.strip())
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def profile_name(profile: dict, fallback: str = "") -> str:
    return profile.get("nameJa") or profile.get("nameEn") or profile.get("slug") or fallback


# ---------------------------------------------------------------------------
# Artists
# ---------------------------------------------------------------------------

def import_artists(session: Session, artist_list: dict) -> dict[str, int]:
    """Import artists from artist_list.json. Returns {name -> db_id} map."""
    artists_by_id = artist_list.get("artistsById", {})
    profiles_by_id = artist_list.get("profilesById", {})
    relations = artist_list.get("artistRelation", {})
    artist_order = [str(i) for i in artist_list.get("artistOrder", [])]

    print(f"  Importing {len(artists_by_id)} artists…")

    def _parse_version_ts(version: str) -> str | None:
        m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})-\w+", version)
        if m:
            yy, mo, dd, hh, mi = m.groups()
            return f"20{yy}{mo}{dd}{hh}{mi}00"
        return None

    version_data = load_json(SCRAPER_DIR / "releases" / "version.json") or {}
    import_ts = (
        _parse_version_ts(version_data.get("version", ""))
        or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    )
    print(f"  Site version timestamp: {import_ts}")

    def _extract_profile_detail(profile: dict) -> tuple[dict, dict]:
        """Parse profile['detail'] → (color_dict, details_dict) for extra storage."""
        color: dict = {}
        details: dict = {}
        for entry in profile.get("detail", []):
            if not isinstance(entry, dict):
                continue
            label = entry.get("label", "")
            if "color" in entry:
                c = entry["color"]
                color = {"name": c.get("name", ""), "hex": c.get("code", c.get("hex", ""))}
            elif "value" in entry:
                v = entry["value"]
                if isinstance(v, dict):
                    details[label] = v.get("content", "")
                elif isinstance(v, str):
                    details[label] = v
        return color, details

    def _extract_image_urls(profile: dict) -> list[dict]:
        """Normalize profilesById image dict → flat list of {"url": ..., "ts": ...} dicts."""
        imgs = profile.get("images", {})
        if isinstance(imgs, list):
            return [{"url": u, "ts": import_ts} for u in imgs if isinstance(u, str)]
        urls: list[str] = []
        for item in imgs.get("profile", []):
            if isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
        thumb = imgs.get("thumbnail", {})
        if isinstance(thumb, dict) and thumb.get("url"):
            urls.append(thumb["url"])
        return [{"url": u, "ts": import_ts} for u in urls]

    # Upsert all artists
    for ext_id, artist_data in artists_by_id.items():
        ext_id = str(ext_id)
        profile = profiles_by_id.get(ext_id, {})

        artist_type = artist_data.get("artistType", "")
        kind = "group" if artist_type == "group" else "member"
        slug = artist_data.get("slug") or profile.get("slug")
        sort_order = artist_order.index(ext_id) if ext_id in artist_order else 9999

        artist = session.execute(
            select(Artist).where(Artist.source == "hp_official", Artist.external_id == ext_id)
        ).scalar_one_or_none()

        if not artist:
            artist = Artist(source="hp_official", external_id=ext_id)
            session.add(artist)

        artist.slug = slug
        artist.kind = kind
        artist.name_ja = profile.get("nameJa")
        artist.name_en = profile.get("nameEn")
        artist.name_kana = profile.get("nameKana")
        artist.updated_at = datetime.now(timezone.utc)

        image_urls = _extract_image_urls(profile)
        color, details = _extract_profile_detail(profile)
        extra = dict(artist.extra or {})
        extra["images"] = image_urls
        extra["sort_order"] = sort_order
        if color:
            extra["color"] = color
        if details:
            extra["details"] = details
        artist.extra = extra

    # Also import profiles not in artistsById (sub-units, etc.)
    for ext_id, profile in profiles_by_id.items():
        ext_id = str(ext_id)
        if ext_id in artists_by_id:
            continue
        # Determine kind: if it appears as a unit in relations, it's a unit
        is_unit = any(
            any(str(e.get("id")) == ext_id and e.get("kind") == "unit"
                for e in entries)
            for entries in relations.values()
        )
        kind = "unit" if is_unit else "member"

        artist = session.execute(
            select(Artist).where(Artist.source == "hp_official", Artist.external_id == ext_id)
        ).scalar_one_or_none()

        if not artist:
            artist = Artist(source="hp_official", external_id=ext_id)
            session.add(artist)

        artist.kind = kind
        artist.slug = profile.get("slug") or None
        artist.name_ja = profile.get("nameJa")
        artist.name_en = profile.get("nameEn")
        artist.name_kana = profile.get("nameKana")
        artist.updated_at = datetime.now(timezone.utc)

        image_urls = _extract_image_urls(profile)
        color, details = _extract_profile_detail(profile)
        extra = dict(artist.extra or {})
        if image_urls:
            extra["images"] = image_urls
        if color:
            extra["color"] = color
        if details:
            extra["details"] = details
        if kind == "member":
            extra["has_grad"] = False
        artist.extra = extra or None

    session.flush()

    # Upsert relations
    for group_id, entries in relations.items():
        group_id = str(group_id)
        parent = session.execute(
            select(Artist).where(Artist.source == "hp_official", Artist.external_id == group_id)
        ).scalar_one_or_none()
        if not parent:
            continue

        for entry in entries:
            child_id = str(entry.get("id"))
            kind = entry.get("kind", "member")

            child = session.execute(
                select(Artist).where(Artist.source == "hp_official", Artist.external_id == child_id)
            ).scalar_one_or_none()
            if not child:
                continue

            rel = session.execute(
                select(ArtistRelation).where(
                    ArtistRelation.parent_id == parent.id,
                    ArtistRelation.child_id == child.id,
                )
            ).scalar_one_or_none()
            if not rel:
                rel = ArtistRelation(parent_id=parent.id, child_id=child.id, kind=kind)
                session.add(rel)
            else:
                rel.kind = kind

    # Store active member external_ids per group (resolved recursively through sub-units)
    def _active_member_ids(group_ext_id: str, depth: int = 0) -> list[str]:
        if depth > 2:
            return []
        ids: list[str] = []
        for entry in relations.get(group_ext_id, []):
            eid = str(entry.get("id"))
            if entry.get("kind") == "member":
                ids.append(eid)
            elif entry.get("kind") == "unit":
                ids.extend(_active_member_ids(eid, depth + 1))
        return ids

    for group_ext_id in relations:
        group_ext_id = str(group_ext_id)
        group_artist = session.execute(
            select(Artist).where(Artist.source == "hp_official", Artist.external_id == group_ext_id)
        ).scalar_one_or_none()
        if not group_artist or group_artist.kind != "group":
            continue
        active_ids = _active_member_ids(group_ext_id)
        extra = dict(group_artist.extra or {})
        extra["active_member_ids"] = active_ids
        group_artist.extra = extra

    session.commit()
    print(f"  Artists committed.")

    # Build name -> artist map for release linking
    name_map: dict[str, int] = {}
    for artist in session.execute(select(Artist).where(Artist.source == "hp_official")).scalars():
        for name in [artist.name_ja, artist.name_en]:
            if name:
                name_map[name] = artist.id
    return name_map


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

def import_members(session: Session) -> None:
    members_dir = SCRAPER_DIR / "members"
    if not members_dir.exists():
        print("  No members/ dir found, skipping.")
        return

    files = list(members_dir.glob("*.json"))
    print(f"  Importing {len(files)} member files…")

    # Cache group lookup by slug to avoid repeated queries
    _group_cache: dict[str, Artist] = {}

    _VIRTUAL_GROUP_NAMES: dict[str, tuple[str | None, str | None]] = {
        "upfront": ("アップフロントワークス", "Up-Front Works"),
    }

    def _get_or_create_group(slug: str) -> Artist | None:
        if slug in _group_cache:
            return _group_cache[slug]
        group = session.execute(
            select(Artist).where(Artist.slug == slug, Artist.kind == "group")
        ).scalar_one_or_none()
        if not group:
            name_ja, name_en = _VIRTUAL_GROUP_NAMES.get(slug, (None, None))
            group = Artist(source="hp_official", slug=slug, kind="group",
                           name_ja=name_ja, name_en=name_en)
            session.add(group)
            session.flush()
        _group_cache[slug] = group
        return group

    for json_file in sorted(files):
        if not re.fullmatch(r"\d+", json_file.stem):
            continue
        data = load_json(json_file)
        if not data:
            continue

        ext_id = str(json_file.stem)
        is_synthetic = int(json_file.stem) >= 800000

        artist = session.execute(
            select(Artist).where(Artist.source == "hp_official", Artist.external_id == ext_id)
        ).scalar_one_or_none()

        enrichment_only = False
        if not artist and is_synthetic and data.get("slug"):
            # Match a member already imported with an official ID — enrich only, don't downgrade
            artist = session.execute(
                select(Artist).where(Artist.slug == data["slug"])
            ).scalar_one_or_none()
            if artist:
                enrichment_only = True

        if not artist:
            artist = Artist(source="hp_official", external_id=ext_id, kind="member")
            session.add(artist)

        if data.get("nameJa"):
            artist.name_ja = data["nameJa"]
        if data.get("nameEn") and not artist.name_en:
            artist.name_en = data["nameEn"]
        if data.get("nameKana") and not artist.name_kana:
            artist.name_kana = data["nameKana"]
        if not artist.slug and data.get("slug"):
            artist.slug = data["slug"]
        artist.updated_at = datetime.now(timezone.utc)

        extra: dict = dict(artist.extra or {})
        for key in ("color", "details", "images", "url", "group", "role",
                    "has_grad", "sources", "archivedUrl"):
            val = data.get(key)
            if not val:
                continue
            if enrichment_only and key in extra:
                continue  # don't overwrite official data with archival data
            if key == "images":
                seen: dict[str, dict] = {}  # basename -> best obj
                for i in val:
                    obj = {"url": i} if isinstance(i, str) else dict(i)
                    if not obj.get("ts"):
                        m = re.search(r"/web/(\d{14})if_/", obj["url"])
                        obj["ts"] = m.group(1) if m else import_ts
                    name = Path(obj["url"]).name
                    prev = seen.get(name)
                    if prev is None or obj["ts"] < prev["ts"]:
                        seen[name] = obj
                webp_stems = {Path(o["url"]).stem for o in seen.values() if o["url"].endswith(".webp")}
                val = sorted(
                    (o for o in seen.values()
                     if not (o["url"].endswith(".jpg") and Path(o["url"]).stem in webp_stems)),
                    key=lambda o: o["ts"], reverse=True,
                )
            extra[key] = val
        artist.extra = extra or None

        session.flush()

        # Create group → member relations (supports multi-group via groups list)
        group_slugs: list[str] = data.get("groups") or (
            [data["group"]] if data.get("has_grad") and data.get("group") else []
        )
        for gslug in group_slugs:
            group = _get_or_create_group(gslug)
            if group:
                rel = session.execute(
                    select(ArtistRelation).where(
                        ArtistRelation.parent_id == group.id,
                        ArtistRelation.child_id == artist.id,
                    )
                ).scalar_one_or_none()
                if not rel:
                    session.add(ArtistRelation(
                        parent_id=group.id, child_id=artist.id, kind="member"
                    ))

    session.commit()
    print("  Members committed.")


# ---------------------------------------------------------------------------
# Releases
# ---------------------------------------------------------------------------

def _coerce_str(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else None
    return str(val)


def _upsert_release_from_catalogue(session: Session, item: dict, name_map: dict[str, int]) -> None:
    ext_id = str(item.get("id", ""))
    if not ext_id:
        return

    release = session.execute(
        select(Release).where(Release.source == "hp_official", Release.external_id == ext_id)
    ).scalar_one_or_none()

    if not release:
        release = Release(source="hp_official", external_id=ext_id)
        session.add(release)

    artist_name = _coerce_str(item.get("artist") or item.get("artistName"))
    release.title = _coerce_str(item.get("title")) or ""
    release.category = _coerce_str(item.get("category"))
    release.artist_label_raw = artist_name
    release.artist_id = _lookup_artist(artist_name, name_map)
    release.release_date = parse_date(_coerce_str(item.get("releaseDate")))
    release.updated_at = datetime.now(timezone.utc)

    # Cover image from catalogue item
    img = item.get("image")
    if isinstance(img, dict):
        img_url = img.get("url")
    else:
        img_url = None

    if img_url:
        existing = session.execute(
            select(ReleaseImage).where(ReleaseImage.release_id == release.id)
        ).scalars().all() if release.id else []
        if not existing:
            session.flush()
            session.add(ReleaseImage(release_id=release.id, path=img_url, sort_order=0))


def _upsert_release_detail(session: Session, data: dict, name_map: dict[str, int]) -> None:
    ext_id = str(data.get("id", ""))
    if not ext_id:
        return

    release = session.execute(
        select(Release).where(Release.source == "hp_official", Release.external_id == ext_id)
    ).scalar_one_or_none()

    if not release:
        release = Release(source="hp_official", external_id=ext_id)
        session.add(release)

    artist_name = _coerce_str(data.get("artist"))
    release.title = _coerce_str(data.get("title")) or ""
    release.category = _coerce_str(data.get("category"))
    release.artist_label_raw = artist_name
    release.artist_id = _lookup_artist(artist_name, name_map)
    release.release_date = parse_date(_coerce_str(data.get("releaseDate")))
    release.label = _coerce_str(data.get("label"))
    release.url = _coerce_str(data.get("url"))
    release.updated_at = datetime.now(timezone.utc)

    session.flush()

    # Images — rebuild only if detail has images; otherwise keep the catalogue cover
    images_data = data.get("images") or []
    if images_data:
        session.execute(delete(ReleaseImage).where(ReleaseImage.release_id == release.id))
        for i, img_path in enumerate(images_data):
            session.add(ReleaseImage(release_id=release.id, path=img_path, sort_order=i))

    # Editions — upsert by sort_order
    editions_data = data.get("editions", [])
    existing_editions: dict[int, Edition] = {}
    for ed in session.execute(
        select(Edition).where(Edition.release_id == release.id)
    ).scalars():
        existing_editions[ed.sort_order] = ed

    for ed_idx, ed_data in enumerate(editions_data):
        ed = existing_editions.get(ed_idx)
        if not ed:
            ed = Edition(release_id=release.id, sort_order=ed_idx)
            session.add(ed)

        ed.name = ed_data.get("name")
        ed.image_path = ed_data.get("image")
        ed.price_raw = ed_data.get("price")
        ed.price_jpy = parse_price(ed_data.get("price"))
        ed.note = ed_data.get("note")

        session.flush()
        _upsert_discs(session, ed, ed_data.get("discs", []))

    # Delete editions beyond what's in source (preserves collection_items for kept editions)
    for idx, ed in existing_editions.items():
        if idx >= len(editions_data):
            # Only delete if not owned
            ci = session.execute(
                select(CollectionItem).where(CollectionItem.edition_id == ed.id)
            ).scalar_one_or_none()
            if not ci or not ci.owned:
                session.delete(ed)
            else:
                print(f"    WARNING: edition {ed.id} removed from source but kept (owned)")


def _upsert_discs(session: Session, edition: Edition, discs_data: list) -> None:
    existing_discs: dict[int, Disc] = {}
    for d in session.execute(
        select(Disc).where(Disc.edition_id == edition.id)
    ).scalars():
        existing_discs[d.sort_order] = d

    for disc_idx, disc_data in enumerate(discs_data):
        disc = existing_discs.get(disc_idx)
        if not disc:
            disc = Disc(edition_id=edition.id, sort_order=disc_idx)
            session.add(disc)

        disc.disc_type = disc_data.get("type")
        disc.catalog_no = disc_data.get("catalogNo")
        disc.jan = lookup_jan(disc_data.get("catalogNo"))

        session.flush()
        _upsert_tracks(session, disc, disc_data.get("tracks", []))

    for idx, disc in existing_discs.items():
        if idx >= len(discs_data):
            session.delete(disc)


def _upsert_tracks(session: Session, disc: Disc, tracks_data: list) -> None:
    existing_tracks: dict[int | None, Track] = {}
    for t in session.execute(select(Track).where(Track.disc_id == disc.id)).scalars():
        existing_tracks[t.index_no] = t

    seen_indices: set[int | None] = set()

    for tr_data in tracks_data:
        index_no = tr_data.get("index")
        seen_indices.add(index_no)

        track = existing_tracks.get(index_no)
        if not track:
            track = Track(disc_id=disc.id, index_no=index_no)
            session.add(track)

        track.title = tr_data.get("title", "")
        track.suffix = tr_data.get("suffix")
        track.duration_seconds = parse_duration(tr_data.get("duration"))

        session.flush()

        # Credits — rebuild
        session.execute(delete(TrackCredit).where(TrackCredit.track_id == track.id))

        for role, credit_text in (tr_data.get("credits") or {}).items():
            session.add(TrackCredit(track_id=track.id, role=role, credit_text=str(credit_text)))

    for idx, track in existing_tracks.items():
        if idx not in seen_indices:
            session.delete(track)


def import_catalogue(session: Session, name_map: dict[str, int],
                     year: int | None = None, all_years: bool = False) -> None:
    releases_dir = SCRAPER_DIR / "releases"
    if year:
        files = sorted(releases_dir.glob(f"{year}_releases.json"))
    elif all_years:
        files = sorted(releases_dir.glob("*_releases.json"))
    else:
        current = date.today().year
        files = [f for y in (current, current + 1)
                 if (f := releases_dir / f"{y}_releases.json").exists()]
    print(f"  Importing catalogue from {len(files)} year file(s)…")
    for f in files:
        data = load_json(f)
        if not data:
            continue
        for item in data.get("items", []):
            _upsert_release_from_catalogue(session, item, name_map)
    session.commit()
    print("  Catalogue committed.")


def import_release_details(session: Session, name_map: dict[str, int],
                           release_id: int | None = None, year: int | None = None,
                           incremental: bool = False) -> None:
    releases_dir = SCRAPER_DIR / "releases"

    if release_id is not None:
        files = [releases_dir / f"{release_id}.json"]
    elif year is not None:
        year_data = load_json(releases_dir / f"{year}_releases.json")
        if not year_data:
            print(f"  No catalogue for year {year}.")
            return
        ids = [item["id"] for item in year_data.get("items", []) if item.get("id")]
        files = [releases_dir / f"{rid}.json" for rid in ids]
    else:
        files = [p for p in releases_dir.glob("*.json") if re.fullmatch(r"\d+", p.stem)]

    existing = [f for f in files if f.exists()]

    if incremental:
        # Build {external_id: updated_at} from DB to skip unchanged files
        db_updated: dict[str, datetime] = {
            r.external_id: r.updated_at
            for r in session.execute(select(Release).where(Release.source == "hp_official")).scalars()
            if r.external_id and r.updated_at
        }
        to_import = []
        skipped = 0
        for f in existing:
            last_db = db_updated.get(f.stem)
            if last_db is not None:
                file_mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if last_db.tzinfo is None:
                    last_db = last_db.replace(tzinfo=timezone.utc)
                if file_mtime <= last_db:
                    skipped += 1
                    continue
            to_import.append(f)
        print(f"  {len(to_import)} files to import, {skipped} unchanged skipped.")
    else:
        to_import = existing
        print(f"  Importing {len(to_import)} scraped release detail files…")

    for i, f in enumerate(to_import, 1):
        data = load_json(f)
        if not data:
            continue
        _upsert_release_detail(session, data, name_map)
        if i % 100 == 0:
            session.commit()
            print(f"    {i}/{len(to_import)}…")

    session.commit()
    print("  Release details committed.")


# ---------------------------------------------------------------------------
# Songs resolution
# ---------------------------------------------------------------------------

def resolve_songs(session: Session) -> None:
    """Group tracks by (title, release artist_id) → create/link Song records."""
    from sqlalchemy import text

    print("  Resolving songs…")

    rows = session.execute(
        select(Track.id, Track.title, Track.song_id, Release.artist_id)
        .join(Disc, Track.disc_id == Disc.id)
        .join(Edition, Disc.edition_id == Edition.id)
        .join(Release, Edition.release_id == Release.id)
        .where(Release.artist_id.isnot(None))
    ).all()

    # group: (title, artist_id) -> list of track_id
    groups: dict[tuple[str, int], list[int]] = {}
    for track_id, title, song_id, artist_id in rows:
        key = (title, artist_id)
        groups.setdefault(key, []).append(track_id)

    song_cache: dict[tuple[str, int], int] = {}

    for (title, artist_id), track_ids in groups.items():
        # Check if any of these tracks already has a song_id
        existing_song_id: int | None = None
        for tid in track_ids:
            t = session.get(Track, tid)
            if t and t.song_id:
                existing_song_id = t.song_id
                break

        if existing_song_id is None:
            # Check song_cache
            existing_song_id = song_cache.get((title, artist_id))

        if existing_song_id is None:
            # Look for an existing song by title
            song = session.execute(
                select(Song).where(Song.title_canonical == title)
            ).scalar_one_or_none()
            if not song:
                song = Song(title_canonical=title)
                session.add(song)
                session.flush()
            existing_song_id = song.id
            song_cache[(title, artist_id)] = existing_song_id

        # Link all tracks in this group
        for tid in track_ids:
            t = session.get(Track, tid)
            if t and not t.song_id:
                t.song_id = existing_song_id

    session.commit()

    song_count = session.execute(select(Song)).scalar() if False else None
    from sqlalchemy import func
    song_count = session.execute(select(func.count(Song.id))).scalar()
    print(f"  Songs committed. Total songs: {song_count}")


# ---------------------------------------------------------------------------
# Build artist name map
# ---------------------------------------------------------------------------

def _strip_year_suffix(name: str) -> str:
    """Strip trailing year suffix like '26 or '26 from a group name."""
    return re.sub(r"['’]\d{2}$", "", name).strip()


def build_name_map(session: Session) -> dict[str, int]:
    name_map: dict[str, int] = {}
    for artist in session.execute(select(Artist).where(Artist.source == "hp_official")).scalars():
        for name in [artist.name_ja, artist.name_en]:
            if name:
                name_map[name] = artist.id
                # Also add the base name without year suffix as a fallback
                base = _strip_year_suffix(name)
                if base != name and base not in name_map:
                    name_map[base] = artist.id
    return name_map


def _lookup_artist(artist_name: str | None, name_map: dict[str, int]) -> int | None:
    if not artist_name:
        return None
    # Exact match first
    if artist_name in name_map:
        return name_map[artist_name]
    # Try stripping year suffix from the raw name
    base = _strip_year_suffix(artist_name)
    return name_map.get(base)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Import scraper data into the HP database")
    parser.add_argument("--all", action="store_true", help="Import everything")
    parser.add_argument("--artists", action="store_true", help="Import artists from artist_list.json")
    parser.add_argument("--members", action="store_true", help="Import member detail JSONs")
    parser.add_argument("--releases", action="store_true", help="Import all catalogue + details")
    parser.add_argument("--release", type=int, metavar="ID", help="Import single release detail")
    parser.add_argument("--year", type=int, help="Import catalogue + details for one year")
    parser.add_argument("--songs", action="store_true", help="Run songs resolution pass only")
    parser.add_argument("--incremental", action="store_true",
                        help="Skip release detail files not modified since last import")
    parser.add_argument("--all-years", action="store_true", dest="all_years",
                        help="Catalogue: import all years (default: current + next only)")
    args = parser.parse_args()

    if not any([args.all, args.artists, args.members, args.releases,
                args.release, args.year, args.songs]):
        parser.print_help()
        sys.exit(1)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    t0 = time.monotonic()

    with Session(engine) as session:
        artist_list = load_json(SCRAPER_DIR / "releases" / "artist_list.json") or {}

        if args.all or args.artists:
            print("[artists]")
            name_map = import_artists(session, artist_list)
        else:
            name_map = build_name_map(session)

        if args.all or args.members:
            print("[members]")
            import_members(session)
            name_map = build_name_map(session)

        if args.all or args.releases:
            print("[catalogue]")
            import_catalogue(session, name_map, all_years=args.all_years)
            print("[release details]")
            import_release_details(session, name_map, incremental=args.incremental)

        elif args.year:
            print(f"[catalogue {args.year}]")
            import_catalogue(session, name_map, year=args.year)
            print(f"[release details {args.year}]")
            import_release_details(session, name_map, year=args.year, incremental=args.incremental)

        elif args.release:
            print(f"[release {args.release}]")
            import_release_details(session, name_map, release_id=args.release)

        if args.all or args.songs:
            print("[songs]")
            resolve_songs(session)

    elapsed = time.monotonic() - t0
    if elapsed >= 60:
        print(f"Done in {elapsed / 60:.1f} min.")
    else:
        print(f"Done in {elapsed:.1f}s.")


if __name__ == "__main__":
    main()
