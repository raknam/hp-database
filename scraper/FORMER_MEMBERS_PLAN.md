# Plan : récupérer les données des anciennes membres H!P

## Contexte

Le scraper actuel (`scraper.py`) ne récupère que les membres **actuels** de H!P car `artist_list.json` ne liste que les membres encore actifs. L'objectif est d'enrichir la base avec les données de profil des graduées via le Wayback Machine, sans toucher au fonctionnement existant.

**Contrainte absolue** : aucune modification des commandes `update`, `scrape`, `members` — le code existant et les données qu'il produit ne doivent pas être altérés.

**Tout le code nouveau vit dans `scraper/`**, à côté de `scraper.py`.

---

## Ères du site et ce qu'on peut scraper

| Ère | Période | URL profil | Parsable |
|-----|---------|-----------|---------|
| **Actuelle** | début 2025 → aujourd'hui | `/{group}/{slug}/` | Oui — déjà fait par `scraper.py` |
| **HTML v1** | 24 avr 2014 → début 2025 | `/{group}/profile/{slug}/` | **Oui** — structure stable sur ~10 ans |
| **Pré-HTML** | avant le 24 avr 2014 | `/{group}/profile.html?id={id}` | **Oui** — HTML Shift-JIS, pages archivées |

### Structure HTML v1 (confirmée sur snapshots réels)

Page liste `/{group}/profile/` :
```
ul#profile_memberlist.cf
  li > div
    div.photo_box > a[href=/{group}/profile/{slug}/] > img[src]   ← thumbnail
    div.name > h4                                                   ← nameJa
               (texte suivant)                                      ← nameKana
    div.item > dl > dt / dd                                         ← 生年月日, 血液型, 出身地
```

Page individuelle `/{group}/profile/{slug}/` (ajoute) :
```
div#artist_photoB > ul.slider > li > img[src]    ← photo full-res
div#artist_text
  h3                                              ← nameJa
  p#yomigana                                      ← nameKana
  dl > dt.question / dd                           ← tous les détails + ハロー！プロジェクト加入
```

Champs **absents** de l'ère HTML v1 : `color`, `nameEn`.

### Structure pré-HTML (confirmée, Shift-JIS)

Page liste `/{group}/profile.html` :
```
ul#profileBtn li a[href*="?id="]    ← IDs courts ("oda", "ishida")
```

Page individuelle `/{group}/profile.html?id={id}` :
```
div#profileMainArea
  h3                                ← nameJa + "(groupe)" — strip la partie groupe
  div#profileImage img[src]         ← photos (img.helloproject.com/…/{id}_01_img.jpg)
  dl#questionList dt / dd           ← Q&A (Q.特技は？, Q.趣味は？…)
```

Champs **absents** de l'ère pré-HTML : birthday, blood type, prefecture, nameKana.
**Déduplication** avec HTML v1 : par nameJa (les IDs courts `oda` ≠ slugs `sakura_oda`).

---

## Stratégie de timestamps

**CDX API** (`collapse=digest`) — une requête par URL de groupe, retourne uniquement les versions où le contenu a changé (~15-25 par groupe sur 10 ans) :

```
GET https://web.archive.org/cdx/search/cdx
  ?url=http://helloproject.com/morningmusume/profile/
  &output=json
  &fl=timestamp,digest
  &filter=statuscode:200
  &collapse=digest
  &from=20140424
  &to=20250101
```

Pas de compte, pas de clé API — entièrement public.

---

## Prérequis

**Zéro nouvelle dépendance.** Tout est déjà disponible :

| Besoin | Source |
|--------|--------|
| HTTP | `requests` — déjà dans `requirements.txt` |
| HTML parsing | `beautifulsoup4` — déjà utilisé par `scraper.py` |
| Shift-JIS decode | `bytes.decode('shift_jis')` — stdlib Python |
| Hash IDs synthétiques | `hashlib` — stdlib Python |
| Rate limiting | `time.sleep` — stdlib Python |

> `beautifulsoup4` est absent de `requirements.txt` — à ajouter au passage.

