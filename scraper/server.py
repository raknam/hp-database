#!/usr/bin/env python3
"""Simple web server to browse scraped helloproject.com data.

Usage:
    py server.py            # starts on http://localhost:8000
    py server.py --port 9000
"""

import argparse
import json
import re
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

RELEASES_DIR = Path("releases")
MEMBERS_DIR = Path("members")
IMAGES_DIR = Path("images")
SITE_URL = "https://helloproject.com"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


class DataStore:
    def __init__(self):
        self.version = load_json(RELEASES_DIR / "version.json") or {}
        self.artist_list = load_json(RELEASES_DIR / "artist_list.json") or {}
        self.artists_by_id = self.artist_list.get("artistsById", {})
        self.profiles_by_id = self.artist_list.get("profilesById", {})
        self.relations = self.artist_list.get("artistRelation", {})

        self.release_years = sorted(
            (int(p.stem.replace("_releases", ""))
             for p in RELEASES_DIR.glob("*_releases.json")),
            reverse=True,
        )

        # year_releases: year -> list of items
        self.year_releases: dict[int, list] = {}
        for year in self.release_years:
            data = load_json(RELEASES_DIR / f"{year}_releases.json")
            if data:
                self.year_releases[year] = data.get("items", [])

        # scraped release details: id -> dict
        self.releases: dict[int, dict] = {}
        for p in RELEASES_DIR.glob("*.json"):
            if re.fullmatch(r"\d+", p.stem):
                data = load_json(p)
                if data:
                    self.releases[int(p.stem)] = data

        # member details: id -> dict
        self.members: dict[int, dict] = {}
        for p in MEMBERS_DIR.glob("*.json"):
            if re.fullmatch(r"\d+", p.stem):
                data = load_json(p)
                if data:
                    self.members[int(p.stem)] = data

        # artist slug -> id
        self.artist_order: list[str] = [str(i) for i in self.artist_list.get("artistOrder", [])]

        self.artist_by_slug = {
            v.get("slug"): k
            for k, v in self.artists_by_id.items()
            if v.get("slug")
        }

        print(
            f"Loaded: {len(self.release_years)} years, "
            f"{sum(len(v) for v in self.year_releases.values())} catalogue releases, "
            f"{len(self.releases)} scraped releases, "
            f"{len(self.members)} members"
        )


