# SCRAPER.md — Référence complète

Remplace : `HP_CURRENT_DATA_STRUCTURE.md`, `HP_HTML_DATA_STRUCTURE.md`, `UFW_DATA_STRUCTURE.md`.  
Tous les scripts se lancent depuis `scraper/`.

---

## Arborescence complète

```
scraper/
  scraper.py               site actuel helloproject.com (live)
  archiver.py              anciennes membres (Wayback) + up-front-works.jp (live)
  migrate_structure.py     script de migration one-shot (conservé pour référence)

releases/
  version.json             version API + releaseYears[]
  artist_list.json         artistsById, profilesById, artistRelation
  <year>_releases.json     liste releases par année (items[])
  <id>.json                détail release HP (un fichier par release)
  upfront_discovered.json  index codes catalogue UFW
  upfront/
    <CODE>.json            détail release UFW (ex. EPCE-7992.json)
  barcodes.json            dict[catalogNo, { jan?, cdjapan? }]

members/
  <id>.json                profil membre : actif (scraper.py) ou consolidé (archiver consolidate)
  artist_registry.json     nameJa → { slug, eras: { html, pre-html, upfront } }
  staging/
    html/
      <slug>.json          brut Wayback 2014–2025 (archiver fetch --era html)
    pre-html/
      <slug>.json          brut Wayback 2012–2014 Shift-JIS (archiver fetch --era pre-html)
    flash/                 futur (Wayback ≤2011, Flash)
    upfront/
      <slug>.json          brut UFW artists (archiver fetch --source upfront --artists)

cache/
  members/
    html/                  HTML Wayback html-era (ex. sakura_oda_profile_20220101.html)
    pre-html/              HTML Wayback pre-html
    current/               HTML pages membres actifs (scraper.py members)
  releases/
    hp/                    HTML pages releases HP (scraper.py scrape)
    upfront/               HTML pages UFW (archiver fetch --source upfront)
  cdjapan/                 HTML pages CDJapan (archiver enrich)
  cdx_member_index.json    index CDX bulk : slug → liste captures Wayback

images/
  <hash>.webp / <hash>.jpg toutes les images téléchargées, nommées par hash
```

---

## Commandes

### scraper.py — site actuel

```powershell
# Télécharger catalogue (version, artist_list, <year>_releases, images)
py scraper.py update

# Scraper pages release HP
py scraper.py scrape                       # toutes
py scraper.py scrape --year 2025
py scraper.py scrape --id 7506
py scraper.py scrape --year 2025 --force   # re-fetch

# Scraper profils membres actifs
py scraper.py members
py scraper.py members --group morningmusume
py scraper.py members --name fukumura_mizuki
py scraper.py members --id 201
py scraper.py members --force
```

### archiver.py — anciens membres + UFW

```powershell
# --- Découverte ---
py archiver.py discover --source helloproject --era html
py archiver.py discover --source helloproject --era html --group morningmusume
py archiver.py discover --source helloproject --era pre-html
py archiver.py discover --source helloproject --era pre-html --group morningmusume
py archiver.py discover --source upfront
py archiver.py discover --source upfront --artists

# --- Pré-fetch CDX (Wayback, recommandé avant fetch html) ---
py archiver.py prefetch-cdx
py archiver.py prefetch-cdx --group countrygirls
py archiver.py prefetch-cdx --force

# --- Fetch ---
py archiver.py fetch --source helloproject --era html
py archiver.py fetch --source helloproject --era html --group morningmusume
py archiver.py fetch --source helloproject --era html --slug sakura_oda
py archiver.py fetch --source helloproject --era pre-html
py archiver.py fetch --source helloproject --era pre-html --group morningmusume
py archiver.py fetch --source upfront
py archiver.py fetch --source upfront --catalog EPCE-7992
py archiver.py fetch --source upfront --artists
py archiver.py fetch --source upfront --artists --slug natsumi_abe

# --- Enrichissement ---
py archiver.py enrich                          # barcodes CDJapan
py archiver.py enrich --catalog EPCE-7886
py archiver.py enrich --images                 # images Wayback dans membres actifs
py archiver.py enrich --images --slug ayumi_ishida

# --- Consolidation ---
py archiver.py consolidate                     # tous les membres staging → members/<id>.json
py archiver.py consolidate --slug sakura_oda
py archiver.py consolidate --force
```