---

## Architecture

### Fichier : `scraper/archiver.py`

Complètement séparé de `scraper.py`. Commandes :

```
py archiver.py discover              # Phase 1 : tous les groupes
py archiver.py discover --group morningmusume
py archiver.py fetch                 # Phase 2 : tous les slugs découverts
py archiver.py fetch --slug ayumi_ishida --force
```

### Phase 1 — Découverte (page liste)

Pour chaque groupe connu (slugs depuis `artist_list.json`) :
1. CDX API `collapse=digest` → timestamps des versions distinctes de `/{group}/profile/`
2. Fetch chaque version via `https://web.archive.org/web/{ts}if_/{url}` (flag `if_` = sans toolbar WM)
3. Parser `#profile_memberlist` → slug + nameJa + nameKana + thumbnail + 生年月日/血液型/出身地
4. Union de toutes les versions → `firstSeen` / `lastSeen` par slug
5. Soustraire les membres actuels → anciennes membres uniquement
6. Sauvegarder `members/former_discovered.json`

Pour l'ère pré-HTML : même logique sur `/{group}/profile.html`, parse `ul#profileBtn`, fetch pages `?id=` individuelles avec `decode('shift_jis')`.

```json
// members/former_discovered.json
{
  "morningmusume": [
    {
      "slug": "ayumi_ishida",
      "era": "html_v1",
      "group": "morningmusume",
      "nameJa": "石田亜佑美",
      "nameKana": "イシダ アユミ",
      "thumbnail": "http://cdn.helloproject.com/img/artist/m/{hash}.jpg",
      "details": { "生年月日": "1997年1月7日", "血液型": "O型", "出身地": "宮城県" },
      "firstSeen": "20140424",
      "lastSeen": "20241005"
    }
  ]
}
```

### Phase 2 — Enrichissement (page individuelle)

Pour chaque slug découvert :
1. CDX API → meilleure capture 200 de `/{group}/profile/{slug}/` autour de `lastSeen`
2. Fetch + parse `#artist_text` complet (nameJa, nameKana, tous les `dt.question/dd`, photo full-res)
3. Fusionner avec les données phase 1
4. Générer un ID synthétique reproductible : `int(hashlib.md5(slug.encode()).hexdigest()[:7], 16)`
5. Sauvegarder `members/{id}.json`

### Sortie `members/{id}.json`

Même format que `scraper.py`, avec champs additionnels :
```json
{
  "archived": true,
  "archivedTimestamp": "20241005122221",
  "archivedUrl": "https://web.archive.org/web/20241005122221/..."
}
```
Champs absents selon l'ère : `color`, `nameEn` (HTML v1), + `nameKana`/birthday/blood/prefecture (pré-HTML).

Les fichiers `members/{id}.json` existants (membres actuels) ne sont **jamais touchés**.

### Fonctions clés

```python
cdx_search(url, **kwargs)             # → liste de {timestamp, digest}
wayback_fetch(url, timestamp)         # → HTML brut (via /web/{ts}if_/)
parse_group_list_html_v1(html, group) # → liste de membres depuis #profile_memberlist
parse_member_profile_html_v1(html)    # → dict membre depuis #artist_text
parse_group_list_pre(html, group)     # → IDs courts depuis ul#profileBtn (Shift-JIS)
parse_member_profile_pre(html)        # → dict membre depuis #profileMainArea (Shift-JIS)
slug_to_id(slug)                      # → ID synthétique stable
```

### Rate limiting & cache

- 1.5 s entre chaque requête vers `web.archive.org`
- Cache HTML local dans `cache/archive/{slug}.html` — dossier dédié, séparé du cache de `scraper.py`

---

## Vérification

1. `py scraper.py update && py scraper.py members` → aucun fichier existant modifié
2. `py archiver.py discover --group morningmusume` → inspecter `members/former_discovered.json`
3. `py archiver.py fetch --slug ayumi_ishida` → vérifier `members/{id}.json` produit
4. Lancer l'importer → vérifier que les anciennes membres apparaissent dans la web app
