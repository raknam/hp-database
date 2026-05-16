# helloproject.com — Site actuel — Structure des données

Référence pour l'implémentation côté base de données.  
Source : `scraper/scraper.py` — commandes `update`, `scrape`, `members`.  
Période : ~2025 → présent (design actuel, classes CSS component-based).  
URL membre : `https://helloproject.com/<group>/<slug>/`

---

## Fichiers produits

```
releases/version.json              version API + liste des années
releases/artist_list.json          catalogue artistes/groupes/membres
releases/<year>_releases.json      liste des releases par année
releases/<id>.json                 détail d'une release scrapée
members/<id>.json                  profil d'un membre actif
```

---

## `version.json`

```json
{
  "version": "20250101",
  "releaseYears": [2025, 2024, 2023, ..., 1997]
}
```

---

## `artist_list.json`

```json
{
  "artistOrder": [101, 102, 103],
  "artistsById": {
    "101": { "artistType": "group",  "slug": "morningmusume" },
    "201": { "artistType": "artist", "slug": "fukumura_mizuki" }
  },
  "profilesById": {
    "101": {
      "nameJa":   "モーニング娘。'25",
      "nameEn":   "Morning Musume.'25",
      "nameKana": "モーニングムスメ",
      "slug":     "morningmusume",
      "images": {
        "thumbnail": { "url": "/upload/images/<hash>.webp" },
        "profile":   [ { "url": "/upload/images/<hash>.webp" } ]
      },
      "release": [ { "id": 7506, "image": { "url": "/upload/images/<hash>.webp" } } ]
    }
  },
  "artistRelation": {
    "101": [
      { "kind": "member", "id": 201 },
      { "kind": "unit",   "id": 301 }
    ]
  }
}
```

**Points importants :**
- Les noms sont dans `profilesById`, **pas** dans `artistsById`.
- `kind: "unit"` = sous-groupe (ex. BEYOOOOONDS → CHICA#TETSU…) ; résolution récursive nécessaire pour lister les membres réels.
- `artistOrder` = ordre d'affichage officiel H!P (liste d'IDs entiers).
- `artistsById` n'a pas de champ `name` — toujours lire `profilesById[id].nameJa`.

---

## `<year>_releases.json`

```json
{
  "items": [
    {
      "id":          7506,
      "title":       "四の五の言わず颯と別れてあげた",
      "artist":      "Juice=Juice",
      "artistName":  "Juice=Juice",
      "category":    "CDシングル",
      "releaseDate": "2025.10.8",
      "image":       { "url": "/upload/images/<hash>.webp" }
    }
  ]
}
```

**Note :** certains anciens fichiers (années 2000–2010) contiennent des caractères de contrôle non échappés — JSON invalide, à gérer à l'import.

---

## `releases/<id>.json`

```json
{
  "id":          7506,
  "url":         "/release/7506/",
  "title":       "四の五の言わず颯と別れてあげた",
  "category":    "CDシングル",
  "artist":      "Juice=Juice",
  "releaseDate": "2025.10.8",
  "label":       "hachama",
  "images":      [ "/upload/images/<hash>.webp" ],
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

**Cas particuliers :**
- `editions = []` pour 写真集 et 書籍.
- `editions[].name = null` pour les releases mono-édition (DVD, BD, VHS, MD).
- `editions[].note` = optionnel.
- `track.suffix` = optionnel ("(Instrumental)", "(Music Video)"…).
- `track.credits` = absent si vide.
- `images` = une entrée par édition pour CDシングル/albums ; une seule pour DVD/BD/写真集.

**Catégories connues :** CDシングル, CDアルバム, DVD, DVDシングルV, BD, MDアルバム, VHS, 写真集, 書籍.

---

## `members/<id>.json`

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
  "images":   [ "/upload/images/<hash>.webp" ],
  "color":    { "name": "ロイヤルパープル", "hex": "#7B2D8B" },
  "details": {
    "生年月日": "1996年10月30日",
    "出身地":   "愛知県",
    "血液型":   "A型"
  }
}
```

**Champs optionnels :** `role`, `color`, `details` (absents si non renseignés sur le site).

---

## HTML source — page release `/release/<id>/`

```
h1.ReleaseHead__mainName                       ← titre
.StatusLabel--category                         ← catégorie
.ReleaseHead__mainTitle .paragraph-sm          ← [0]=type label, [1]=artiste
.ReleaseHead__mainDetails dl.contents          ← dt/dd : 発売日, レーベル
.ReleaseItemGallery__image img                 ← galerie covers

.ReleaseEdition                                ← un bloc par édition
  .ReleaseEdition__name h2                     ← nom édition (null si mono-édition)
  .ReleaseEdition__cover img                   ← cover édition
  .ReleaseEdition__coverName                   ← prix
  .ReleaseEdition__head .paragraph-md          ← note bonus (optionnel)
  .ReleaseEdition__discs .TrackList            ← un par disque
    .ReleaseEdition__headline
      .ReleaseEdition__mediaType               ← type disque (CD, DVD…)
      [class*="text-blueGray"]                 ← code catalogue
    .TrackListItem                             ← une ligne par piste
      .TrackListItem__index
      .TrackListItem__title > span > span[0]   ← titre
      .TrackListItem__title > span > span[1]   ← suffix optionnel
      .TrackListItem__duration
      .TrackListItem__notes span               ← crédits, format "作詞：XXX"
```

---

## HTML source — page membre `/<group>/<slug>/`

```
.MemberHeader
  .MemberHeader__content div
    div.mb-1.5                          ← rôle (optionnel)
    h1                                  ← nameJa
    div.mb-5                            ← "nameEn ／ nameKana"
  .MemberHeader__detail dl             ← détails (生年月日, 出身地, 血液型…)
    dd.MemberHeader__color             ← couleur : style="background-color:#xxx"
  .MemberHeader__images img            ← photos (filter : src contient /upload/images/)
```

---

## IDs et clés de jointure

| Entité | Clé primaire | Clé de jointure |
|--------|-------------|-----------------|
| Release | `id` (int, officiel) | `editions[].discs[].catalogNo` |
| Membre | `id` (int, officiel, depuis `profilesById`) | `slug` |
| Groupe | `id` (int, officiel, depuis `artistsById`) | `slug` |