---

## Schémas JSON

### `releases/<id>.json` — Release HP

```json
{
  "id":          7506,
  "url":         "/release/7506/",
  "title":       "四の五の言わず颯と別れてあげた",
  "category":    "CDシングル",
  "artist":      "Juice=Juice",
  "releaseDate": "2025.10.8",
  "label":       "hachama",
  "images":      ["/upload/images/<hash>.webp"],
  "editions": [
    {
      "name":  "【初回生産限定盤A】",
      "image": "/upload/images/<hash>.webp",
      "price": "￥2,090（税抜価格 ￥1,900）",
      "note":  "BD付",
      "discs": [
        {
          "type":      "CD",
          "catalogNo": "HKCN-50852",
          "tracks": [
            {
              "index":    1,
              "title":    "四の五の言わず颯と別れてあげた",
              "duration": "03:35",
              "suffix":   "(Instrumental)",
              "credits":  { "作詞": "大森祥子", "作曲": "KOUGA" }
            }
          ]
        }
      ]
    }
  ]
}
```

- `editions = []` pour 写真集, 書籍
- `editions[].name = null` pour releases mono-édition (DVD, BD, VHS, MD)
- `editions[].note` optionnel
- `track.suffix` optionnel
- `track.credits` omis si vide
- `images` : une par édition pour CDシングル/albums, une seule pour DVD/BD/写真集
- Catégories : CDシングル, CDアルバム, DVD, DVDシングルV, BD, MDアルバム, VHS, 写真集, 書籍

### `releases/upfront/<CODE>.json` — Release UFW

```json
{
  "code":        "EPCE-2038",
  "url":         "/release/detail/EPCE-2038/",
  "source":      "upfront",
  "title":       "入っておいで この里に",
  "category":    "CDシングル",
  "artist":      "ブラザーズ5",
  "releaseDate": "2014/10/01",
  "label":       "zetima",
  "images":      ["/images/<hash>.jpg"],
  "editions": [
    {
      "name":  "初回生産限定盤",
      "image": "/images/<hash>.jpg",
      "price": "￥1,834 (税抜価格 ￥1,667)",
      "note":  "特典：DVD付",
      "discs": [
        {
          "type":      "CDシングル",
          "catalogNo": "EPCE-2038",
          "tracks": [
            {
              "index":    1,
              "title":    "入っておいで この里に",
              "duration": "03:35",
              "credits":  { "作詞": "アメリカ民謡/日本語詞:兵頭 剛", "作曲": "アメリカ民謡" }
            }
          ]
        }
      ]
    }
  ]
}
```

Différences HP vs UFW :

| Champ       | HP (`releases/<id>.json`)           | UFW (`releases/upfront/<code>.json`) |
|-------------|-------------------------------------|--------------------------------------|
| Identifiant | `id` (int officiel)                 | `code` (string, ex. `"EPCE-2038"`)  |
| URL         | `/release/<id>/`                    | `/release/detail/<code>/`            |
| Source      | absent                              | `"source": "upfront"`               |
| Date format | `"2025.10.8"`                       | `"2014/10/01"`                       |
| Images      | `/upload/images/<hash>.webp`        | `/images/<hash>.jpg`                 |

### `releases/barcodes.json`

```json
{
  "EPCE-7992":  { "cdjapan": "4988002848423", "jan": "4988002848423" },
  "HKCN-50852": { "cdjapan": null }
}
```

Clé = `catalogNo`. `jan` = EAN-13 (absent si non trouvé sur CDJapan). Environ 3975/5565 codes ont un JAN.

### `members/<id>.json` — Membre actif (scraper.py)

