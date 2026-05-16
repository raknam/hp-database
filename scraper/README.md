# scraper

Two scripts to build a local JSON database of Hello! Project releases and member profiles.

All commands run from the `scraper/` directory with `py` (Windows Python Launcher).

---

## Setup

Dependencies are in the root `requirements.txt`. Install once from the repo root:

```
py -m pip install -r requirements.txt
```

---

## `scraper.py` — live site (helloproject.com)

Targets the current live site and its JSON API. Covers all releases and active member profiles.

### Workflow

```
py scraper.py update     # step 1 — download catalogue JSONs + cover images
py scraper.py scrape     # step 2 — scrape individual release pages
py scraper.py members    # step 3 — scrape active member profiles
```

### `update`

Hits the site's JSON API (`/json/<version>/`). No HTML parsing. Downloads:
- `releases/version.json`
- `releases/artist_list.json`
- `releases/<year>_releases.json` for all years
- Cover images → `images/<hash>.webp`

```
py scraper.py update
```

### `scrape`

Reads release IDs from `releases/*_releases.json`, fetches `/release/<id>/` HTML, writes `releases/<id>.json`. HTML is cached in `cache/` so re-runs are incremental.

```
py scraper.py scrape                     # all releases
py scraper.py scrape --id 7506           # single release
py scraper.py scrape --year 2025         # one year
py scraper.py scrape --year 2025 --force # ignore cache, re-fetch
py scraper.py --debug scrape --id 7506   # verbose output
```

### `members`

Scrapes `/{group}/{slug}/` profile pages for every active member in `artist_list.json`. Writes `members/<id>.json`.

```
py scraper.py members                          # all active members
py scraper.py members --group morningmusume    # one group
py scraper.py members --name sakura_oda        # one member by slug
py scraper.py members --id 42                  # one member by ID
py scraper.py members --force                  # re-fetch even if cached
```

### Output layout

```
releases/
  version.json              API version + releaseYears[]
  artist_list.json          artistsById, profilesById, artistRelation
  <year>_releases.json      flat list of releases for that year
  <id>.json                 scraped release detail

members/
  <id>.json                 active member profile

cache/
  <id>.html                 raw HTML cache (releases)

images/
  <hash>.webp               cover images, named by content hash
```

### `releases/<id>.json` structure

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

Known categories: CDシングル, CDアルバム, DVD, DVDシングルV, BD, MDアルバム, VHS, 写真集, 書籍.

### `members/<id>.json` structure (active members)

```json
{
  "id": 42,
  "slug": "sakura_oda",
  "group": "morningmusume",
  "nameJa": "小田さくら",
  "nameEn": "Oda Sakura",
  "nameKana": "オダ サクラ",
  "color": "#e60012",
  "images": ["http://img.helloproject.com/..."],
  "details": {
    "生年月日": "1999年3月12日",
    "血液型": "A型",
    "出身地": "東京都"
  }
}
```

---

## `archiver.py` — web.archive.org (former/graduated members)

Fetches **archived snapshots of helloproject.com** from web.archive.org to recover profiles of graduated members no longer on the live site.

Does **not** modify any files produced by `scraper.py`.

### Workflow

```
py archiver.py discover    # step 1 — find former member slugs → members/former_discovered.json
py archiver.py fetch       # step 2 — scrape archived profiles  → members/<id>.json
```

### Site eras covered

| Era | Period | URL pattern | Encoding |
|-----|--------|-------------|----------|
| **HTML v1** | Apr 24 2014 → Jan 2025 | `/{group}/profile/{slug}/` | UTF-8 |
| **Pré-HTML** | before Apr 24 2014 | `/{group}/profile.html?id={id}` | Shift-JIS |

The Wayback CDX API is queried with `collapse=digest` to retrieve only content-distinct snapshots (~15–25 per group over 10 years).

### `discover`

Queries web.archive.org for historical group list pages, unions all members seen across all snapshots, subtracts current active members → former members only.

```
py archiver.py discover                        # all known groups
py archiver.py discover --group morningmusume  # one group
py archiver.py discover --force                # re-fetch cached pages
```

Groups covered by default: all groups from `artist_list.json` + dissolved groups (`berryzkobo`, `c-ute`, `smileage`).

Result: `members/former_discovered.json`

```json
{
  "morningmusume": [
    {
      "slug": "ayumi_ishida",
      "group": "morningmusume",
      "era": "html_v1",
      "nameJa": "石田亜佑美",
      "nameKana": "イシダ アユミ",
      "thumbnail": "http://cdn.helloproject.com/img/...",
      "details": { "生年月日": "1997年1月7日", "血液型": "O型", "出身地": "宮城県" },
      "firstSeen": "20140424",
      "lastSeen": "20241005"
    }
  ]
}
```

### `fetch`

For each discovered former member, fetches their individual archived profile page from web.archive.org and writes `members/<id>.json`.

```
py archiver.py fetch                           # all discovered former members
py archiver.py fetch --group morningmusume     # one group
py archiver.py fetch --slug ayumi_ishida       # one member by slug
py archiver.py fetch --force                   # re-fetch even if cached
```

### `members/<id>.json` structure (former members)

Same format as active members, with additional archive metadata:

```json
{
  "id": 942837,
  "slug": "ayumi_ishida",
  "group": "morningmusume",
  "nameJa": "石田亜佑美",
  "nameKana": "イシダ アユミ",
  "images": ["http://img.helloproject.com/..."],
  "details": {
    "生年月日": "1997年1月7日",
    "血液型": "O型",
    "出身地": "宮城県",
    "ハロー！プロジェクト加入": "2011年"
  },
  "archived": true,
  "archivedTimestamp": "20241005122221",
  "archivedUrl": "https://web.archive.org/web/20241005122221/..."
}
```

Fields absent depending on era:

| Field | HTML v1 | Pré-HTML |
|-------|:-------:|:--------:|
| `color` | — | — |
| `nameEn` | — | — |
| `nameKana` | yes | — |
| `生年月日` / `血液型` / `出身地` | yes | — |

IDs for former members are synthetic (range `900000–999998`), stable, and derived from the slug.

### Output layout

```
members/
  former_discovered.json        intermediate discovery index
  <id>.json                     former member profile (id >= 900000)

cache/
  archive/
    <group>_list_<ts>.html      cached group list snapshots
    <slug>_profile_<ts>.html    cached individual profile snapshots
```

### Notes

- **Rate limiting**: 1.5 s between every request to web.archive.org. Expect 3–5 min per group for `discover`.
- **Partial failures**: if Wayback refuses or times out on specific snapshots, they are skipped with a warning. Discovery still succeeds from the other snapshots.
- **Pre-2014 members** (e.g. Takahashi Ai, Mitsui Aika) are in the pré-HTML era and require a separate discovery pass once that era is implemented.
