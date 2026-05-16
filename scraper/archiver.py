#!/usr/bin/env python3
"""
archiver.py — scrape former H!P member profiles and up-front-works releases

Commands:
  discover [--source SRC] [--era ERA] [--group GROUP]
           [--year-from YEAR] [--year-to YEAR] [--force]
  fetch    [--source SRC] [--era ERA] [--slug SLUG] [--group GROUP]
           [--catalog CODE] [--force]

Sources / eras:
  helloproject / html      (Apr 2014 → Jan 2025, via Wayback Machine)
  helloproject / pre-html  (before Apr 2014, Shift-JIS, via Wayback Machine)
  upfront      / html      (up-front-works.jp, live site, 1998 → present)
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WAYBACK    = "https://web.archive.org"
CDX_API    = f"{WAYBACK}/cdx/search/cdx"
HP_URL     = "http://helloproject.com"
UFW_URL    = "https://www.up-front-works.jp"

CACHE_DIR           = Path("cache") / "archive"
UFW_CACHE_DIR       = Path("cache") / "upfront"
CDJAPAN_CACHE_DIR   = Path("cache") / "cdjapan"
MEMBERS_DIR         = Path("members")
RELEASES_DIR        = Path("releases")
UFW_RELEASES_DIR    = RELEASES_DIR / "upfront"
IMAGES_DIR          = Path("images")
DISCOVERED_FILE          = MEMBERS_DIR / "former_discovered.json"
UFW_DISCOVERED_FILE      = RELEASES_DIR / "upfront_discovered.json"
UFW_ARTISTS_DISCOVERED_FILE = MEMBERS_DIR / "ufw_artists_discovered.json"
BARCODES_FILE            = RELEASES_DIR / "barcodes.json"
CDX_INDEX_FILE           = Path("cache") / "cdx_member_index.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

RATE_LIMIT          = 3.0  # seconds between Wayback requests
UFW_RATE_LIMIT      = 1.0  # seconds between up-front-works live requests
CDJAPAN_RATE_LIMIT  = 0.0  # seconds between cdjapan.co.jp requests
CDJAPAN_URL         = "https://www.cdjapan.co.jp"
UFW_PAGE_SIZE  = 20
UFW_YEAR_FROM  = 1998
UFW_YEAR_TO    = 2026

# HTML v1 era: Apr 24 2014 → Jan 1 2025
ERA_V1_FROM = "20140424"
ERA_V1_TO   = "20250101"

# Groups no longer in current artist_list.json
FORMER_GROUP_SLUGS = ["berryzkobo", "c-ute", "smileage", "countrygirls"]

# UFW slugs that are groups but not in HP artist_list.json
UFW_NON_HP_GROUP_SLUGS: set[str] = {
    "upupgirlskakkokari",  # アップアップガールズ（仮）
    "sharam_q",            # シャ乱Q
    "brothers5",           # ブラザーズ5
}

# Known (source, era) combinations
SOURCE_ERAS: dict[str, list[str]] = {
    "helloproject": ["html", "pre-html"],
    "upfront":      ["html"],
}

DEBUG = False

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_last_request: float = 0.0
_cdx_index: dict[str, list[dict]] | None = None


def load_cdx_index() -> dict[str, list[dict]]:
    global _cdx_index
    if _cdx_index is None:
        _cdx_index = json.loads(CDX_INDEX_FILE.read_text(encoding="utf-8")) if CDX_INDEX_FILE.exists() else {}
    return _cdx_index


def short_err(e: Exception) -> str:
    s = str(e)
    if "WinError 10061" in s or "Connection refused" in s:
        return "connection refused"
    if "timed out" in s.lower() or "timeout" in s.lower():
        return "timeout"
    return s.split("\n")[0][:120]


def el_text(el) -> str | None:
    return re.sub(r"\s+", " ", el.get_text()).strip() if el else None


# ---------------------------------------------------------------------------
# Wayback Machine helpers
# ---------------------------------------------------------------------------

def cdx_search(url: str, **kwargs) -> list[dict]:
    params = {
        "url": url,
        "output": "json",
        "fl": "timestamp,digest,statuscode",
        "filter": "statuscode:200",
        **kwargs,
    }
    if DEBUG:
        print(f"  CDX  {url}")
    for attempt in range(4):
        try:
            resp = requests.get(CDX_API, params=params, headers=HEADERS, timeout=60)
            if resp.status_code in (429, 503, 504):
                wait = 15 * (attempt + 1)
                print(f"  CDX {resp.status_code}, waiting {wait}s… ({attempt + 1}/4)")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            rows = resp.json()
            if not rows or len(rows) < 2:
                return []
            keys = rows[0]
            return [dict(zip(keys, row)) for row in rows[1:]]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < 3:
                wait = 10 * (attempt + 1)
                print(f"  CDX error, waiting {wait}s… ({attempt + 2}/4)")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("CDX API unavailable after 4 attempts")


def wayback_fetch(url: str, timestamp: str) -> bytes:
    global _last_request
    elapsed = time.time() - _last_request
    if elapsed < RATE_LIMIT:
        time.sleep(RATE_LIMIT - elapsed)
    wb_url = f"{WAYBACK}/web/{timestamp}if_/{url}"
    if DEBUG:
        print(f"  FETCH {wb_url}")
    for attempt in range(3):
        try:
            resp = requests.get(wb_url, headers=HEADERS, timeout=(8, 30), allow_redirects=True)
            _last_request = time.time()
            resp.raise_for_status()
            return resp.content
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            _last_request = time.time()
            if attempt < 2:
                time.sleep(10 * (attempt + 1))
            else:
                raise
    raise RuntimeError("unreachable")


def get_cached(cache_key: str, url: str, timestamp: str,
               encoding: str = "utf-8", force: bool = False) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.html"
    if cache_file.exists() and not force:
        if DEBUG:
            print(f"  CACHE {cache_key}")
        return cache_file.read_bytes().decode(encoding, errors="replace")
    raw = wayback_fetch(url, timestamp)
    cache_file.write_bytes(raw)
    return raw.decode(encoding, errors="replace")


def slug_to_id(slug: str) -> int:
    """Stable synthetic ID in range 900000–999998, collision-free for ~200 members."""
    h = int(hashlib.md5(slug.encode()).hexdigest()[:8], 16)
    return 900000 + (h % 99999)


def ufw_slug_to_id(slug: str) -> int:
    """Stable synthetic ID in range 800000–899998 for UFW artists."""
    h = int(hashlib.md5(("ufw:" + slug).encode()).hexdigest()[:8], 16)
    return 800000 + (h % 99999)


def download_image(wb_url: str) -> str | None:
    """Download a Wayback image URL to images/. Returns local filename or None on failure."""
    m = re.search(r'if_/(https?://.+)', wb_url)
    if not m:
        return None
    original = m.group(1)
    filename = Path(original.split("?")[0]).name
    if not filename or "." not in filename:
        return None
    IMAGES_DIR.mkdir(exist_ok=True)
    dest = IMAGES_DIR / filename
    if dest.exists():
        return filename
    try:
        raw = wayback_fetch(original.replace("http://", "https://", 1)
                            if original.startswith("http://") else original,
                            re.search(r'/web/(\d+)if_/', wb_url).group(1))
        dest.write_bytes(raw)
        return filename
    except Exception as e:
        if DEBUG:
            print(f"    Image download failed ({filename}): {e}")
        return None


def clean_wayback_src(src: str) -> str:
    """Strip Wayback rewrite prefix from image/resource URLs."""
    m = re.match(r'https?://web\.archive\.org/web/\d+[a-z_]*/(.+)', src)
    return m.group(1) if m else src


def extract_slug_v1(href: str) -> str | None:
    """Extract member slug from /…/profile/{slug}/ href (raw or Wayback-rewritten)."""
    m = re.search(r'/profile/([^/?#\s]+)/?(?:\s|$)', href + " ")
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Live HTTP helpers (up-front-works.jp)
# ---------------------------------------------------------------------------

_last_live_req: float = 0.0


def live_fetch(url: str) -> bytes:
    global _last_live_req
    elapsed = time.time() - _last_live_req
    if elapsed < UFW_RATE_LIMIT:
        time.sleep(UFW_RATE_LIMIT - elapsed)
    if DEBUG:
        print(f"  FETCH {url}")
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=(8, 30), allow_redirects=True)
            _last_live_req = time.time()
            if resp.status_code in (429, 503):
                wait = 15 * (attempt + 1)
                print(f"  HTTP {resp.status_code}, waiting {wait}s… ({attempt + 1}/3)")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.content
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            _last_live_req = time.time()
            if attempt < 2:
                print(f"  Retry {attempt + 2}/3 — {short_err(e)}")
                time.sleep(10 * (attempt + 1))
            else:
                raise
    raise RuntimeError("unreachable")


_last_cdjapan_req: float = 0.0


def get_cached_cdjapan(catalog_no: str, force: bool = False) -> str | None:
    global _last_cdjapan_req
    CDJAPAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = re.sub(r"[^A-Za-z0-9_-]", "_", catalog_no)
    path = CDJAPAN_CACHE_DIR / f"{safe_key}.html"
    if path.exists() and not force:
        return path.read_text(encoding="utf-8", errors="replace")
    elapsed = time.time() - _last_cdjapan_req
    if elapsed < CDJAPAN_RATE_LIMIT:
        time.sleep(CDJAPAN_RATE_LIMIT - elapsed)
    url = f"{CDJAPAN_URL}/product/{catalog_no}"
    if DEBUG:
        print(f"  CDJAPAN {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=(8, 30), allow_redirects=True)
        _last_cdjapan_req = time.time()
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        path.write_bytes(resp.content)
        return resp.content.decode("utf-8", errors="replace")
    except Exception as e:
        _last_cdjapan_req = time.time()
        if DEBUG:
            print(f"  CDJapan error ({catalog_no}): {short_err(e)}")
        return None


def extract_jan(html: str) -> str | None:
    m = re.search(r'gtin13[^>]*content="(\d{13})"', html)
    return m.group(1) if m else None


def collect_all_catalog_nos() -> tuple[list[str], dict[str, str]]:
    """Collect catalog numbers from HP + UFW releases.

    Returns:
        codes       — catalog numbers to fetch from CDJapan
        isbn_map    — {catalogNo: jan} derived directly from ISBN-13 (no CDJapan needed)
    """
    codes: list[str] = []
    seen: set[str] = set()
    isbn_map: dict[str, str] = {}

    def add(c: str):
        if c and c not in seen:
            seen.add(c)
            codes.append(c)

    # HP releases
    for p in RELEASES_DIR.glob("*.json"):
        if not re.fullmatch(r"\d+", p.stem):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cat  = data.get("catalogNo")
            isbn = data.get("isbn")
            if cat and isbn:
                jan = re.sub(r"[^0-9]", "", isbn)
                if len(jan) == 13:
                    isbn_map[cat] = jan
                    seen.add(cat)
                    continue
            for ed in data.get("editions", []):
                for disc in ed.get("discs", []):
                    add(disc.get("catalogNo"))
            add(cat)
        except Exception:
            pass

    # UFW releases
    for p in UFW_RELEASES_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for ed in data.get("editions", []):
                for disc in ed.get("discs", []):
                    add(disc.get("catalogNo"))
        except Exception:
            pass

    return codes, isbn_map


def load_barcodes() -> dict[str, str]:
    if BARCODES_FILE.exists():
        return json.loads(BARCODES_FILE.read_text(encoding="utf-8"))
    return {}


def save_barcodes(data: dict[str, str]):
    RELEASES_DIR.mkdir(exist_ok=True)
    BARCODES_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )


def cmd_enrich_images(args):
    """Merge Wayback historical images into current member profiles (no has_grad)."""
    cdx_idx = load_cdx_index()

    targets = []
    for p in sorted(MEMBERS_DIR.glob("*.json")):
        if not re.fullmatch(r"\d+", p.stem):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or d.get("has_grad") or d.get("source") == "upfront":
            continue
        slug_url = d.get("url", "")
        m = re.match(r'^/([^/]+)/(?:profile/)?([^/]+)/?$', slug_url)
        if not m:
            continue
        targets.append({"path": p, "data": d, "group": m.group(1), "slug": m.group(2)})

    if args.slug:
        targets = [t for t in targets if t["slug"] == args.slug]

    print(f"Enriching images for {len(targets)} current member(s)…")
    for t in targets:
        slug  = t["slug"]
        group = t["group"]
        data  = t["data"]
        p     = t["path"]

        print(f"  {slug}…", end=" ", flush=True)

        url = f"{HP_URL}/{group}/profile/{slug}/"
        if slug in cdx_idx:
            captures = cdx_idx[slug]
        else:
            try:
                captures = cdx_search(url, collapse="digest",
                                      **{"from": ERA_V1_FROM, "to": ERA_V1_TO})
            except RuntimeError as e:
                print(f"CDX unavailable, skipping ({e})")
                continue

        if not captures:
            print("no snapshot found, skipping")
            continue

        all_images: list[str] = []
        seen_imgs: set[str] = set()
        for cap in captures:
            ts = cap["timestamp"]
            try:
                html = get_cached(f"{slug}_profile_{ts}", url, ts, force=args.force)
            except Exception as e:
                print(f"\n    Warning: {ts} — {short_err(e)}")
                continue
            parsed = parse_member_profile_v1(html)
            for img in parsed.get("images", []):
                if img not in seen_imgs:
                    seen_imgs.add(img)
                    all_images.append(f"{WAYBACK}/web/{ts}if_/{img}")

        for wb_img in all_images:
            download_image(wb_img)

        existing_imgs = data.get("images", [])
        known = set(existing_imgs)
        new_imgs = [i for i in all_images if Path(i).name not in {Path(k).name for k in known}]
        if new_imgs:
            data["images"] = existing_imgs + new_imgs
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ +{len(new_imgs)} images")
        else:
            print("→ no new images")


def cmd_enrich(args):
    if args.images:
        cmd_enrich_images(args)
        return
    if args.source != "cdjapan":
        print(f"Unknown enrichment source '{args.source}'. Known: cdjapan")
        return

    barcodes        = load_barcodes()
    codes, isbn_map = collect_all_catalog_nos()
    force           = args.force

    # Inject ISBN-derived barcodes directly
    isbn_added = 0
    for cat, jan in isbn_map.items():
        if cat not in barcodes or force:
            barcodes[cat] = jan
            isbn_added += 1
    if isbn_added:
        print(f"  {isbn_added} barcode(s) derived from ISBN (photobooks/books)")

    if args.catalog:
        codes = [args.catalog]

    todo = [c for c in codes if force or c not in barcodes]
    print(f"{len(barcodes)} known barcodes, {len(todo)}/{len(codes)} to fetch from CDJapan…")

    added = 0
    for i, code in enumerate(todo, 1):
        html = get_cached_cdjapan(code, force)
        if html is None:
            if DEBUG:
                print(f"  {code}: not found on CDJapan")
            continue
        jan = extract_jan(html)
        if jan:
            barcodes[code] = jan
            added += 1
            print(f"  {code} → {jan}")
        elif DEBUG:
            print(f"  {code}: no JAN found")
        if i % 100 == 0:
            save_barcodes(barcodes)
            print(f"  [{i}/{len(todo)}] checkpoint saved")

    save_barcodes(barcodes)
    print(f"\nDone — {added} new barcode(s) added, {len(barcodes)} total in {BARCODES_FILE}")


def get_cached_ufw(cache_key: str, url: str, force: bool = False) -> str:
    UFW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = UFW_CACHE_DIR / f"{cache_key}.html"
    if path.exists() and not force:
        if DEBUG:
            print(f"  CACHE {cache_key}")
        return path.read_text(encoding="utf-8", errors="replace")
    raw = live_fetch(url)
    path.write_bytes(raw)
    return raw.decode("utf-8", errors="replace")


def download_image_live(url: str) -> str | None:
    """Download a CDN image URL to images/. No rate limit (CDN, not the main site)."""
    filename = Path(url.split("?")[0]).name
    if not filename or "." not in filename:
        return None
    IMAGES_DIR.mkdir(exist_ok=True)
    dest = IMAGES_DIR / filename
    if dest.exists():
        return filename
    try:
        resp = requests.get(url, headers=HEADERS, timeout=(8, 30))
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return filename
    except Exception as e:
        if DEBUG:
            print(f"    Image download failed ({filename}): {short_err(e)}")
        return None


# ---------------------------------------------------------------------------
# Parsers — HTML v1 (Apr 2014 → Jan 2025)
# ---------------------------------------------------------------------------

def parse_group_list_v1(html: str, group: str) -> list[dict]:
    """Parse #profile_memberlist from /{group}/profile/ page."""
    soup = BeautifulSoup(html, "html.parser")
    members = []

    for li in soup.select("ul#profile_memberlist li"):
        link = li.select_one("div.photo_box a")
        if not link:
            continue
        slug = extract_slug_v1(link.get("href", ""))
        if not slug:
            continue

        img = link.select_one("img")
        thumbnail = clean_wayback_src(img.get("src", "")) if img else None

        name_ja = name_kana = None
        name_div = li.select_one("div.name")
        if name_div:
            h4 = name_div.select_one("h4")
            name_ja = el_text(h4)
            for node in name_div.children:
                if isinstance(node, NavigableString):
                    text = node.strip()
                    if text:
                        name_kana = text
                        break

        details = {}
        dts = li.select("div.item dl dt")
        for dt in dts:
            dd = dt.find_next_sibling("dd")
            k, v = el_text(dt), el_text(dd) if dd else None
            if k and v:
                details[k] = v

        members.append({
            "slug": slug,
            "group": group,
            "nameJa": name_ja,
            "nameKana": name_kana,
            "thumbnail": thumbnail,
            "details": details,
        })

    return members