DB = DataStore()


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #0e0e0e; color: #e8e8e8; min-height: 100vh; }
a { color: #c8a0ff; text-decoration: none; }
a:hover { text-decoration: underline; }
header { background: #1a1a2e; border-bottom: 1px solid #2a2a4a; padding: 12px 24px; display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
header .logo { font-size: 1.2rem; font-weight: 700; color: #fff; letter-spacing: 1px; }
header nav a { color: #aaa; font-size: 0.9rem; }
header nav a:hover { color: #fff; }
.group-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; margin-top: 8px; }
.group-card { background: #141414; border: 1px solid #222; border-radius: 10px; overflow: hidden; display: flex; flex-direction: column; }
.group-card-banner { position: relative; height: 140px; overflow: hidden; background: #1a1a2e; }
.group-card-banner img { width: 100%; height: 100%; object-fit: cover; object-position: top; filter: brightness(0.7); }
.group-card-banner .group-card-name { position: absolute; bottom: 10px; left: 14px; font-size: 1.1rem; font-weight: 700; color: #fff; text-shadow: 0 1px 4px #000; }
.group-card-body { padding: 12px 14px; flex: 1; }
.group-card-members { display: flex; flex-wrap: wrap; gap: 6px; }
.member-chip { display: flex; align-items: center; gap: 5px; background: #1e1e1e; border-radius: 20px; padding: 3px 10px 3px 3px; font-size: 0.75rem; text-decoration: none; color: #ccc; transition: background .12s; }
.member-chip:hover { background: #2a2a4a; color: #fff; text-decoration: none; }
.member-chip img { width: 22px; height: 22px; border-radius: 50%; object-fit: cover; object-position: top; }
.member-chip .chip-placeholder { width: 22px; height: 22px; border-radius: 50%; background: #333; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; flex-shrink: 0; }
.search-bar { margin-left: auto; display: flex; gap: 8px; }
.search-bar input { background: #111; border: 1px solid #333; color: #eee; padding: 6px 12px; border-radius: 4px; font-size: 0.9rem; width: 220px; }
.search-bar button { background: #5a2fa0; border: none; color: #fff; padding: 6px 14px; border-radius: 4px; cursor: pointer; }
main { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 1.6rem; margin-bottom: 20px; }
h2 { font-size: 1.2rem; margin: 24px 0 12px; color: #ccc; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
.card { background: #1a1a1a; border-radius: 8px; overflow: hidden; transition: transform .15s; }
.card:hover { transform: translateY(-3px); }
.card img { width: 100%; aspect-ratio: 1; object-fit: cover; background: #222; display: block; }
.card .no-img { width: 100%; aspect-ratio: 1; background: #1f1f1f; display: flex; align-items: center; justify-content: center; font-size: 2rem; color: #444; }
.card-body { padding: 10px; }
.card-body .title { font-size: 0.82rem; font-weight: 600; line-height: 1.3; color: #eee; }
.card-body .sub { font-size: 0.75rem; color: #888; margin-top: 4px; }
.badge { display: inline-block; font-size: 0.7rem; padding: 2px 7px; border-radius: 12px; background: #2a2a4a; color: #aab; margin-top: 4px; }
.year-nav { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
.year-nav a { background: #1a1a2e; padding: 5px 14px; border-radius: 20px; font-size: 0.85rem; color: #aaa; border: 1px solid #2a2a4a; }
.year-nav a:hover, .year-nav a.active { background: #5a2fa0; color: #fff; border-color: #5a2fa0; text-decoration: none; }
.release-detail { display: flex; gap: 32px; flex-wrap: wrap; }
.release-detail .cover { flex: 0 0 260px; }
.release-detail .cover img { width: 100%; border-radius: 8px; }
.release-detail .info { flex: 1; min-width: 240px; }
.meta-table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
.meta-table td { padding: 6px 10px; border-bottom: 1px solid #1f1f1f; font-size: 0.9rem; }
.meta-table td:first-child { color: #888; width: 120px; white-space: nowrap; }
.editions { margin-top: 24px; }
.edition-block { background: #141414; border: 1px solid #222; border-radius: 8px; margin-bottom: 20px; overflow: hidden; }
.edition-header { background: #1a1a2e; padding: 10px 16px; font-weight: 600; font-size: 0.9rem; display: flex; justify-content: space-between; align-items: center; }
.edition-price { font-size: 0.8rem; color: #888; font-weight: normal; }
.edition-note { font-size: 0.78rem; color: #c8a0ff; margin-top: 2px; }
.disc-label { padding: 8px 16px 4px; font-size: 0.78rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
.track-list { list-style: none; }
.track-list li { display: flex; align-items: baseline; gap: 10px; padding: 5px 16px; border-bottom: 1px solid #1a1a1a; font-size: 0.85rem; }
.track-list li:last-child { border-bottom: none; }
.track-idx { color: #555; width: 24px; text-align: right; flex-shrink: 0; }
.track-title { flex: 1; }
.track-suffix { color: #888; font-size: 0.78rem; }
.track-dur { color: #666; flex-shrink: 0; }
.track-credits { font-size: 0.72rem; color: #666; display: block; margin-top: 2px; }
.gallery { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0; }
.gallery img { height: 120px; border-radius: 6px; object-fit: cover; }
.member-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 14px; }
.member-card { background: #1a1a1a; border-radius: 8px; overflow: hidden; text-align: center; }
.member-card img { width: 100%; aspect-ratio: 3/4; object-fit: cover; object-position: top; }
.member-card .no-img { width: 100%; aspect-ratio: 3/4; background: #1f1f1f; display: flex; align-items: center; justify-content: center; font-size: 2rem; color: #444; }
.member-card-body { padding: 8px 6px; }
.member-card-body .name { font-size: 0.82rem; font-weight: 600; }
.member-card-body .group { font-size: 0.72rem; color: #888; margin-top: 2px; }
.member-detail { display: flex; gap: 28px; flex-wrap: wrap; }
.member-detail .photo { flex: 0 0 200px; }
.member-detail .photo img { width: 100%; border-radius: 8px; }
.color-swatch { display: inline-block; width: 14px; height: 14px; border-radius: 50%; vertical-align: middle; margin-right: 6px; border: 1px solid #333; }
.search-results .result-item { padding: 12px 0; border-bottom: 1px solid #1f1f1f; display: flex; gap: 12px; align-items: flex-start; }
.search-results .result-item img { width: 56px; height: 56px; object-fit: cover; border-radius: 4px; flex-shrink: 0; }
.search-results .result-item .no-img { width: 56px; height: 56px; background: #1f1f1f; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; color: #444; flex-shrink: 0; }
.tag { display: inline-block; font-size: 0.7rem; padding: 1px 6px; border-radius: 3px; background: #222; color: #888; margin-left: 6px; }
.artists-list { columns: 2; column-gap: 32px; }
@media(min-width:700px) { .artists-list { columns: 3; } }
.artists-list .group-block { break-inside: avoid; margin-bottom: 20px; }
.artists-list .group-name { font-weight: 700; font-size: 0.95rem; color: #c8a0ff; margin-bottom: 6px; }
.artists-list .group-name a { color: inherit; }
.artists-list .member-link { font-size: 0.83rem; color: #aaa; margin: 2px 0; display: block; }
.no-data { color: #555; text-align: center; padding: 40px; }
"""


def page(title: str, body: str, active_year: int | None = None, q: str = "") -> str:
    year_links = " ".join(
        f'<a href="/releases/{y}" class="{"active" if y == active_year else ""}">{y}</a>'
        for y in DB.release_years
    )
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} – HP Data</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <span class="logo"><a href="/" style="color:inherit">HP Data</a></span>
  <nav style="display:flex;gap:16px">
    <a href="/groups">Groups</a>
    <a href="/members">Members</a>
    <a href="/releases">Releases</a>
  </nav>
  <form class="search-bar" action="/search" method="get">
    <input name="q" placeholder="Search…" value="{escape(q)}">
    <button type="submit">Go</button>
  </form>
</header>
<main>
{body}
</main>
</body>
</html>"""


def escape(s) -> str:
    if s is None:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def img_tag(path: str | None, cls: str = "", alt: str = "", placeholder: str = "🎵") -> str:
    if not path:
        return f'<div class="no-img">{placeholder}</div>'
    filename = Path(path).name
    local = IMAGES_DIR / filename
    src = f"/images/{filename}" if local.exists() else f"{SITE_URL}{path}"
    return f'<img src="{escape(src)}" alt="{escape(alt)}" loading="lazy">'


def cover_img(path: str | None, alt: str = "") -> str:
    return img_tag(path, alt=alt)


def release_cover_path(item: dict) -> str | None:
    return item.get("image", {}).get("url") if isinstance(item.get("image"), dict) else None


def year_nav(active: int | None = None) -> str:
    links = "".join(
        f'<a href="/releases/{y}" class="{"active" if y == active else ""}">{y}</a>'
        for y in DB.release_years
    )
    return f'<div class="year-nav"><a href="/releases" class="{"active" if active is None else ""}">All</a>{links}</div>'


# ---------------------------------------------------------------------------
# Page renderers
# ---------------------------------------------------------------------------

def render_home() -> str:
    total_cat = sum(len(v) for v in DB.year_releases.values())
    body = f"""
<h1>Hello! Project Data</h1>
<p style="color:#888;margin-bottom:20px">
  {len(DB.release_years)} years &nbsp;·&nbsp; {total_cat} catalogue releases &nbsp;·&nbsp;
  {len(DB.releases)} scraped &nbsp;·&nbsp; {len(DB.members)} members
</p>
{year_nav()}
"""
    if DB.release_years:
        latest = DB.release_years[0]
        items = DB.year_releases.get(latest, [])
        body += f'<h2>Latest releases ({latest})</h2><div class="grid">'
        for item in items[:24]:
            rid = item.get("id")
            title = escape(item.get("title", "—"))
            artist = escape(item.get("artist") or item.get("artistName", ""))
            cat = escape(item.get("category", ""))
            img = release_cover_path(item)
            link = f"/release/{rid}" if rid else "#"
            body += f"""
<a href="{link}" class="card">
  {cover_img(img, alt=title)}
  <div class="card-body">
    <div class="title">{title}</div>
    <div class="sub">{artist}</div>
    <span class="badge">{cat}</span>
  </div>
</a>"""
        body += "</div>"
    return page("Home", body)


def render_releases(year: int | None) -> str:
    if year is not None and year not in DB.year_releases:
        return page(str(year), f'<h1>{year}</h1><p class="no-data">No data for this year.</p>')

    if year is None:
        title = "All Releases"
        items = []
        for y in DB.release_years:
            items.extend(DB.year_releases.get(y, []))
    else:
        title = f"{year} Releases"
        items = DB.year_releases.get(year, [])

    body = f"<h1>{title} <span style='color:#555;font-size:1rem'>({len(items)})</span></h1>"
    body += year_nav(year)
    body += '<div class="grid">'
    for item in items:
        rid = item.get("id")
        t = escape(item.get("title", "—"))
        artist = escape(item.get("artist") or item.get("artistName", ""))
        cat = escape(item.get("category", ""))
        date = escape(item.get("releaseDate", ""))
        img = release_cover_path(item)
        link = f"/release/{rid}" if rid else "#"
        body += f"""
<a href="{link}" class="card">
  {cover_img(img, alt=t)}
  <div class="card-body">
    <div class="title">{t}</div>
    <div class="sub">{artist}</div>
    <span class="badge">{cat}</span>
    {f'<div class="sub">{date}</div>' if date else ''}
  </div>
</a>"""
    body += "</div>"
    return page(title, body, active_year=year)


def render_release(rid: int) -> str | None:
    data = DB.releases.get(rid)
    if not data:
        # try to find basic info from catalogue
        for items in DB.year_releases.values():
            for item in items:
                if item.get("id") == rid:
                    return render_release_stub(rid, item)
        return None

    title = data.get("title", f"Release {rid}")
    artist = data.get("artist", "")
    category = data.get("category", "")
    date = data.get("releaseDate", "")
    label = data.get("label", "")
    images = data.get("images", [])
    editions = data.get("editions", [])

    first_img = images[0] if images else None

    meta = f"""
<table class="meta-table">
  <tr><td>Artist</td><td>{escape(artist)}</td></tr>
  <tr><td>Category</td><td>{escape(category)}</td></tr>
  <tr><td>Release date</td><td>{escape(date)}</td></tr>
  <tr><td>Label</td><td>{escape(label)}</td></tr>
  <tr><td>ID</td><td>{rid} &nbsp;<a href="{SITE_URL}/release/{rid}/" target="_blank" style="font-size:0.8rem">↗ site</a></td></tr>
</table>"""

    gallery_html = ""
    if len(images) > 1:
        gallery_html = '<div class="gallery">' + "".join(
            f'<a href="{SITE_URL}{escape(p)}" target="_blank">{img_tag(p)}</a>'
            for p in images
        ) + "</div>"

    editions_html = ""
    for ed in editions:
        ed_name = escape(ed.get("name") or "Edition")
        ed_price = escape(ed.get("price") or "")
        ed_note = escape(ed.get("note") or "")
        ed_img_path = ed.get("image")

        discs_html = ""
        for disc in ed.get("discs", []):
            dtype = escape(disc.get("type") or "")
            cat_no = escape(disc.get("catalogNo") or "")
            label_parts = [x for x in [dtype, cat_no] if x]
            discs_html += f'<div class="disc-label">{" · ".join(label_parts)}</div>'
            discs_html += '<ul class="track-list">'
            for tr in disc.get("tracks", []):
                idx = tr.get("index", "")
                tname = escape(tr.get("title") or "")
                suffix = escape(tr.get("suffix") or "")
                dur = escape(tr.get("duration") or "")
                credits = tr.get("credits", {})
                credits_str = " · ".join(f"{escape(k)}：{escape(v)}" for k, v in credits.items()) if credits else ""
                discs_html += f"""
<li>
  <span class="track-idx">{idx}</span>
  <span class="track-title">
    {tname}
    {f'<span class="track-suffix">{suffix}</span>' if suffix else ''}
    {f'<span class="track-credits">{credits_str}</span>' if credits_str else ''}
  </span>
  <span class="track-dur">{dur}</span>
</li>"""
            discs_html += "</ul>"

        ed_img_html = ""
        if ed_img_path and ed_img_path != first_img:
            ed_img_html = f'<div style="padding:10px">{img_tag(ed_img_path, alt=ed_name)}</div>'

        editions_html += f"""
<div class="edition-block">
  <div class="edition-header">
    <div>
      <div>{ed_name}</div>
      {f'<div class="edition-note">{ed_note}</div>' if ed_note else ''}
    </div>
    <div class="edition-price">{ed_price}</div>
  </div>
  {ed_img_html}
  {discs_html}
</div>"""

    body = f"""
<h1>{escape(title)}</h1>
<div class="release-detail">
  <div class="cover">{cover_img(first_img, alt=title)}{gallery_html}</div>
  <div class="info">
    {meta}
    <div class="editions">
      {"<h2>Editions & Tracklists</h2>" + editions_html if editions else '<p style="color:#555">No edition data scraped.</p>'}
    </div>
  </div>
</div>"""

    return page(title, body)


def render_release_stub(rid: int, item: dict) -> str:
    title = item.get("title", f"Release {rid}")
    artist = escape(item.get("artist") or item.get("artistName", ""))
    cat = escape(item.get("category", ""))
    date = escape(item.get("releaseDate", ""))
    img = release_cover_path(item)

    body = f"""
<h1>{escape(title)}</h1>
<div class="release-detail">
  <div class="cover">{cover_img(img, alt=title)}</div>
  <div class="info">
    <table class="meta-table">
      <tr><td>Artist</td><td>{artist}</td></tr>
      <tr><td>Category</td><td>{cat}</td></tr>
      <tr><td>Release date</td><td>{date}</td></tr>
      <tr><td>ID</td><td>{rid} &nbsp;<a href="{SITE_URL}/release/{rid}/" target="_blank">↗ site</a></td></tr>
    </table>
    <p style="color:#666;font-size:0.85rem">Detail not scraped yet — run <code>py scraper.py scrape --id {rid}</code></p>
  </div>
</div>"""
    return page(title, body)


def profile_name(profile: dict, fallback: str = "") -> str:
    return profile.get("nameJa") or profile.get("nameEn") or profile.get("slug") or fallback


def resolve_members(group_id: str, depth: int = 0) -> list[tuple[int, str, str | None]]:
    """Return list of (member_id, name, thumbnail_url) for a group, resolving sub-units."""
    if depth > 2:
        return []
    entries = []
    for entry in DB.relations.get(group_id, []):
        kind = entry.get("kind")
        eid = str(entry["id"])
        if kind == "member":
            profile = DB.profiles_by_id.get(eid, {})
            mname = profile_name(profile, eid)
            mthumb = profile.get("images", {}).get("thumbnail", {})
            mthumb_url = mthumb.get("url") if mthumb else None
            entries.append((int(eid), mname, mthumb_url))
        elif kind == "unit":
            entries.extend(resolve_members(eid, depth + 1))
    return entries


def render_groups() -> str:
    profiles_by_id = DB.profiles_by_id

    # Only keep top-level groups (those present in artistsById as groups)
    group_ids = [gid for gid, a in DB.artists_by_id.items() if a.get("artistType") == "group"]

    groups = []
    for group_id in group_ids:
        profile = profiles_by_id.get(group_id, {})
        name = profile_name(profile, group_id)
        slug = DB.artists_by_id[group_id].get("slug", "")

        group_imgs = profile.get("images", {})
        banner_url = None
        profile_imgs = group_imgs.get("profile", [])
        if profile_imgs:
            banner_url = profile_imgs[0].get("url")
        if not banner_url:
            thumb = group_imgs.get("thumbnail", {})
            banner_url = thumb.get("url") if thumb else None

        member_entries = resolve_members(group_id)
        groups.append((name, slug, group_id, banner_url, member_entries))

    order_index = {gid: i for i, gid in enumerate(DB.artist_order)}
    groups.sort(key=lambda x: order_index.get(x[2], 9999))

    cards = ""
    for name, slug, group_id, banner_url, members in groups:
        if banner_url:
            banner_filename = Path(banner_url).name
            banner_src = (
                f"/images/{banner_filename}" if (IMAGES_DIR / banner_filename).exists()
                else f"{SITE_URL}{banner_url}"
            )
            banner_html = f'<img src="{escape(banner_src)}" alt="{escape(name)}" loading="lazy">'
        else:
            banner_html = ""

        chips = ""
        for mid, mname, mthumb_url in members:
            if mthumb_url:
                fn = Path(mthumb_url).name
                msrc = f"/images/{fn}" if (IMAGES_DIR / fn).exists() else f"{SITE_URL}{mthumb_url}"
                chip_img = f'<img src="{escape(msrc)}" alt="{escape(mname)}">'
            else:
                chip_img = '<span class="chip-placeholder">👤</span>'
            chips += f'<a href="/member/{mid}" class="member-chip">{chip_img}{escape(mname)}</a>'

        group_href = f"/artist/{slug or group_id}"
        cards += f"""
<div class="group-card">
  <a href="{group_href}" class="group-card-banner">
    {banner_html}
    <span class="group-card-name">{escape(name)}</span>
  </a>
  <div class="group-card-body">
    <div class="group-card-members">{chips}</div>
  </div>
</div>"""

    body = f'<h1>Groups</h1><div class="group-grid">{cards or "<p class=\'no-data\'>No group data found.</p>"}</div>'
    return page("Groups", body)


def render_artist(slug: str) -> str | None:
    artist_id = DB.artist_by_slug.get(slug)
    if not artist_id:
        return None

    profile = DB.profiles_by_id.get(artist_id, {})
    name = profile_name(profile, slug)

    # collect releases from catalogue
    releases_in_cat = []
    for year, items in DB.year_releases.items():
        for item in items:
            a = item.get("artist") or item.get("artistName", "")
            if name and a == name:
                releases_in_cat.append(item)
    releases_in_cat.sort(key=lambda x: x.get("releaseDate", ""), reverse=True)

    # profile image
    thumb = profile.get("images", {}).get("thumbnail", {}).get("url")
    img_html = f'<div style="margin-bottom:16px">{img_tag(thumb, alt=name, placeholder="👤")}</div>' if thumb else ""

    cards = ""
    for item in releases_in_cat:
        rid = item.get("id")
        t = escape(item.get("title", "—"))
        cat = escape(item.get("category", ""))
        date = escape(item.get("releaseDate", ""))
        img = release_cover_path(item)
        link = f"/release/{rid}" if rid else "#"
        scraped = "✓" if rid in DB.releases else ""
        cards += f"""
<a href="{link}" class="card">
  {cover_img(img, alt=t)}
  <div class="card-body">
    <div class="title">{t} {f'<span style="color:#5a5">{scraped}</span>' if scraped else ''}</div>
    <div class="sub">{date}</div>
    <span class="badge">{cat}</span>
  </div>
</a>"""

    body = f"""
<h1>{escape(name)}</h1>
{img_html}
<h2>Releases ({len(releases_in_cat)})</h2>
<div class="grid">{cards or '<p class="no-data">No releases found in catalogue.</p>'}</div>"""
    return page(name, body)


def render_members() -> str:
    if not DB.members:
        return page("Members", '<p class="no-data">No member data — run <code>py scraper.py members</code></p>')

    def parse_birthday(m: dict):
        raw = (m.get("details") or {}).get("生年月日", "")
        match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
        if match:
            return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return (9999, 99, 99)

    all_members = sorted(DB.members.values(), key=parse_birthday)

    cards = ""
    for m in all_members:
        mid = m.get("id")
        name = escape(profile_name(m, str(mid)))
        name_en = escape(m.get("nameEn") or "")
        group = escape(m.get("group") or "")
        imgs = m.get("images", [])
        img = imgs[0] if imgs else None
        color = m.get("color", {})
        swatch = f'<span class="color-swatch" style="background:{escape(color.get("hex","#444"))}"></span>' if color and color.get("hex") else ""
        cards += f"""
<a href="/member/{mid}" class="member-card">
  {img_tag(img, alt=name, placeholder="👤")}
  <div class="member-card-body">
    <div class="name">{swatch}{name}</div>
    {f'<div class="group">{name_en}</div>' if name_en else ''}
    <div class="group">{group}</div>
  </div>
</a>"""

    body = f'<h1>Members ({len(DB.members)})</h1><div class="member-grid">{cards}</div>'
    return page("Members", body)


def render_member(mid: int) -> str | None:
    m = DB.members.get(mid)
    if not m:
        return None

    name_ja = m.get("nameJa", "")
    name_en = m.get("nameEn", "")
    name_kana = m.get("nameKana", "")
    group = m.get("group", "")
    role = m.get("role", "")
    color = m.get("color", {})
    details = m.get("details", {})
    images = m.get("images", [])

    title = name_ja or name_en or str(mid)

    color_html = ""
    if color:
        swatch = f'<span class="color-swatch" style="background:{escape(color.get("hex","#444"))}"></span>'
        color_html = f"<tr><td>Color</td><td>{swatch}{escape(color.get('name',''))}</td></tr>"

    details_rows = "".join(
        f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>"
        for k, v in details.items()
    )

    photos_html = ""
    if len(images) > 1:
        photos_html = '<div class="gallery" style="margin-top:12px">' + "".join(
            img_tag(p, alt=name_ja, placeholder="👤") for p in images[1:]
        ) + "</div>"

    slug_url = m.get("url", "")
    site_link = f'<a href="{SITE_URL}{escape(slug_url)}" target="_blank">↗ site</a>' if slug_url else ""

    body = f"""
<h1>{escape(title)}</h1>
<div class="member-detail">
  <div class="photo">
    {img_tag(images[0] if images else None, alt=title, placeholder="👤")}
    {photos_html}
  </div>
  <div class="info">
    <table class="meta-table">
      {f'<tr><td>Name (JA)</td><td>{escape(name_ja)}</td></tr>' if name_ja else ''}
      {f'<tr><td>Name (EN)</td><td>{escape(name_en)}</td></tr>' if name_en else ''}
      {f'<tr><td>Kana</td><td>{escape(name_kana)}</td></tr>' if name_kana else ''}
      {f'<tr><td>Group</td><td><a href="/artist/{escape(group)}">{escape(group)}</a></td></tr>' if group else ''}
      {f'<tr><td>Role</td><td>{escape(role)}</td></tr>' if role else ''}
      {color_html}
      {details_rows}
      <tr><td>Link</td><td>{site_link}</td></tr>
    </table>
  </div>
</div>"""
    return page(title, body)


def render_search(q: str) -> str:
    q = q.strip()
    if not q:
        return page("Search", '<p class="no-data">Enter a search term.</p>', q=q)

    ql = q.lower()
    results = []

    # Search scraped releases
    for rid, data in DB.releases.items():
        title = data.get("title", "")
        artist = data.get("artist", "")
        if ql in title.lower() or ql in artist.lower():
            results.append(("release", rid, data))

    # Search catalogue items not yet scraped
    scraped_ids = set(DB.releases.keys())
    for year, items in DB.year_releases.items():
        for item in items:
            rid = item.get("id")
            if rid in scraped_ids:
                continue
            title = item.get("title", "")
            artist = item.get("artist") or item.get("artistName", "")
            if ql in title.lower() or ql in artist.lower():
                results.append(("catalogue", rid, item))

    # Search members
    for mid, m in DB.members.items():
        name_ja = m.get("nameJa", "")
        name_en = m.get("nameEn", "")
        kana = m.get("nameKana", "")
        if any(ql in (s or "").lower() for s in [name_ja, name_en, kana]):
            results.append(("member", mid, m))

    items_html = ""
    for kind, eid, data in results[:100]:
        if kind in ("release", "catalogue"):
            title = escape(data.get("title", "—"))
            artist = escape(data.get("artist") or data.get("artistName", ""))
            cat = escape(data.get("category", ""))
            img = (data.get("images", [None])[0] if kind == "release" else release_cover_path(data))
            tag_html = f'<span class="tag">{"scraped" if kind == "release" else "catalogue only"}</span>'
            items_html += f"""
<div class="result-item">
  <a href="/release/{eid}">{img_tag(img, alt=title)}</a>
  <div>
    <div><a href="/release/{eid}">{title}</a>{tag_html}</div>
    <div style="color:#888;font-size:0.82rem">{artist} · {cat}</div>
  </div>
</div>"""
        else:
            name = escape(data.get("nameJa") or data.get("nameEn") or str(eid))
            name_en = escape(data.get("nameEn") or "")
            group = escape(data.get("group") or "")
            imgs = data.get("images", [])
            img = imgs[0] if imgs else None
            items_html += f"""
<div class="result-item">
  <a href="/member/{eid}">{img_tag(img, alt=name, placeholder="👤")}</a>
  <div>
    <div><a href="/member/{eid}">{name}</a><span class="tag">member</span></div>
    <div style="color:#888;font-size:0.82rem">{name_en} · {group}</div>
  </div>
</div>"""

    count = len(results)
    shown = min(count, 100)
    body = f"""
<h1>Search: "{escape(q)}" <span style="color:#555;font-size:1rem">({shown}{'+' if count > 100 else ''} results)</span></h1>
<div class="search-results">{items_html or '<p class="no-data">No results found.</p>'}</div>"""
    return page(f"Search: {q}", body, q=q)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_404(self):
        self.send_html(page("Not Found", '<h1>404 Not Found</h1>'), 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path).rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        # Serve images
        if path.startswith("/images/"):
            filename = Path(path).name
            img_path = IMAGES_DIR / filename
            if img_path.exists() and img_path.suffix in {".webp", ".jpg", ".jpeg", ".png", ".gif"}:
                data = img_path.read_bytes()
                mime = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "png": "image/png", "gif": "image/gif"}.get(img_path.suffix.lstrip("."), "image/webp")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_404()
            return

        if path == "/" or path == "":
            self.send_html(render_home())
        elif path == "/groups":
            self.send_html(render_groups())
        elif path.startswith("/artist/"):
            slug = path[len("/artist/"):]
            html = render_artist(slug)
            self.send_html(html) if html else self.send_404()
        elif path == "/releases":
            self.send_html(render_releases(None))
        elif path.startswith("/releases/"):
            part = path[len("/releases/"):]
            try:
                year = int(part)
            except ValueError:
                self.send_404()
                return
            self.send_html(render_releases(year))
        elif path.startswith("/release/"):
            part = path[len("/release/"):]
            try:
                rid = int(part)
            except ValueError:
                self.send_404()
                return
            html = render_release(rid)
            self.send_html(html) if html else self.send_404()
        elif path == "/members":
            self.send_html(render_members())
        elif path.startswith("/member/"):
            part = path[len("/member/"):]
            try:
                mid = int(part)
            except ValueError:
                self.send_404()
                return
            html = render_member(mid)
            self.send_html(html) if html else self.send_404()
        elif path == "/search":
            q = qs.get("q", [""])[0]
            self.send_html(render_search(q))
        else:
            self.send_404()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="HP Data web browser")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="localhost")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True

    def shutdown(sig, frame):
        print("\nStopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, shutdown)

    print(f"Serving at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
