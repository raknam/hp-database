# helloproject.com HTML v1 — Structure des données

Référence pour l'implémentation côté base de données.  
Source : `scraper/archiver.py` — commandes `discover` / `fetch --source helloproject --era html-v1`.  
Période : avril 2014 → janvier 2025 (structure HTML classique, récupérée via Wayback Machine).  
URL membre : `https://helloproject.com/<group>/profile/<slug>/`

---

## Fichiers produits

```
members/former_discovered.json     index des membres graduées découvertes
members/<id>.json                  profil d'une membre graduée (id synthétique)
```

---

## `members/former_discovered.json`

Index structuré par groupe :

```json
{
  "morningmusume": [
    {
      "slug":      "sakura_oda",
      "group":     "morningmusume",
      "nameJa":    "小田さくら",
      "nameKana":  "オダサクラ",
      "thumbnail": "https://cdn.helloproject.com/img/…jpg",
      "details":   { "生年月日": "1999年3月12日" },
      "source":    "helloproject",
      "era":       "html_v1",
      "firstSeen": "20180101120000",
      "lastSeen":  "20240601120000"
    }
  ],
  "c-ute": [ … ],
  "berryzkobo": [ … ]
}
```

- `firstSeen` / `lastSeen` = timestamps Wayback (format `YYYYMMDDHHmmss`) de la première et dernière apparition dans la liste de groupe.
- Dédupliqué par `nameJa` cross-groupes (une même personne n'apparaît qu'une fois).

---

## `members/<id>.json`

```json
{
  "id":               905894,
  "url":              "/morningmusume/profile/sakura_oda/",
  "slug":             "sakura_oda",
  "group":            "morningmusume",
  "nameJa":           "小田さくら",
  "nameKana":         "オダサクラ",
  "images": [
    "https://web.archive.org/web/20220101120000if_/https://cdn.helloproject.com/img/…jpg"
  ],
  "archived":          true,
  "archivedTimestamp": "20220101120000",
  "archivedUrl":       "https://web.archive.org/web/20220101120000/http://helloproject.com/morningmusume/profile/sakura_oda/",
  "details": {
    "生年月日": "1999年3月12日",
    "出身地":   "東京都",
    "血液型":   "A型"
  }
}
```

**Différences avec membre actif (site actuel) :**
- `id` = synthétique (900000–999998, MD5 du slug) — pas l'ID officiel H!P.
- `url` = chemin `/profile/` (format html_v1).
- `archived: true` + `archivedTimestamp` + `archivedUrl`.
- `images` = URLs Wayback (`https://web.archive.org/web/<ts>if_/<original_cdn_url>`).
- Pas de `nameEn`, `role`, `color` (absents du HTML de cette ère).

---

## HTML source — liste de groupe `/<group>/profile/`

```
ul#profile_memberlist
  li
    div.photo_box
      a[href="/…/profile/<slug>/"]    ← lien vers profil individuel
        img[src]                       ← thumbnail
    div.name
      h4                               ← nameJa
      NavigableString (nœud direct)   ← nameKana
    div.item dl
      dt / dd                          ← détails (生年月日, 出身地…)
```

---

## HTML source — profil individuel `/<group>/profile/<slug>/`

```
div#artist_text
  h3                                   ← nameJa
  p#yomigana                           ← nameKana
  dl
    dt.question / dd                   ← détails
div#artist_photoB  (ou #artist_photo)
  ul.slider li img                     ← photos (URLs CDN originales)
```

---

## IDs et clés de jointure

| Champ | Valeur |
|-------|--------|
| `id` | Synthétique 900000–999998 (MD5 du slug). Non stable si le slug change. |
| `slug` | Clé naturelle stable pour déduplication avec d'autres sources. |
| `nameJa` | Clé de déduplication cross-groupes et cross-ères. |

**Déduplication :**
- Avec site actuel : par `slug` ou `nameJa`.
- Avec up-front-works : par `nameJa` (les slugs sont différents entre les deux sites).