def parse_member_profile_v1(html: str) -> dict:
    """Parse /{group}/profile/{slug}/ individual page (HTML v1)."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}

    artist_text = soup.select_one("div#artist_text")
    if not artist_text:
        return result

    result["nameJa"]   = el_text(artist_text.select_one("h3"))
    result["nameKana"] = el_text(artist_text.select_one("p#yomigana"))

    details = {}
    for dt in artist_text.select("dl dt.question"):
        dd = dt.find_next_sibling("dd")
        k, v = el_text(dt), el_text(dd) if dd else None
        if k and v:
            details[k] = v
    if details:
        result["details"] = details

    photo_div = soup.select_one("div#artist_photoB") or soup.select_one("div#artist_photo")
    if photo_div:
        result["images"] = [
            clean_wayback_src(img.get("src", ""))
            for img in photo_div.select("ul.slider li img")
            if img.get("src")
        ]

    return result


# ---------------------------------------------------------------------------
# Parsers — Pré-HTML (before Apr 2014, Shift-JIS)
# ---------------------------------------------------------------------------

def parse_group_list_pre(html: str) -> list[str]:
    """Return list of short IDs ('oda', 'ishida') from /{group}/profile.html."""
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for a in soup.select("ul#profileBtn li a[href]"):
        m = re.search(r'[?&]id=([^&\s]+)', a.get("href", ""))
        if m:
            ids.append(m.group(1))
    return ids


def parse_member_profile_pre(html: str) -> dict:
    """Parse /{group}/profile.html?id={id} individual page (pré-HTML, Shift-JIS)."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict = {}

    area = soup.select_one("div#profileMainArea")
    if not area:
        return result

    h3 = area.select_one("h3")
    if h3:
        raw = el_text(h3) or ""
        result["nameJa"] = re.sub(r'[(（][^)）]*[)）].*$', '', raw).strip()

    images = []
    for img in area.select("div#profileImage img"):
        src = clean_wayback_src(img.get("src", ""))
        if src:
            images.append(src)
    if images:
        result["images"] = images

    details = {}
    for dt in area.select("dl#questionList dt"):
        dd = dt.find_next_sibling("dd")
        k, v = el_text(dt), el_text(dd) if dd else None
        if k and v:
            details[re.sub(r'^Q\.', '', k).strip()] = v
    if details:
        result["details"] = details

    return result


