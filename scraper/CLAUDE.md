# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A scraper for [helloproject.com](https://helloproject.com) that downloads catalogue data (artists, releases) and scrapes individual release pages into structured JSON. Everything lives in `scraper.py`.

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
```

Use `py` on Windows (Python Launcher). `USER_AGENT` env var overrides the default Chrome UA.

## Data layout

All generated — not committed to git:

```
releases/
  version.json          # API version string + releaseYears[]
  artist_list.json      # artistsById, profilesById (images, releases per artist)
  <year>_releases.json  # flat list of releases for that year (items[])
  <id>.json             # scraped release detail (one per release page)
cache/
  <id>.html             # raw HTML cache for scrape, avoids re-fetching
images/
  <hash>.webp           # all downloaded images, named by hash
```

## Two-step workflow

1. **`update`** hits the site's JSON API (`/json/<version>/`) — no HTML parsing. Downloads `version.json`, `artist_list.json`, all `<year>_releases.json`, and the cover images referenced in those files.

2. **`scrape`** reads release IDs from `releases/*_releases.json`, fetches `/release/<id>/` HTML pages, parses them with BeautifulSoup, and writes `releases/<id>.json`. HTML is cached in `cache/` so re-parsing doesn't re-fetch.

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

## Members scraping (`members` command)

```bash
py scraper.py members              # all members
py scraper.py members --group morningmusume
py scraper.py members --name sakura_oda
py scraper.py members --id 42
py scraper.py members --force
```

Writes `members/<id>.json`. Member slugs and group slugs come from `artist_list.json`.

## Data layout (updated)

```
members/
  <id>.json   # scraped member profile (nameJa, nameEn, nameKana, details, color, images…)
```

Member `details` dict uses Japanese keys: `生年月日` (birthday as `1999年3月12日`), `出身地`, `血液型`, etc.

## artist_list.json structure (key fields)

- `artistOrder` — ordered list of group IDs in official H!P order
- `artistsById` — `{ id: { artistType, slug } }` — no name field here
- `profilesById` — `{ id: { nameJa, nameEn, nameKana, slug, images, … } }` — names live here
- `artistRelation` — `{ group_id: [ { kind: "member"|"unit", id } ] }` — kind `"unit"` means sub-group (e.g. BEYOOOOONDS → CHICA#TETSU, 雨ノ森 川海, SeasoningS)

Always resolve names from `profilesById[id].nameJa/nameEn`, not from `artistsById`.

## Web server

See `WEBSERVER.md`. Run with `py server.py`.

## Pitfalls

- Some older `<year>_releases.json` files contain unescaped control characters that break `json.loads()`. `update` saves the raw text regardless and warns if it can't parse for image extraction.
- All paths are relative to the working directory — run the script from the repo root.
- `collect_ids` reads from `releases/*_releases.json`; run `update` first if those files are missing.
- Names are **not** in `artistsById` — always read from `profilesById[id].nameJa` or `nameEn`.
- Groups with `kind: "unit"` relations (like BEYOOOOONDS) require recursive resolution to get actual members.