```json
{
  "id":       201,
  "url":      "/morningmusume/fukumura_mizuki/",
  "slug":     "fukumura_mizuki",
  "group":    "morningmusume",
  "nameJa":   "譜久村聖",
  "nameEn":   "Mizuki Fukumura",
  "nameKana": "フクムラミズキ",
  "role":     "リーダー",
  "images":   ["/upload/images/<hash>.webp"],
  "color":    { "name": "ロイヤルパープル", "hex": "#7B2D8B" },
  "details": {
    "生年月日": "1996年10月30日",
    "出身地":   "愛知県",
    "血液型":   "A型"
  }
}
```

- `role`, `color`, `details` : optionnels
- `id` officiel (depuis `profilesById` de `artist_list.json`)

### `members/<id>.json` — Membre consolidé (archiver consolidate)

```json
{
  "id":          905894,
  "url":         "/morningmusume/profile/sakura_oda/",
  "slug":        "sakura_oda",
  "group":       "morningmusume",
  "nameJa":      "小田さくら",
  "nameKana":    "オダサクラ",
  "images": [
    "https://web.archive.org/web/20220101120000if_/https://cdn.helloproject.com/img/…jpg"
  ],
  "has_grad":    true,
  "archivedUrl": "https://web.archive.org/web/20220101120000/http://helloproject.com/…",
  "sources":     ["html"],
  "details": {
    "生年月日": "1999年3月12日",
    "出身地":   "東京都",
    "血液型":   "A型"
  }
}
```

- `id` : synthétique 900000–999998 (MD5 du slug)
- `has_grad: true` distingue membre graduée vs membre actif
- `sources` : liste des ères utilisées (`["html"]`, `["html", "pre-html"]`, etc.)
- Pas de `nameEn`, `role` (absents des ères Wayback)
- `color` : présent si trouvé dans l'ère html

### `members/artist_registry.json`

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

- Clés = `nameJa` NFKC-normalisé
- Construit par `migrate_structure.py` depuis `former_discovered.json` + `ufw_artists_discovered.json`
- Mis à jour par `discover --era pre-html` et `consolidate`

### `members/staging/html/<slug>.json` — Brut html-era

Même structure que membre consolidé mais sans `sources`. Toujours `has_grad: true`.

### `members/staging/upfront/<slug>.json` — Artiste UFW

```json
{
  "id":     812382,
  "url":    "/artist/natsumi_abe/",
  "slug":   "natsumi_abe",
  "source": "upfront",
  "kind":   "artist",
  "nameJa": "安倍なつみ",
  "images": ["/images/<hash>.jpg"],
  "bio":    "1997年9月7日…"
}
```

`kind` : `"artist"` (solo) ou `"group"`. ID synthétique 800000–899998 (MD5 de `"ufw:" + slug`).

---

## Plages d'IDs synthétiques

| Source | Plage | Clé MD5 |
|--------|-------|---------|
| helloproject ancien (html, pre-html) | 900000–999998 | `slug` |
| upfront (artistes) | 800000–899998 | `"ufw:" + slug` |
| Membres actifs | Officiel depuis `profilesById` | — |

---

## Déduplication entre sources

### Releases HP ↔ UFW

Clé naturelle : `editions[].discs[].catalogNo`

Stratégie importer :
1. Importer releases HP en premier (IDs officiels).
2. Pour chaque release UFW, chercher un match par `catalogNo` dans les éditions HP.
3. Match → enrichir (images, tracklist). Pas de match → créer release `source:upfront`.

### Membres HP ↔ UFW ↔ Wayback

Clés par priorité :
1. `slug` (identique entre scraper.py et archiver.py html-era)
2. `nameJa` (NFKC-normalisé) pour match cross-sources

---

## Points d'attention pour l'importer

- `<year>_releases.json` anciens (années 2000–2010) : JSON invalide (caractères de contrôle non échappés).
- `artist_list.json` : les noms sont dans `profilesById`, **pas** dans `artistsById`.
- `artistRelation[group_id]` : `kind: "unit"` = sous-groupe — résolution récursive pour lister les vrais membres.
- `track.credits` et `track.suffix` : absents si vides (ne pas assumer `null`).
- Images membres actifs : peuvent contenir des URLs Wayback si enrichis par `enrich --images`.
- `has_grad: true` dans `members/<id>.json` : membre graduée consolidée (ID synthétique).
- `color.hex` : couleur officielle du membre (utile pour l'affichage).