# ---------------------------------------------------------------------------
# Parsers — up-front-works.jp (live site, same HTML structure as HP html)
# ---------------------------------------------------------------------------

def parse_ufw_release_list(html: str) -> list[str]:
    """Return [catalog_codes] from /release/search/... listing page."""
    soup = BeautifulSoup(html, "html.parser")
    codes: list[str] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r'/release/detail/([^/?#\s]+)/', a["href"])
        if m:
            code = m.group(1)
            if code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


def parse_ufw_release_html(code: str, html: str) -> dict:
    """Parse /release/detail/{code}/ — up-front-works.jp proprietary structure."""
    soup = BeautifulSoup(html, "html.parser")

    # Title: h2.product_title direct text nodes only (nested h3.artist excluded)
    title = None
    title_el = soup.select_one("h2.product_title")
    if title_el:
        title = re.sub(r'\s+', ' ',
            " ".join(t.strip() for t in title_el.find_all(string=True, recursive=False))
        ).strip() or None

    artist   = el_text(soup.select_one("h3.artist"))
    category = None
    release_date = label = None
    for row in soup.select("table.data1 tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue
        key = el_text(cells[0])
        val = el_text(cells[1])
        if key == "ジャンル":
            category = val
        elif key == "発売日":
            release_date = val
        elif key == "レーベル":
            label = val

    # Images: primary jacket (large href), then sub-jackets
    images: list[str] = []
    primary = soup.select_one("a.jacket-box")
    if primary:
        href = primary.get("href", "")
        images.append(href if href.startswith("http") else (primary.select_one("img") or {}).get("src", ""))
    for a in soup.select("div.sub-jacket a.modal"):
        href = a.get("href", "")
        if href.startswith("http"):
            images.append(href)
    images = [i for i in images if i]

    # Editions: each h3.notes starts a block, followed by h4.genre + table.data2
    editions = []
    right = soup.select_one("#right")
    if right:
        notes_els = right.select("h3.notes")
        genre_els = right.select("h4.genre")
        data2_els = right.select("table.data2")

        for i, notes_el in enumerate(notes_els):
            raw = el_text(notes_el) or ""
            lines = [l.strip() for l in raw.replace("\n", "\n").splitlines() if l.strip()]
            first = lines[0] if lines else ""

            cat_m  = re.search(r'([A-Z]{2,6}-\d+)', first)
            catalog_no = cat_m.group(1) if cat_m else None

            price_m = re.search(r'(￥[\d,]+(?:\s*\([^)]*\))?)', first)
            price = price_m.group(1).strip() if price_m else None

            name = None
            if catalog_no and catalog_no in first:
                before = first[:first.index(catalog_no)].strip().strip('　').strip()
                name = before or None

            ed_note = None
            note_lines = [l for l in lines[1:] if l]
            if note_lines:
                ed_note = " / ".join(note_lines)

            disc_type = el_text(genre_els[i]) if i < len(genre_els) else None
            ed_image  = images[i] if i < len(images) else None

            tracks = []
            if i < len(data2_els):
                for row in data2_els[i].select("tr"):
                    classes = row.get("class") or []
                    if "head" in classes or "hide_cell" in classes:
                        continue
                    cells = row.select("td")
                    if len(cells) < 2:
                        continue
                    idx_text = el_text(cells[0]) or ""
                    try:
                        idx = int(re.sub(r'\D', '', idx_text))
                    except ValueError:
                        continue
                    track_title = el_text(cells[1]) if len(cells) > 1 else None
                    duration    = el_text(cells[2]) if len(cells) > 2 else None
                    credits = {}
                    labels_map = {3: "作詞", 4: "作曲", 5: "編曲"}
                    for ci, cname in labels_map.items():
                        v = el_text(cells[ci]) if len(cells) > ci else None
                        if v:
                            credits[cname] = v
                    track = {"index": idx, "title": track_title, "duration": duration}
                    if credits:
                        track["credits"] = credits
                    tracks.append(track)

            edition = {"name": name, "image": ed_image, "price": price,
                       "discs": [{"type": disc_type, "catalogNo": catalog_no, "tracks": tracks}]}
            if ed_note:
                edition["note"] = ed_note
            editions.append(edition)

    return {
        "code":        code,
        "url":         f"/release/detail/{code}/",
        "source":      "upfront",
        "title":       title,
        "category":    category,
        "artist":      artist,
        "releaseDate": release_date,
        "label":       label,
        "images":      images,
        "editions":    editions,
    }


# ---------------------------------------------------------------------------
# Discovery helpers — helloproject members
# ---------------------------------------------------------------------------

def load_current_slugs() -> dict[str, set[str]]:
    """Return {group_slug: {member_slug, …}} from current artist_list.json."""
    artist_file = RELEASES_DIR / "artist_list.json"
    if not artist_file.exists():
        print("Warning: releases/artist_list.json not found — run 'py scraper.py update' first")
        return {}

    data = json.loads(artist_file.read_text(encoding="utf-8"))
    artists   = data.get("artistsById", {})
    profiles  = data.get("profilesById", {})
    relations = data.get("artistRelation", {})

    result: dict[str, set[str]] = {}
    for group_id, members in relations.items():
        group_slug = artists.get(group_id, {}).get("slug")
        if not group_slug:
            continue
        slugs = set()
        for entry in members:
            if entry.get("kind") != "member":
                continue
            slug = profiles.get(str(entry["id"]), {}).get("slug")
            if slug:
                slugs.add(slug)
        result[group_slug] = slugs

    return result


def load_discovered() -> dict:
    if DISCOVERED_FILE.exists():
        return json.loads(DISCOVERED_FILE.read_text(encoding="utf-8"))
    return {}


def save_discovered(data: dict):
    MEMBERS_DIR.mkdir(exist_ok=True)
    DISCOVERED_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Discovery helpers — up-front-works releases
# ---------------------------------------------------------------------------

def load_ufw_discovered() -> list[dict]:
    if UFW_DISCOVERED_FILE.exists():
        return json.loads(UFW_DISCOVERED_FILE.read_text(encoding="utf-8"))
    return []


def save_ufw_discovered(data: list[dict]):
    RELEASES_DIR.mkdir(exist_ok=True)
    UFW_DISCOVERED_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_ufw_artists_discovered() -> list[dict]:
    if UFW_ARTISTS_DISCOVERED_FILE.exists():
        return json.loads(UFW_ARTISTS_DISCOVERED_FILE.read_text(encoding="utf-8"))
    return []


def save_ufw_artists_discovered(data: list[dict]):
    MEMBERS_DIR.mkdir(exist_ok=True)
    UFW_ARTISTS_DISCOVERED_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def parse_ufw_artist_listing(html: str) -> list[dict]:
    """Return [{slug, nameJa}] from /artist/ listing page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        m = re.match(r"^/artist/([^/]+)/$", a["href"])
        if m:
            slug = m.group(1)
            if slug in seen:
                continue
            seen.add(slug)
            name = a.get_text(strip=True)
            results.append({"slug": slug, "nameJa": name or slug})
    return results


def parse_ufw_artist_page(html: str) -> dict:
    """Parse /artist/<slug>/ — returns {nameJa, image_url, bio}."""
    soup = BeautifulSoup(html, "html.parser")
    name_el = soup.select_one("div#name-tie")
    nameJa  = el_text(name_el)
    img_el  = soup.select_one("div#leftColumn img")
    image_url = img_el["src"] if img_el and img_el.get("src") else None
    bio_el  = soup.select_one("div#rightColumn")
    bio     = el_text(bio_el) if bio_el else None
    return {"nameJa": nameJa, "image_url": image_url, "bio": bio}


def discover_ufw_artists(force: bool) -> list[dict]:
    """Fetch /artist/ listing and return [{slug, nameJa}]."""
    html = get_cached_ufw("ufw_artist_listing", f"{UFW_URL}/artist/", force)
    artists = parse_ufw_artist_listing(html)
    print(f"  {len(artists)} UFW artist(s) found")
    return artists


def _ufw_group_slugs() -> set[str]:
    """Return set of slugs that are groups (HP groups + known non-HP groups)."""
    slugs = set(UFW_NON_HP_GROUP_SLUGS)
    artist_file = RELEASES_DIR / "artist_list.json"
    if artist_file.exists():
        data = json.loads(artist_file.read_text(encoding="utf-8"))
        for aid, info in data.get("artistsById", {}).items():
            if info.get("artistType") == "group":
                s = info.get("slug")
                if s:
                    slugs.add(s)
    return slugs


def fetch_ufw_artist(rec: dict, force: bool):
    slug     = rec["slug"]
    member_id = ufw_slug_to_id(slug)
    out_file  = MEMBERS_DIR / f"{member_id}.json"

    if out_file.exists() and not force:
        if DEBUG:
            print(f"  {slug}: exists, skipping")
        return

    url = f"{UFW_URL}/artist/{slug}/"
    try:
        html = get_cached_ufw(f"ufw_artist_{slug}", url, force)
    except Exception as e:
        print(f"  {slug}: fetch error — {short_err(e)}")
        return

    profile = parse_ufw_artist_page(html)
    nameJa  = profile.get("nameJa") or rec.get("nameJa") or slug

    images: list[str] = []
    img_url = profile.get("image_url")
    if img_url:
        fn = download_image_live(img_url)
        images = [f"/images/{fn}"] if fn else [img_url]

    kind = "group" if slug in _ufw_group_slugs() else "artist"

    result: dict = {
        "id":     member_id,
        "url":    f"/artist/{slug}/",
        "slug":   slug,
        "source": "upfront",
        "kind":   kind,
        "nameJa": nameJa,
        "images": images,
    }
    bio = profile.get("bio")
    if bio:
        result["bio"] = bio

    MEMBERS_DIR.mkdir(exist_ok=True)
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {slug} → {out_file}")


# ---------------------------------------------------------------------------
# discover command — helloproject member slugs
# ---------------------------------------------------------------------------

# Site navigation slugs that are not artist slugs
_NAV_SLUGS = {"artist", "release", "releases", "special", "news", "profile",
              "about", "json", "search", "top", "en", "ja", "contact"}


def parse_artist_list_v1(html: str) -> list[str]:
    """Extract artist/group slugs from /artist page (HTML v1)."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    slugs: list[str] = []
    for a in soup.find_all("a", href=True):
        m = re.match(r'^/([a-z0-9_-]+)/?$', a["href"])
        if m:
            slug = m.group(1)
            if slug not in seen and slug not in _NAV_SLUGS:
                seen.add(slug)
                slugs.append(slug)
    return slugs


def discover_artist_slugs_v1(force: bool) -> set[str]:
    """Return all artist/group slugs ever listed on /artist (HTML v1)."""
    url = f"{HP_URL}/artist"
    print("  CDX /artist…", end=" ", flush=True)
    try:
        captures = cdx_search(url, collapse="digest",
                              **{"from": ERA_V1_FROM, "to": ERA_V1_TO})
    except RuntimeError as e:
        print(f"CDX unavailable: {e}")
        return set()
    if not captures:
        print("no captures")
        return set()
    print(f"{len(captures)} distinct version(s)")

    all_slugs: set[str] = set()
    for cap in sorted(captures, key=lambda c: c["timestamp"]):
        ts = cap["timestamp"]
        try:
            html = get_cached(f"artist_page_{ts}", url, ts, force=force)
        except Exception as e:
            print(f"    Warning: {ts} — {short_err(e)}")
            continue
        all_slugs.update(parse_artist_list_v1(html))

    return all_slugs


def dedup_by_name_ja(discovered: dict) -> dict:
    """Remove cross-group duplicates keeping the first occurrence per nameJa."""
    seen_names: set[str] = set()
    result: dict = {}
    for group, members in discovered.items():
        unique = []
        for m in members:
            name = m.get("nameJa")
            if name and name in seen_names:
                continue
            if name:
                seen_names.add(name)
            unique.append(m)
        if unique:
            result[group] = unique
    return result


def discover_group_v1(group: str, current_slugs: set[str], force: bool) -> list[dict]:
    url = f"{HP_URL}/{group}/profile/"
    print(f"  CDX {group}…", end=" ", flush=True)

    captures = cdx_search(url, collapse="digest",
                          **{"from": ERA_V1_FROM, "to": ERA_V1_TO})
    if not captures:
        print("no captures")
        return []

    print(f"{len(captures)} distinct version(s)")

    slug_data: dict[str, dict] = {}

    for cap in sorted(captures, key=lambda c: c["timestamp"]):
        ts = cap["timestamp"]
        cache_key = f"{group}_list_{ts}"
        try:
            html = get_cached(cache_key, url, ts, force=force)
        except Exception as e:
            print(f"    Warning: {ts} — {short_err(e)}")
            continue

        for m in parse_group_list_v1(html, group):
            slug = m["slug"]
            if slug not in slug_data:
                slug_data[slug] = {**m, "source": "helloproject", "era": "html", "firstSeen": ts, "lastSeen": ts}
            else:
                slug_data[slug]["lastSeen"] = ts

    former = [v for k, v in slug_data.items() if k not in current_slugs]
    print(f"    {len(former)} former member(s) found (out of {len(slug_data)} total)")
    return former


def _era_key(era_arg: str) -> str:
    return era_arg


# ---------------------------------------------------------------------------
# discover command — up-front-works releases
# ---------------------------------------------------------------------------

def discover_ufw_releases(year_from: int, year_to: int, force: bool) -> list[dict]:
    """Enumerate all release catalog codes from up-front-works.jp by year."""
    all_recs: list[dict] = []
    all_codes: set[str] = set()

    for year in range(year_from, year_to + 1):
        base_url = f"{UFW_URL}/release/search/?-s=1&g=&y={year}&m=&q="
        print(f"  {year}…", end=" ", flush=True)

        year_count = 0
        page = 1

        while True:
            url = base_url if page == 1 else f"{base_url}&p={page}"
            try:
                html = get_cached_ufw(f"ufw_list_{year}_p{page}", url, force)
            except Exception as e:
                print(f"error p{page} ({short_err(e)})")
                break

            codes = parse_ufw_release_list(html)
            for code in codes:
                if code not in all_codes:
                    all_codes.add(code)
                    all_recs.append({"code": code, "year": year})
                    year_count += 1

            if len(codes) < UFW_PAGE_SIZE:
                break
            page += 1

        print(year_count)

    return all_recs


# ---------------------------------------------------------------------------
# fetch command — helloproject member profiles
# ---------------------------------------------------------------------------

def fetch_member(member: dict, force: bool):
    slug  = member["slug"]
    group = member["group"]
    era   = member.get("era", "html")

    member_id  = slug_to_id(slug)
    out_file   = MEMBERS_DIR / f"{member_id}.json"

    # If the file exists but wasn't created by the archiver (no "has_grad" key),
    # it was written by scraper.py for a current member — still fetch Wayback
    # images and merge them in, but don't overwrite profile data.
    existing = None
    if out_file.exists():
        existing = json.loads(out_file.read_text(encoding="utf-8"))
        if existing.get("has_grad") and not force:
            print(f"  {slug}: skip")
            return

    print(f"  {slug}…", end=" ", flush=True)
    last_seen = member.get("lastSeen", ERA_V1_TO)
    if era == "html":
        url = f"{HP_URL}/{group}/profile/{slug}/"
        cdx_idx = load_cdx_index()
        if slug in cdx_idx:
            captures = cdx_idx[slug]
        else:
            first_seen = member.get("firstSeen", ERA_V1_FROM)
            try:
                captures = cdx_search(url, collapse="digest",
                                      **{"from": first_seen, "to": last_seen})
            except RuntimeError as e:
                print(f"CDX unavailable, skipping ({e})")
                return
        if not captures:
            print(f"no snapshot found, skipping")
            return

        profile: dict = {}
        all_images: list[str] = []
        seen_imgs: set[str] = set()
        best_ts = captures[-1]["timestamp"]

        for cap in captures:
            ts = cap["timestamp"]
            try:
                html = get_cached(f"{slug}_profile_{ts}", url, ts, force=force)
            except Exception as e:
                print(f"\n    Warning: {ts} — {short_err(e)}")
                continue
            p = parse_member_profile_v1(html)
            if not profile:
                profile = p
            elif not profile.get("nameJa") and p.get("nameJa"):
                profile = p
            for img in p.get("images", []):
                wb_img = f"{WAYBACK}/web/{ts}if_/{img}"
                if img not in seen_imgs:
                    seen_imgs.add(img)
                    all_images.append(wb_img)

        ts = best_ts

        for wb_img in all_images:
            download_image(wb_img)

    else:
        print(f"era '{era}' not yet implemented, skipping")
        return

    if existing and not existing.get("has_grad"):
        # Enrich scraper.py file: merge archived images only
        existing_imgs = existing.get("images", [])
        known = {Path(i).name for i in existing_imgs}
        new_imgs = [i for i in all_images if Path(i).name not in known]
        if new_imgs:
            existing["images"] = existing_imgs + new_imgs
            out_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ +{len(new_imgs)} images merged")
        else:
            print(f"→ no new images")
        return

    result = {
        "id": member_id,
        "url": f"/{group}/profile/{slug}/",
        "slug": slug,
        "group": group,
        "nameJa":   profile.get("nameJa")   or member.get("nameJa"),
        "nameKana": profile.get("nameKana") or member.get("nameKana"),
        "images":      all_images,
        "has_grad":    True,
        "archivedUrl": f"{WAYBACK}/web/{ts}/{url}",
    }

    details = {**member.get("details", {}), **profile.get("details", {})}
    if details:
        result["details"] = details

    MEMBERS_DIR.mkdir(exist_ok=True)
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {out_file}")


# ---------------------------------------------------------------------------
# fetch command — up-front-works releases
# ---------------------------------------------------------------------------

def fetch_ufw_release(rec: dict, force: bool):
    code     = rec["code"]
    out_file = UFW_RELEASES_DIR / f"{code}.json"

    if out_file.exists() and not force:
        if DEBUG:
            print(f"  {code}: exists, skipping")
        return

    url = f"{UFW_URL}/release/detail/{code}/"
    try:
        # force=False: always read from cache; re-fetch only if no cache exists
        html = get_cached_ufw(f"ufw_rel_{code}", url, False)
    except Exception as e:
        print(f"  {code}: fetch error — {short_err(e)}")
        return

    data = parse_ufw_release_html(code, html)

    # Download images and rewrite to local paths
    local_images = []
    for img_url in data.get("images", []):
        if img_url.startswith("http"):
            fn = download_image_live(img_url)
            local_images.append(f"/images/{fn}" if fn else img_url)
        else:
            local_images.append(img_url)
    data["images"] = local_images

    for edition in data.get("editions", []):
        img_url = edition.get("image")
        if img_url and img_url.startswith("http"):
            fn = download_image_live(img_url)
            if fn:
                edition["image"] = f"/images/{fn}"

    UFW_RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {code} → {out_file}")


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_prefetch_cdx(args):
    """Bulk-fetch CDX captures for all former member profile URLs.

    Does one CDX request per group instead of one per member, saving the
    results to cache/cdx_member_index.json. Subsequent 'fetch' calls use
    this index and skip the per-member CDX lookup entirely.
    """
    discovered = load_discovered()
    if not discovered:
        print("Nothing discovered yet — run 'py archiver.py discover --source helloproject' first")
        return

    groups = [args.group] if args.group else list(discovered.keys())

    # Load existing index (incremental by default)
    index: dict[str, list[dict]] = {}
    if CDX_INDEX_FILE.exists() and not args.force:
        index = json.loads(CDX_INDEX_FILE.read_text(encoding="utf-8"))
        print(f"Loaded existing index: {len(index)} slugs")

    for group in groups:
        members = discovered.get(group, [])
        if not members:
            continue

        if not args.force and all(m["slug"] in index for m in members):
            print(f"  {group}: all {len(members)} members already indexed, skipping")
            continue

        url = f"{HP_URL}/{group}/profile/"
        print(f"  CDX {group}…", end=" ", flush=True)
        try:
            captures = cdx_search(
                url,
                matchType="prefix",
                fl="original,timestamp,digest",
                collapse="digest",
                **{"from": ERA_V1_FROM, "to": ERA_V1_TO},
            )
        except RuntimeError as e:
            print(f"CDX unavailable: {e}")
            continue

        by_slug: dict[str, list[dict]] = {}
        for cap in captures:
            m = re.search(r'/profile/([^/?#]+)/?$', cap.get("original", ""))
            if not m:
                continue
            slug = m.group(1)
            by_slug.setdefault(slug, []).append({
                "timestamp": cap["timestamp"],
                "digest":    cap["digest"],
            })

        print(f"{len(by_slug)} slugs, {len(captures)} captures")
        index.update(by_slug)

    CDX_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    CDX_INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {len(index)} slugs → {CDX_INDEX_FILE}")


def cmd_discover(args):
    source_filter = args.source
    era_filter    = _era_key(args.era) if args.era else None

    if source_filter and source_filter not in SOURCE_ERAS:
        print(f"Unknown source '{source_filter}'. Known: {', '.join(SOURCE_ERAS)}")
        return

    combos = [
        (src, era)
        for src, eras in SOURCE_ERAS.items()
        for era in eras
        if (not source_filter or src == source_filter)
        and (not era_filter or era == era_filter)
    ]

    if not combos:
        print("No matching (source, era) combination — nothing to do.")
        return

    # --- helloproject member discovery ---
    hp_combos = [(s, e) for s, e in combos if s == "helloproject"]
    if hp_combos:
        current    = load_current_slugs()
        discovered = load_discovered()

        all_groups = list(current.keys()) + FORMER_GROUP_SLUGS
        if args.group:
            if args.group not in all_groups:
                print(f"Unknown group '{args.group}'. Known: {', '.join(all_groups)}")
                return
            groups = [args.group]
        else:
            groups = all_groups

        for source, era in hp_combos:
            if source == "helloproject" and era == "html":
                if args.group:
                    groups_to_scan = groups
                else:
                    artist_slugs   = discover_artist_slugs_v1(args.force)
                    groups_to_scan = sorted(set(groups) | artist_slugs)
                print(f"Discovering [{source}/{era}] across {len(groups_to_scan)} group(s)/artist(s)…")
                for group in groups_to_scan:
                    known = current.get(group, set())
                    try:
                        former = discover_group_v1(group, known, args.force)
                    except RuntimeError as e:
                        print(f"  {group}: CDX unavailable, skipping ({e})")
                        continue
                    if former:
                        existing = {m["slug"]: m for m in discovered.get(group, [])}
                        for m in former:
                            existing[m["slug"]] = m
                        discovered[group] = list(existing.values())
            else:
                print(f"  [{source}/{era}]: not yet implemented, skipping")

        discovered = dedup_by_name_ja(discovered)
        save_discovered(discovered)
        total = sum(len(v) for v in discovered.values())
        print(f"\nSaved {total} former member(s) to {DISCOVERED_FILE}")

    # --- up-front-works discovery ---
    ufw_combos = [(s, e) for s, e in combos if s == "upfront"]
    if ufw_combos:
        for source, era in ufw_combos:
            if source == "upfront" and era == "html":
                if not args.artists:
                    year_from = args.year_from or UFW_YEAR_FROM
                    year_to   = args.year_to   or UFW_YEAR_TO
                    print(f"Discovering [upfront/html] releases {year_from}–{year_to}…")
                    existing     = load_ufw_discovered()
                    existing_set = {r["code"] for r in existing}
                    new_recs     = discover_ufw_releases(year_from, year_to, args.force)
                    added        = [r for r in new_recs if r["code"] not in existing_set]
                    combined     = existing + added
                    save_ufw_discovered(combined)
                    print(f"Total {len(combined)} release(s) in {UFW_DISCOVERED_FILE} ({len(added)} new)")
                else:
                    print("Discovering [upfront/html] artists…")
                    artists      = discover_ufw_artists(args.force)
                    existing     = load_ufw_artists_discovered()
                    existing_set = {a["slug"] for a in existing}
                    added        = [a for a in artists if a["slug"] not in existing_set]
                    combined     = existing + added
                    save_ufw_artists_discovered(combined)
                    print(f"Total {len(combined)} artist(s) in {UFW_ARTISTS_DISCOVERED_FILE} ({len(added)} new)")
            else:
                print(f"  [{source}/{era}]: not yet implemented, skipping")


def cmd_fetch(args):
    # --- up-front-works artists ---
    if args.source == "upfront" and args.artists:
        disc = load_ufw_artists_discovered()
        if not disc:
            print("Nothing discovered yet — run 'py archiver.py discover --source upfront --artists' first")
            return
        if args.slug:
            targets = [a for a in disc if a["slug"] == args.slug]
            if not targets:
                print(f"Slug '{args.slug}' not found in {UFW_ARTISTS_DISCOVERED_FILE}")
                return
        else:
            targets = disc
        print(f"Fetching {len(targets)} UFW artist(s)…")
        for rec in targets:
            fetch_ufw_artist(rec, args.force)
        return

    # --- up-front-works releases ---
    if args.source == "upfront":
        ufw_disc = load_ufw_discovered()
        if not ufw_disc:
            print("Nothing discovered yet — run 'py archiver.py discover --source upfront' first")
            return
        catalog = args.catalog
        if catalog:
            targets = [r for r in ufw_disc if r["code"] == catalog]
            if not targets:
                print(f"Catalog '{catalog}' not found in {UFW_DISCOVERED_FILE}")
                return
        else:
            targets = ufw_disc
        print(f"Fetching {len(targets)} up-front-works release(s)…")
        for rec in targets:
            fetch_ufw_release(rec, args.force)
        return

    # --- helloproject member profiles ---
    discovered = load_discovered()
    if not discovered:
        print("Nothing discovered yet — run 'py archiver.py discover' first")
        return

    all_members = [m for members in discovered.values() for m in members]

    if args.slug:
        targets = [m for m in all_members if m["slug"] == args.slug]
        if not targets:
            print(f"Slug '{args.slug}' not found in former_discovered.json")
            return
    elif args.group:
        targets = discovered.get(args.group, [])
        if not targets:
            print(f"No former members found for group '{args.group}'")
            return
    else:
        targets = all_members

    if args.source:
        targets = [m for m in targets if m.get("source") == args.source]
    if args.era:
        targets = [m for m in targets if m.get("era") == _era_key(args.era)]

    if not targets:
        print("No members match the given filters.")
        return

    print(f"Fetching {len(targets)} member profile(s)…")
    for member in targets:
        fetch_member(member, args.force)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="archiver.py")
    parser.add_argument("--debug", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_disc = sub.add_parser("discover", help="Phase 1: find former member slugs or release codes")
    p_disc.add_argument("--source",    help="Source site: helloproject, upfront")
    p_disc.add_argument("--era",       help="Site era: html, pre-html")
    p_disc.add_argument("--group",     help="(helloproject) Restrict to one group slug")
    p_disc.add_argument("--year-from", type=int, dest="year_from",
                        help=f"(upfront) Start year (default {UFW_YEAR_FROM})")
    p_disc.add_argument("--year-to",   type=int, dest="year_to",
                        help=f"(upfront) End year (default {UFW_YEAR_TO})")
    p_disc.add_argument("--artists",   action="store_true", help="(upfront) Discover artists instead of releases")
    p_disc.add_argument("--force",     action="store_true", help="Re-fetch even if cached")

    p_fetch = sub.add_parser("fetch", help="Phase 2: scrape profiles or release pages")
    p_fetch.add_argument("--source",  help="Source site: helloproject, upfront")
    p_fetch.add_argument("--era",     help="(helloproject) Filter by era: html, pre-html")
    p_fetch.add_argument("--slug",    help="Fetch a single artist/member by slug")
    p_fetch.add_argument("--group",   help="(helloproject) Fetch all former members of a group")
    p_fetch.add_argument("--catalog", help="(upfront) Fetch a single release by catalog code")
    p_fetch.add_argument("--artists", action="store_true", help="(upfront) Fetch artists instead of releases")
    p_fetch.add_argument("--force",   action="store_true", help="Re-fetch even if cached")

    p_enrich = sub.add_parser("enrich", help="Enrich data from external sources")
    p_enrich.add_argument("--source",  default="cdjapan", help="Barcode source (default: cdjapan)")
    p_enrich.add_argument("--catalog", help="(barcodes) Enrich a single catalog code")
    p_enrich.add_argument("--images",  action="store_true", help="Merge Wayback images into current member profiles")
    p_enrich.add_argument("--slug",    help="(--images) Restrict to one member slug")
    p_enrich.add_argument("--force",   action="store_true", help="Re-fetch even if cached")

    p_cdx = sub.add_parser("prefetch-cdx", help="Bulk-prefetch CDX index (one request per group, not per member)")
    p_cdx.add_argument("--group", help="Restrict to one group slug")
    p_cdx.add_argument("--force", action="store_true", help="Rebuild index even if already present")

    args = parser.parse_args()
    global DEBUG
    DEBUG = args.debug

    {
        "discover":     cmd_discover,
        "fetch":        cmd_fetch,
        "enrich":       cmd_enrich,
        "prefetch-cdx": cmd_prefetch_cdx,
    }[args.command](args)


if __name__ == "__main__":
    main()
