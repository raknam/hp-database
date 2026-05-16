# Scraper — Commandes par source / ère

Tous les scripts se lancent depuis `scraper/`.

## Sources disponibles

| Source | Ère | Script | Site | Méthode |
|--------|-----|--------|------|---------|
| helloproject | current | `scraper.py` | helloproject.com | Live |
| helloproject | html | `archiver.py` | helloproject.com | Wayback Machine |
| upfront | html | `archiver.py` | up-front-works.jp | Live |

---

## helloproject — site actuel (`scraper.py`)

Données produites : `releases/`, `members/`  
Structure : [HP_CURRENT_DATA_STRUCTURE.md](HP_CURRENT_DATA_STRUCTURE.md)

```powershell
# 1. Télécharger le catalogue (version, artist_list, <year>_releases, images)
py scraper.py update

# 2. Scraper les pages de détail des releases
py scraper.py scrape                      # toutes les releases
py scraper.py scrape --year 2025          # une année
py scraper.py scrape --id 7506            # une release
py scraper.py scrape --year 2025 --force  # forcer le re-fetch

# 3. Scraper les profils des membres actifs
py scraper.py members                     # tous
py scraper.py members --group morningmusume
py scraper.py members --name fukumura_mizuki
py scraper.py members --id 201
py scraper.py members --force
```

---

## helloproject — HTML v1 (`archiver.py`, via Wayback)

Données produites : `members/former_discovered.json`, `members/<id>.json`  
Structure : [HP_HTML_DATA_STRUCTURE.md](HP_HTML_DATA_STRUCTURE.md)

```powershell
# 1. Découvrir toutes les membres graduées (Wayback CDX API)
py archiver.py discover --source helloproject --era html

# Variantes
py archiver.py discover --source helloproject --era html --group morningmusume
py archiver.py discover --source helloproject --era html --force  # re-fetch le cache

# 2. (Optionnel mais recommandé) Pré-fetcher l'index CDX en masse
#    → 1 requête par groupe au lieu de 1 par membre, évite les 503
py archiver.py prefetch-cdx
py archiver.py prefetch-cdx --group countrygirls  # un groupe seulement
py archiver.py prefetch-cdx --force               # reconstruire l'index

# 3. Scraper les profils individuels (toutes les snapshots Wayback)
py archiver.py fetch --source helloproject --era html

# Variantes
py archiver.py fetch --source helloproject --era html --group morningmusume
py archiver.py fetch --source helloproject --era html --slug sakura_oda
py archiver.py fetch --source helloproject --era html --force
```

**Notes :**
- Rate limit Wayback : 3 s entre requêtes, 60 req/min max (429 = blocage 1h).
- 503 = surcharge serveur Wayback, retries automatiques (4 tentatives, attente progressive).
- Cache HTML dans `cache/archive/`, index CDX dans `cache/cdx_member_index.json`.
- Les fichiers membres créés par `scraper.py` (membres actives) conservent leurs images quand re-fetchés.

---

## up-front-works.jp — HTML v1 (`archiver.py`, live)

Données produites : `releases/upfront_discovered.json`, `releases/upfront/<code>.json`  
Structure : [UFW_DATA_STRUCTURE.md](UFW_DATA_STRUCTURE.md)

```powershell
# 1. Découvrir tous les codes catalogue (1998–2026, ~3 100 releases)
py archiver.py discover --source upfront

# Variantes
py archiver.py discover --source upfront --year-from 2010 --year-to 2020
py archiver.py discover --source upfront --force  # re-fetch les pages listing

# 2. Scraper les pages de détail
py archiver.py fetch --source upfront

# Variantes
py archiver.py fetch --source upfront --catalog EPCE-7992  # une release
py archiver.py fetch --source upfront --force              # re-parser depuis le cache HTML
```

**Notes :**
- `--force` sur fetch re-parse le HTML mis en cache **sans** re-télécharger.
- Rate limit : 1 s entre requêtes (site live, pas de restriction stricte connue).
- Cache HTML dans `cache/upfront/`, images téléchargées dans `images/`.

---

## Enrichissement (`archiver.py enrich`)

```powershell
# Barcodes via CDJapan (codes catalogue → JAN/EAN-13, sauvegardé dans releases/barcodes.json)
py archiver.py enrich                         # tous les codes
py archiver.py enrich --catalog EPCE-7886     # un seul code
py archiver.py enrich --force                 # re-fetch même si déjà en cache

# Images historiques Wayback pour les membres actives (complète les photos de scraper.py)
py archiver.py enrich --images                # toutes les membres actives
py archiver.py enrich --images --slug ayumi_ishida  # une seule membre
py archiver.py enrich --images --force        # re-fetch depuis Wayback
```

**Notes :**
- `enrich --images` ne touche pas aux membres graduées (`has_grad: true`) — elles ont déjà leurs images Wayback.
- `enrich` (barcodes) : ISBN-13 des photobooks/livres est pré-calculé sans réseau depuis le champ `isbn` des releases.

---

## Lancer les deux sources d'un coup

```powershell
# Discover
py archiver.py discover   # helloproject html + upfront html

# Fetch
py archiver.py fetch      # helloproject membres seulement
py archiver.py fetch --source upfront
```

---

## Fichiers de données — vue d'ensemble

```
releases/
  version.json                     API version + années (HP current)
  artist_list.json                  groupes + membres actifs (HP current)
  <year>_releases.json              catalogue par année (HP current)
  <id>.json                         détail release HP (HP current)
  upfront_discovered.json           index releases UFW
  upfront/
    <CODE>.json                     détail release UFW (ex. EPCE-7992.json)

members/
  <id>.json                         profil membre (actif = ID officiel, gradué = ID synthétique)
  former_discovered.json            index membres graduées HP html

cache/
  <id>.html                         cache pages release HP
  <slug>.html                       cache pages membre HP
  archive/                          cache Wayback (membres graduées + actives)
  upfront/                          cache pages UFW
  cdjapan/                          cache pages CDJapan (barcodes)
  cdx_member_index.json             index CDX bulk (slugs → captures Wayback)

images/
  <hash>.webp / <hash>.jpg          toutes les images téléchargées
```
