# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraper for [helloproject.com](https://helloproject.com) that downloads catalogue data (artists, releases) and scrapes individual release pages into structured JSON. `scraper.py` handles current content; `archiver.py` handles former members (via Wayback Machine) and up-front-works.jp releases.

## Commands

```bash
# Download catalogue JSONs and cover images from the site's JSON API
py scraper.py update

# Scrape all release detail pages found in releases/*_releases.json
py scraper.py scrape

# Scrape a single release
py scraper.py scrape --id 7506

# Scrape all releases from a given year
py scraper.py scrape --year 2025

# Re-fetch even if already cached
py scraper.py scrape --year 2025 --force

# Show every URL fetched + image SKIP/FETCH
py scraper.py --debug scrape --id 7506

# Scrape current member profiles
py scraper.py members
py scraper.py members --group morningmusume
py scraper.py members --name sakura_oda
py scraper.py members --id 42
py scraper.py members --force
```

```bash
# Discover former member slugs (Wayback Machine)
py archiver.py discover --source helloproject --era html
py archiver.py discover --source helloproject --era pre-html --group morningmusume

# Fetch former member profiles
py archiver.py fetch --source helloproject --era html
py archiver.py fetch --source helloproject --era html --slug sayumi_michishige

# Fetch up-front-works releases + artists
py archiver.py discover --source upfront
py archiver.py fetch --source upfront

# Merge archived images into current member files
py archiver.py enrich --images

# Consolidate staging data into members/<id>.json
py archiver.py consolidate [--slug SLUG] [--force]
```

Use `py` on Windows (Python Launcher). `USER_AGENT` env var overrides the default Chrome UA.

## Data layout

All generated — not committed to git:

```
releases/
  version.json              # API version string + releaseYears[]
  artist_list.json          # artistsById, profilesById (images, releases per artist)
  <year>_releases.json      # flat list of releases for that year (items[])
  <id>.json                 # scraped release detail (one per HP release page)
  upfront/
    <code>.json             # scraped UFW release detail
  barcodes.json             # dict[catalogNo, { jan?, cdjapan?, ... }]
members/
  <id>.json                 # current member profile (scraper.py) or consolidated (archiver consolidate)
  artist_registry.json      # nameJa → { slug, eras: { html, pre-html, upfront } }
  staging/
    html/                   # raw Wayback 2014–2025 (archiver fetch --era html)
      <slug>.json
    pre-html/               # raw Wayback 2012–2014 (archiver fetch --era pre-html)
      <slug>.json
    flash/                  # raw Wayback ≤2011 (future)
    upfront/                # raw UFW artists (archiver fetch --source upfront --artists)
      <slug>.json
cache/
  members/
    html/                   # HTML cache for Wayback html-era fetches
    pre-html/               # HTML cache for Wayback pre-html fetches
    current/                # HTML cache for current scraper.py member pages
  releases/
    hp/                     # HTML cache for helloproject.com release pages
    upfront/                # HTML cache for up-front-works.jp pages
  cdjapan/
  cdx_member_index.json     # CDX snapshot index (slug → captures list)
images/
  <hash>.webp               # all downloaded images, named by hash
```

## Two-step workflow (scraper.py)

1. **`update`** hits the site's JSON API (`/json/<version>/`) — no HTML parsing. Downloads `version.json`, `artist_list.json`, all `<year>_releases.json`, and the cover images referenced in those files.

2. **`scrape`** reads release IDs from `releases/*_releases.json`, fetches `/release/<id>/` HTML pages, parses them with BeautifulSoup, and writes `releases/<id>.json`. HTML is cached in `cache/releases/hp/` so re-parsing doesn't re-fetch.

## archiver.py workflow

- **discover** — builds former member slug lists from Wayback CDX or UFW live site; writes to `members/former_discovered.json` or `members/artist_registry.json`
- **fetch** — fetches Wayback snapshots and parses profiles; writes to `members/staging/<era>/<slug>.json`
- **consolidate** — merges staging data (html + pre-html + upfront) into `members/<id>.json`

## Release JSON structure (`releases/<id>.json`)

```json
{
  "id": 7506,
  "url": "/release/7506/",
  "title": "...",
  "category": "CDシングル",
  "artist": "Juice=Juice",
  "releaseDate": "2025.10.8",
  "label": "hachama",
  "images": ["/upload/images/<hash>.webp"],
  "editions": [
    {
      "name": "【初回生産限定盤A】",
      "image": "/upload/images/<hash>.webp",
      "price": "￥2,090（税抜価格 ￥1,900）",
      "note": "BD付",
      "discs": [
        {
          "type": "CD",
          "catalogNo": "HKCN-50852",
          "tracks": [
            {
              "index": 1,
              "title": "四の五の言わず颯と別れてあげた",
              "suffix": "(Instrumental)",
              "duration": "03:35",
              "credits": { "作詞": "大森祥子", "作曲": "KOUGA" }
            }
          ]
        }
      ]
    }
  ]
}
```

- `images` — gallery images from the carousel (always present, one per edition for CDシングル/albums, one for photo books/books/DVD/BD/VHS/MD)
- `editions` — empty `[]` for releases with no edition blocks (写真集, 書籍)
- `editions[].name` — `null` for single-edition releases (DVD, BD, VHS, MD)
- `editions[].note` — optional, e.g. bonus content description
- `track.suffix` — optional, e.g. `"(Instrumental)"`, `"(Music Video)"`
- `track.credits` — optional, omitted when empty

## Known release categories

CDシングル, CDアルバム, DVD, DVDシングルV, BD, MDアルバム, VHS, 写真集, 書籍. The parser handles all of them with the same code path.

## artist_list.json structure (key fields)

- `artistOrder` — ordered list of group IDs in official H!P order
- `artistsById` — `{ id: { artistType, slug } }` — no name field here
- `profilesById` — `{ id: { nameJa, nameEn, nameKana, slug, images, … } }` — names live here
- `artistRelation` — `{ group_id: [ { kind: "member"|"unit", id } ] }` — kind `"unit"` means sub-group (e.g. BEYOOOOONDS → CHICA#TETSU, 雨ノ森 川海, SeasoningS)

Always resolve names from `profilesById[id].nameJa/nameEn`, not from `artistsById`.

## artist_registry.json structure

```json
{
  "高橋愛": {
    "slug": "takahashi_ai",
    "eras": {
      "html":     { "group": "morningmusume", "firstSeen": "20140424", "lastSeen": "20141005" },
      "pre-html": { "group": "morningmusume" },
      "upfront":  { "slug": "takahashi_ai" }
    }
  }
}
```

Keys are `nameJa` (NFKC-normalized). Built by migration script and updated by `archiver.py discover/fetch`.

## Pitfalls

- Some older `<year>_releases.json` files contain unescaped control characters that break `json.loads()`. `update` saves the raw text regardless and warns if it can't parse for image extraction.
- All paths are relative to the working directory — run scripts from the scraper repo root.
- `collect_ids` reads from `releases/*_releases.json`; run `update` first if those files are missing.
- Names are **not** in `artistsById` — always read from `profilesById[id].nameJa` or `nameEn`.
- Groups with `kind: "unit"` relations (like BEYOOOOONDS) require recursive resolution to get actual members.
- `archiver.py fetch --source helloproject --era html` writes to `members/staging/html/<slug>.json`, not `members/<id>.json`.
