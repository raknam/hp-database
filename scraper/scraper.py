#!/usr/bin/env python3
import argparse
import json
import os
import re
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from image_path import image_subpath

SITE_URL = "https://helloproject.com"
JSON_BASE = f"{SITE_URL}/json"
HEADERS = {
    "User-Agent": os.environ.get(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    )
}
DEBUG = False  # set via --debug flag

RELEASES_DIR = Path("releases")
MEMBERS_DIR = Path("members")
IMAGES_DIR = Path("images")
HP_CACHE_DIR     = Path("cache") / "releases" / "hp"
MEMBERS_CACHE_DIR = Path("cache") / "members" / "current"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def fetch(url: str) -> requests.Response:
    if DEBUG:
        print(f"  FETCH {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def save_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def download_image(path: str):
    filename = Path(path).name
    dest = IMAGES_DIR / image_subpath(filename)
    if dest.exists():
        if DEBUG:
            print(f"  SKIP  {filename}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = fetch(f"{SITE_URL}{path}")
    dest.write_bytes(resp.content)
    if not DEBUG:
        print(f"  image: {filename}")


# ---------------------------------------------------------------------------
# update command
# ---------------------------------------------------------------------------

def cmd_update(args):
    print("Fetching version.json...")
    version_data = fetch(f"{JSON_BASE}/version.json").json()
    save_json(version_data, RELEASES_DIR / "version.json")

    version = version_data["version"]
    release_years = version_data["releaseYears"]
    if not args.all_years:
        current = date.today().year
        release_years = [y for y in release_years if y in (current, current + 1)]
    print(f"Version: {version}")
    print(f"Release years: {' '.join(str(y) for y in release_years)}")

    print("Fetching artist_list.json...")
    artist_data = fetch(f"{JSON_BASE}/{version}/artist_list.json").json()
    save_json(artist_data, RELEASES_DIR / "artist_list.json")

    for year in release_years:
        print(f"Fetching {year}_releases.json...")
        try:
            raw = fetch(f"{JSON_BASE}/{version}/{year}_releases.json").text
        except Exception as e:
            print(f"  Warning: failed to fetch {year}_releases.json: {e}")
            continue
        dest = RELEASES_DIR / f"{year}_releases.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(raw, encoding="utf-8")

        try:
            year_data = json.loads(raw)
            for item in year_data.get("items", []):
                img = item.get("image", {}).get("url")
                if img:
                    download_image(img)
        except json.JSONDecodeError as e:
            print(f"  Warning: could not parse {year}_releases.json for images: {e}")

    print("Downloading artist images...")
    for profile in artist_data.get("profilesById", {}).values():
        images = profile.get("images", {})
        for img in images.get("profile", []):
            if img.get("url"):
                download_image(img["url"])
        if images.get("thumbnail", {}).get("url"):
            download_image(images["thumbnail"]["url"])
        for rel in profile.get("release", []):
            img = rel.get("image", {}).get("url")
            if img:
                download_image(img)

    print("Done.")


# ---------------------------------------------------------------------------
# scrape command — HTML parsing
# ---------------------------------------------------------------------------

def el_text(el) -> str | None:
    return re.sub(r"\s+", " ", el.get_text()).strip() if el else None


def parse_credits(notes_el) -> dict:
    if not notes_el:
        return {}
    credits = {}
    for span in notes_el.select("span"):
        raw = el_text(span)
        if raw and "：" in raw:
            key, _, value = raw.partition("：")
            credits[key] = value
    return credits


def parse_track(item) -> dict:
    index_el = item.select_one(".TrackListItem__index")
    index = int(re.sub(r"\D", "", el_text(index_el))) if index_el else None

    title_el = item.select_one(".TrackListItem__title > span")
    title = suffix = None
    if title_el:
        spans = title_el.find_all("span", recursive=False)
        title = el_text(spans[0]) if spans else el_text(title_el)
        suffix = el_text(spans[1]) if len(spans) > 1 else None

    duration = el_text(item.select_one(".TrackListItem__duration"))
    credits = parse_credits(item.select_one(".TrackListItem__notes"))

    track = {"index": index, "title": title, "duration": duration}
    if suffix:
        track["suffix"] = suffix
    if credits:
        track["credits"] = credits
    return track


def parse_disc(tracklist_div) -> dict:
    headline = tracklist_div.select_one(".ReleaseEdition__headline")
    media_type = el_text(headline.select_one(".ReleaseEdition__mediaType")) if headline else None
    catalog_el = headline.select_one('[class*="text-blueGray"]') if headline else None
    catalog_no = el_text(catalog_el)

    tracks = [parse_track(item) for item in tracklist_div.select(".TrackListItem")]

    disc = {"type": media_type, "tracks": tracks}
    if catalog_no:
        disc["catalogNo"] = catalog_no
    return disc


def parse_edition(edition_div) -> dict:
    name = el_text(edition_div.select_one(".ReleaseEdition__name h2"))
    img_el = edition_div.select_one(".ReleaseEdition__cover img")
    image = img_el["src"] if img_el else None
    price = el_text(edition_div.select_one(".ReleaseEdition__coverName"))
    note = el_text(edition_div.select_one(".ReleaseEdition__head .paragraph-md"))
    discs = [parse_disc(tl) for tl in edition_div.select(".ReleaseEdition__discs .TrackList")]

    edition = {"name": name, "image": image, "price": price, "discs": discs}
    if note:
        edition["note"] = note
    return edition


def parse_release_html(release_id: int, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    title = el_text(soup.select_one("h1.ReleaseHead__mainName"))
    category = el_text(soup.select_one(".StatusLabel--category"))

    artist = None
    main_title = soup.select_one(".ReleaseHead__mainTitle")
    if main_title:
        paragraphs = main_title.select(".paragraph-sm")
        if len(paragraphs) >= 2:
            artist = el_text(paragraphs[1])

    release_date = label = isbn = None
    for dl in soup.select(".ReleaseHead__mainDetails dl.contents"):
        for dt, dd in zip(dl.select("dt"), dl.select("dd")):
            key = el_text(dt)
            val = el_text(dd)
            if "発売日" in key:
                release_date = val
            elif "レーベル" in key:
                label = val
            elif "ISBN" in key:
                isbn = val

    header_catalog_el = soup.select_one(".ReleaseHead__mainDetails [class*='text-blueGray']")
    header_catalog_no = el_text(header_catalog_el) if header_catalog_el else None

    gallery = [
        img["src"]
        for img in soup.select(".ReleaseItemGallery__image img")
        if img.get("src")
    ]

    editions = [parse_edition(div) for div in soup.select(".ReleaseEdition")]

    result = {
        "id": release_id,
        "url": f"/release/{release_id}/",
        "title": title,
        "category": category,
        "artist": artist,
        "releaseDate": release_date,
        "label": label,
        "images": gallery,
        "editions": editions,
    }
    if header_catalog_no:
        result["catalogNo"] = header_catalog_no
    if isbn:
        result["isbn"] = isbn
    return result


def scrape_one(release_id: int, force: bool):
    out_file = RELEASES_DIR / f"{release_id}.json"
    if out_file.exists() and not force:
        print(f"  {release_id}: already exists, skipping")
        return

    cache_file = HP_CACHE_DIR / f"{release_id}.html"
    if cache_file.exists() and not force:
        html = cache_file.read_text(encoding="utf-8")
    else:
        resp = fetch(f"{SITE_URL}/release/{release_id}/")
        html = resp.text
        HP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(html, encoding="utf-8")

    data = parse_release_html(release_id, html)

    for path in data["images"]:
        download_image(path)

    save_json(data, out_file)
    print(f"  {release_id}: written to {out_file}")


def collect_ids(year: int | None) -> list[int]:
    if year:
        files = [RELEASES_DIR / f"{year}_releases.json"]
    else:
        files = sorted(RELEASES_DIR.glob("*_releases.json"))

    ids = []
    for f in files:
        if not f.exists():
            print(f"  Warning: {f} not found, run update first")
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            if item.get("id"):
                ids.append(item["id"])
    return ids


def cmd_scrape(args):
    if args.id:
        ids = [args.id]
    else:
        ids = collect_ids(args.year)
        print(f"Found {len(ids)} releases to scrape")

    for release_id in ids:
        scrape_one(release_id, args.force)


# ---------------------------------------------------------------------------
# members command — member page parsing
# ---------------------------------------------------------------------------

def collect_members() -> list[dict]:
    """Return list of {id, group_slug, member_slug} from artist_list.json."""
    artist_file = RELEASES_DIR / "artist_list.json"
    if not artist_file.exists():
        print("Warning: releases/artist_list.json not found, run update first")
        return []

    data = json.loads(artist_file.read_text(encoding="utf-8"))
    artists_by_id = data.get("artistsById", {})
    profiles_by_id = data.get("profilesById", {})
    relations = data.get("artistRelation", {})

    members = []
    for group_id, members_list in relations.items():
        group = artists_by_id.get(group_id, {})
        group_slug = group.get("slug")
        if not group_slug:
            continue
        for entry in members_list:
            if entry.get("kind") != "member":
                continue
            member_id = str(entry["id"])
            profile = profiles_by_id.get(member_id, {})
            member_slug = profile.get("slug")
            if not member_slug:
                continue
            members.append({"id": int(member_id), "group_slug": group_slug, "member_slug": member_slug})

    return members


def parse_member_html(member_id: int, group_slug: str, member_slug: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    header = soup.select_one(".MemberHeader")
    if not header:
        return {"id": member_id, "url": f"/{group_slug}/{member_slug}/", "slug": member_slug, "group": group_slug}

    content = header.select_one(".MemberHeader__content")
    name_block = content.select_one("div") if content else None

    role = name_en = name_kana = name_ja = None
    if name_block:
        children = [c for c in name_block.children if hasattr(c, "get")]
        for child in children:
            classes = " ".join(child.get("class", []))
            text = el_text(child)
            if "mb-1.5" in classes and child.name == "div":
                role = text
            elif child.name == "h1":
                name_ja = text
            elif "mb-5" in classes and child.name == "div" and text:
                parts = text.split(" ／ ", 1)
                name_en = parts[0].strip() if parts else None
                name_kana = parts[1].strip() if len(parts) > 1 else None

    details = {}
    for dl in header.select(".MemberHeader__detail"):
        dt = dl.select_one("dt")
        dd = dl.select_one("dd")
        if not (dt and dd):
            continue
        key = el_text(dt)
        # skip color dd (handled separately)
        if "MemberHeader__color" in " ".join(dd.get("class", [])):
            continue
        val = el_text(dd)
        if key and val:
            details[key] = val

    color = None
    color_dd = header.select_one("dd.MemberHeader__color")
    if color_dd:
        color_name = el_text(color_dd)
        style = color_dd.get("style", "")
        hex_match = re.search(r"background-color:\s*(#[0-9a-fA-F]{3,6})", style)
        color = {"name": color_name, "hex": hex_match.group(1) if hex_match else None}

    images = [
        img["src"]
        for img in header.select(".MemberHeader__images img")
        if "/upload/images/" in img.get("src", "")
    ]
    # deduplicate preserving order
    seen = set()
    images = [x for x in images if not (x in seen or seen.add(x))]

    result = {
        "id": member_id,
        "url": f"/{group_slug}/{member_slug}/",
        "slug": member_slug,
        "group": group_slug,
        "nameJa": name_ja,
        "nameEn": name_en,
        "nameKana": name_kana,
        "images": images,
    }
    if role:
        result["role"] = role
    if color:
        result["color"] = color
    if details:
        result["details"] = details
    return result


def scrape_member_one(member: dict, force: bool):
    member_id = member["id"]
    group_slug = member["group_slug"]
    member_slug = member["member_slug"]

    out_file = MEMBERS_DIR / f"{member_id}.json"
    if out_file.exists() and not force:
        if DEBUG:
            print(f"  {member_slug}: already exists, skipping")
        return

    cache_file = MEMBERS_CACHE_DIR / f"{member_slug}.html"
    if cache_file.exists() and not force:
        html = cache_file.read_text(encoding="utf-8")
    else:
        resp = fetch(f"{SITE_URL}/{group_slug}/{member_slug}/")
        html = resp.text
        MEMBERS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(html, encoding="utf-8")

    data = parse_member_html(member_id, group_slug, member_slug, html)

    for path in data.get("images", []):
        download_image(path)

    # Preserve images added by archiver.py (historical Wayback photos)
    if out_file.exists():
        existing = json.loads(out_file.read_text(encoding="utf-8"))
        existing_imgs = existing.get("images", [])
        new_imgs = data.get("images", [])
        known = set(new_imgs)
        extra = [i for i in existing_imgs if i not in known]
        if extra:
            data["images"] = new_imgs + extra

    # Drop Wayback JPGs superseded by a live WebP with the same stem; transplant ts
    def _img_url(i): return i if isinstance(i, str) else i["url"]
    jpg_ts: dict[str, str] = {}
    for i in data.get("images", []):
        url = _img_url(i)
        if url.endswith(".jpg"):
            ts = i.get("ts") if isinstance(i, dict) else None
            stem = Path(url).stem
            if ts and (stem not in jpg_ts or ts < jpg_ts[stem]):
                jpg_ts[stem] = ts
    webp_stems = {Path(_img_url(i)).stem for i in data.get("images", []) if _img_url(i).endswith(".webp")}
    if webp_stems & jpg_ts.keys():
        result = []
        for i in data["images"]:
            url = _img_url(i)
            stem = Path(url).stem
            if url.endswith(".jpg") and stem in webp_stems:
                continue
            if url.endswith(".webp") and stem in jpg_ts:
                obj = i if isinstance(i, dict) else {"url": i}
                result.append(obj if obj.get("ts") else {**obj, "ts": jpg_ts[stem]})
            else:
                result.append(i)
        data["images"] = result

    MEMBERS_DIR.mkdir(exist_ok=True)
    save_json(data, out_file)
    print(f"  {member_slug}: written to {out_file}")


def cmd_members(args):
    all_members = collect_members()

    if args.id:
        members = [m for m in all_members if m["id"] == args.id]
        if not members:
            print(f"Member ID {args.id} not found in artist_list.json")
            return
    elif args.name:
        members = [m for m in all_members if m["member_slug"] == args.name]
        if not members:
            print(f"Member '{args.name}' not found in artist_list.json")
            return
    elif args.group:
        members = [m for m in all_members if m["group_slug"] == args.group]
        if not members:
            print(f"No members found for group '{args.group}'")
            return
    else:
        members = all_members

    print(f"Scraping {len(members)} member(s)...")
    for member in members:
        scrape_member_one(member, args.force)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="scraper.py")
    parser.add_argument("--debug", action="store_true", help="Print each URL fetched")
    sub = parser.add_subparsers(dest="command", required=True)

    p_update = sub.add_parser("update", help="Download catalogue JSONs and images")
    p_update.add_argument("--all-years", action="store_true", dest="all_years",
                          help="Fetch all years (default: current + next only)")

    p_scrape = sub.add_parser("scrape", help="Scrape release detail pages")
    p_scrape.add_argument("--id", type=int, help="Scrape a single release ID")
    p_scrape.add_argument("--year", type=int, help="Scrape all releases from a given year")
    p_scrape.add_argument("--force", action="store_true", help="Re-fetch even if cached")

    p_members = sub.add_parser("members", help="Scrape member profile pages")
    p_members.add_argument("--id", type=int, help="Scrape a single member by profile ID")
    p_members.add_argument("--name", help="Scrape a single member by slug (e.g. sakura_oda)")
    p_members.add_argument("--group", help="Scrape all members of a group (e.g. morningmusume)")
    p_members.add_argument("--force", action="store_true", help="Re-fetch even if cached")

    args = parser.parse_args()
    global DEBUG
    DEBUG = args.debug
    {"update": cmd_update, "scrape": cmd_scrape, "members": cmd_members}[args.command](args)


if __name__ == "__main__":
    main()
