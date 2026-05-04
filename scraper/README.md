# hpdata

Scraper for [helloproject.com](https://helloproject.com). Downloads catalogue data and scrapes release pages into structured JSON, with cover images.

## Requirements

```bash
pip install requests beautifulsoup4
```

## Usage

### Step 1 — Download the catalogue

```bash
py scraper.py update
```

Fetches the site's JSON API: artist list, all yearly release catalogues, and their cover images. Output goes to `releases/` and `images/`.

### Step 2 — Scrape release detail pages

```bash
# All releases
py scraper.py scrape

# One year only
py scraper.py scrape --year 2025

# Single release
py scraper.py scrape --id 7506
```

Fetches each release page, parses editions/tracklists/credits, and writes `releases/<id>.json`. HTML pages are cached in `cache/` — re-running is incremental by default.

### Options

| Flag | Description |
|------|-------------|
| `--force` | Re-fetch and re-parse even if already cached |
| `--debug` | Print every URL fetched and every image skipped |

```bash
py scraper.py --debug scrape --year 2025 --force
```

## Output

```
releases/
  version.json          # API version metadata
  artist_list.json      # Artists and their profiles
  <year>_releases.json  # Release catalogue per year
  <id>.json             # Scraped detail for each release
images/
  <hash>.webp           # All cover images
cache/
  <id>.html             # Cached HTML pages (scrape only)
```

Each `releases/<id>.json` contains the release metadata, all editions with their tracklists and credits, and image paths.
