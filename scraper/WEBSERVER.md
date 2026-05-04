# WEBSERVER.md

Browse scraped data at `http://localhost:8000`. No extra dependencies — stdlib only.

## Start

```bash
py server.py
py server.py --port 9000
py server.py --host 0.0.0.0 --port 8000   # expose on LAN
```

Stop with Ctrl+C. Uses a daemon thread + `join(timeout=1)` loop for reliable Ctrl+C on Windows.

## Routes

| Route | Description |
|---|---|
| `/` | Home — stats + latest year grid |
| `/groups` | All H!P groups in official `artistOrder`, with banner photo and member chips |
| `/artist/<slug>` | Group discography (catalogue + scraped releases) |
| `/members` | All scraped members sorted by birthday (oldest first) |
| `/member/<id>` | Member detail — photo, color, details table |
| `/releases` | All catalogue releases |
| `/releases/<year>` | Releases for a given year |
| `/release/<id>` | Release detail — editions, tracklists, credits |
| `/search?q=…` | Full-text search across releases and members |
| `/images/<hash>.webp` | Serve local image, fallback to helloproject.com |

## Data loaded at startup

`DataStore` loads everything into memory on boot:

- `releases/version.json` — API version + `releaseYears`
- `releases/artist_list.json` — `artistsById`, `profilesById`, `artistRelation`, `artistOrder`
- `releases/<year>_releases.json` — catalogue items per year
- `releases/<id>.json` — scraped release details
- `members/<id>.json` — scraped member profiles

Restart the server to pick up newly scraped files.

## Key design notes

- **Names**: resolved from `profilesById[id].nameJa → nameEn → slug` via `profile_name()`. `artistsById` has no name field.
- **Group member resolution**: `resolve_members(group_id)` recurses into `kind: "unit"` sub-groups (e.g. BEYOOOOONDS → its three units → their members).
- **Group order**: `artistOrder` from `artist_list.json` drives the `/groups` sort. Only entries with `artistType: "group"` in `artistsById` appear as top-level cards.
- **Birthday sort**: parses `details['生年月日']` (`1999年3月12日`) with regex.
- **Images**: served locally from `images/` if the file exists, otherwise proxied from `helloproject.com`. `Cache-Control: max-age=86400` on local images.
- **Release stubs**: catalogue items not yet scraped show basic info + a hint to run `py scraper.py scrape --id <id>`.
