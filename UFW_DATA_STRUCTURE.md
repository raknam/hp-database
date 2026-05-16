# up-front-works.jp — Structure des données

Référence pour l'implémentation côté base de données.  
Source : `scraper/archiver.py` — commandes `discover` / `fetch --source upfront`.

---

## Fichiers produits

```
releases/upfront_discovered.json   liste des codes catalogue découverts
releases/upfront/<CODE>.json       détail d'une release (un fichier par code)
```

---

## `upfront_discovered.json`

Liste plate :

```json
[
  { "code": "EPCE-7992", "year": 2026 },
  { "code": "EPBE-3004", "year": 2000 }
]
```

`year` est l'année extraite de l'URL de découverte (`/release/search/?y=YEAR`) —
redondant avec `releaseDate` dans le fichier détail, mais utile si `releaseDate` est absent.

---

## `releases/upfront/<CODE>.json`

```json
{
  "code":        "EPCE-2038",
  "url":         "/release/detail/EPCE-2038/",
  "source":      "upfront",
  "title":       "入っておいで この里に/この街で/地球が生まれた日",
  "category":    "CDシングル",
  "artist":      "ブラザーズ5",
  "releaseDate": "2014/10/01",
  "label":       "zetima",
  "images": [
    "/images/f3aff06e9175b37249ec794c5d511e407c0ccdb1.jpg",
    "/images/2953be520b77da27e22f8add6f3b18984583b909.jpg"
  ],
  "editions": [
    {
      "name":  "初回生産限定盤",
      "image": "/images/f3aff06e9175b37249ec794c5d511e407c0ccdb1.jpg",
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
              "credits": {
                "作詞": "アメリカ民謡/日本語詞:兵頭 剛",
                "作曲": "アメリカ民謡",
                "編曲": "和田春彦"
              }
            }
          ]
        }
      ]
    },
    {
      "name":  "通常盤",
      "image": "/images/2953be520b77da27e22f8add6f3b18984583b909.jpg",
      "price": "￥1,234 (税抜価格 ￥1,122)",
      "discs": [ { "type": "CDシングル", "catalogNo": "EPCE-2039", "tracks": [] } ]
    }
  ]
}
```

---

## Différences clés avec helloproject.com

| Champ         | helloproject (`releases/<id>.json`) | up-front-works (`releases/upfront/<code>.json`) |
|---------------|-------------------------------------|-------------------------------------------------|
| Identifiant   | `id` (entier, ex. `7506`)           | `code` (string, ex. `"EPCE-7992"`)              |
| URL           | `/release/<id>/`                    | `/release/detail/<code>/`                       |
| Source        | *(absent)*                          | `"source": "upfront"`                           |
| Date format   | `"2025.10.8"`                       | `"2026/06/03"`                                  |
| Images        | chemins relatifs `/upload/images/…` | chemins locaux `/images/<hash>.jpg` (CDN)       |
| Editions      | plusieurs disques possibles par édition | un seul disc par édition (structure du site) |
| Performer     | dans `track.credits`                | dans `hide_cell` HTML (non extrait actuellement)|

---

## Déduplication avec helloproject

Le champ `editions[].discs[].catalogNo` est présent dans les deux sources.  
Un release helloproject contient les mêmes codes catalogue (ex. `EPCE-7992`) que le fichier upfront correspondant.  
→ Clé de déduplication naturelle : **`catalogNo`**.

Stratégie suggérée pour l'importer :
1. Importer les releases helloproject en premier (IDs numériques officiels).
2. Pour chaque release upfront, chercher un match par `catalogNo` dans les éditions existantes.
3. Si match → enrichir (ajouter images, compléter tracklist si manquante).
4. Si pas de match → créer une nouvelle release avec `source: "upfront"` et un ID synthétique.

---

## `members/ufw_artists_discovered.json`

Index des artistes/groupes découverts sur `/artist/` :

```json
[
  { "slug": "natsumi_abe",        "nameJa": "安倍なつみ" },
  { "slug": "upupgirlskakkokari", "nameJa": "アップアップガールズ（仮）" }
]
```

---

## `members/<id>.json` (artiste UFW)

ID synthétique dans la plage **800000–899998** (MD5 de `"ufw:" + slug`).

```json
{
  "id":     812382,
  "url":    "/artist/natsumi_abe/",
  "slug":   "natsumi_abe",
  "source": "upfront",
  "kind":   "artist",
  "nameJa": "安倍なつみ",
  "images": ["/images/01bb4971e689675cf7ce470703c1893e518f6de3.jpg"],
  "bio":    "1997年9月7日、…"
}
```

`kind` : `"artist"` (solo) ou `"group"`.  
Pas de `nameKana`, `nameEn`, `details` (birthday, blood type…) — absents des pages UFW.  
Pas de `archived` — les artistes UFW ne sont pas des "graduées H!P".

**Détection group vs artist :**
- Groupes HP → cross-référence `releases/artist_list.json` (`artistType == "group"`)
- Groupes non-HP → liste statique `UFW_NON_HP_GROUP_SLUGS` dans `archiver.py`

**Commandes :**
```powershell
py archiver.py discover --source upfront --artists
py archiver.py fetch    --source upfront --artists
py archiver.py fetch    --source upfront --artists --slug natsumi_abe
py archiver.py fetch    --source upfront --artists --force
```

---

## Plages d'IDs synthétiques

| Source | Plage | Clé MD5 |
|--------|-------|---------|
| helloproject/html (membres graduées) | 900000–999998 | `slug` |
| upfront (artistes) | 800000–899998 | `"ufw:" + slug` |

---

## Volume

- ~3 138 releases découvertes (1998–2026)
- Répartition : ~100–345 releases par année selon l'activité
- Codes préfixes observés : `EPCE-`, `EPBE-`, `EPXE-`, `HKCN-`, `PKCP-`, `UFDL-`, `UFBW-`

---

## HTML source (référence pour re-parsing)

Structure de `/release/detail/<CODE>/` :

```
div.wrap_detaildata.cf
  div#left
    a.jacket-box.modal[href=CDN_LARGE]   ← cover principale (grande résolution)
      img[src=CDN_MEDIUM]
      p.sub_title                         ← label édition ("初回生産限定盤", "通常盤"…)
    div.sub-jacket
      a.modal[href=CDN_LARGE]            ← covers supplémentaires (une par édition)
        img[src=CDN_SMALL]
        p.sub_title
  div#right
    h2.product_title                     ← titre (contient h3.artist imbriqué — texte direct seulement)
      h3.artist                          ← artiste
    table.data1                          ← métadonnées
      tr > td.columnA / td.columnB      ← paires clé/valeur : ジャンル, 発売日, レーベル, 備考
    -- répété par édition --
    h3.notes                             ← "EDITION_NAME　CODE　PRICE\nNOTE"
    h4.genre                             ← type de disque (CDシングル, DVD…)
    table.data2                          ← tracklist
      tr.head                            ← en-tête (ignorer)
      tr > td.columnA…F                 ← piste : index, titre, durée, 作詞, 作曲, 編曲
      tr.hide_cell                       ← détails performer (non extrait actuellement)
```
