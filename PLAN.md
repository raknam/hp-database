# Plan — Base de données + site local pour la collection H!P (et au-delà)

## Context

Le scraper `scraper/scraper.py` produit aujourd'hui des fichiers JSON (catalogue, releases, members, images) servis en lecture par `scraper/server.py`. L'objectif est de passer à une vraie base de données pour :

1. **Étendre le périmètre** : artistes hors H!P pur (Up-Front, Perfume, externes) sans tordre le schéma actuel.
2. **Gérer une collection physique** : savoir quelles éditions on possède (CD/BD/DVD/photobook…), où, dans quel état.
3. **Indexer les ISO du NAS** par disque, avec lien direct depuis le site local pour parcourir/lire.
4. **Préparer l'arrivée d'autres types d'objets** que le scraper ajoutera plus tard (clips MV, peut-être events, magazines, etc.).
5. **Garder le scraper comme source de vérité** pour les données publiques — la DB est régénérable à partir des JSON.

Décisions validées :
- **Moteur DB** : SQLite pour le dev, MySQL à terme → ORM portable (SQLAlchemy).
- **Source de vérité** : les JSON du scraper, importés idempotemment. Les données perso (collection, ISO) ne sont jamais écrasées.
- **Stack site** : FastAPI + Jinja2 + SQLAlchemy.
- **Granularité** : collection par édition, ISO par disque.
- **Clip IDs YouTube** : reportés — le scraper évoluera pour les ajouter, mais le schéma prévoit déjà la table `video_clips`.

---

## Architecture cible

```
hp-database/
├── scraper/              # inchangé — produit les JSON
├── db/
│   ├── models.py         # SQLAlchemy ORM (compatible SQLite + MySQL)
│   ├── schema.sql        # référence lisible du schéma
│   └── migrations/       # alembic
├── importer/
│   ├── __init__.py
│   └── import_scraper.py # lit scraper/releases/*, scraper/members/* → DB
├── webapp/
│   ├── main.py           # FastAPI app
│   ├── routes/           # /releases, /collection, /iso, /search, /artists
│   ├── templates/        # Jinja2 (peut reprendre le look de server.py)
│   └── static/
├── nas/
│   └── scan_iso.py       # scan d'un répertoire NAS → table iso_files
├── config.py             # DATABASE_URL (sqlite:///hp.db | mysql+pymysql://...), NAS_ROOTS
└── pyproject.toml
```

L'ancien `scraper/server.py` peut rester en parallèle au début, puis être remplacé par `webapp/`.

---

## Schéma de la base

Principes :
- IDs **internes** auto-incrémentés partout, IDs **externes** (helloproject.com release id, member id) en colonne séparée + index unique par `(source, external_id)`.
- Multi-source dès le départ : champ `source` sur les entités importables (`hp_official`, `up_front`, `perfume_official`, `manual`, …).
- Pas de JSON dans les colonnes (sauf champ `extra` optionnel pour des données rares non normalisées) — on reste portable MySQL.
- Toutes les tables ont `created_at`, `updated_at`.

### Domaine "catalogue public" (alimenté par le scraper)

**`artists`** — toute entité créditée comme artiste (groupe, sub-unit, membre solo, artiste externe).
- `id` PK
- `source` enum (`hp_official`, `up_front`, `perfume_official`, `manual`)
- `external_id` (l'id helloproject.com pour H!P, NULL pour les autres)
- `slug` (unique par source)
- `kind` enum (`group`, `unit`, `member`, `external`)
- `name_ja`, `name_en`, `name_kana`
- `extra` JSON nullable (couleur, dates, blood type… tout ce qui ne mérite pas sa propre colonne)
- index `(source, external_id)` unique, index `slug`

**`artist_relations`** — hiérarchie (membre → groupe, sub-unit → groupe parent).
- `parent_id` FK artists, `child_id` FK artists
- `kind` enum (`member`, `unit`)
- `joined_at`, `left_at` nullable
- PK `(parent_id, child_id)`

**`releases`** — un disque/photobook/livre.
- `id` PK
- `source`, `external_id` (id du site)
- `title`
- `category` (CDシングル, CDアルバム, DVD, BD, …) — string libre, pas d'enum (le scraper en ajoutera)
- `artist_id` FK artists (nullable si plusieurs / V.A.)
- `artist_label_raw` (le champ `"artist"` brut du JSON, garde l'attribution exacte)
- `release_date` DATE
- `label`
- `url` (path /release/<id>/ pour H!P)
- `extra` JSON

**`release_artists`** — table de liaison N-N pour les V.A. / multi-artistes (bonus, pas bloquant si vide au début).

**`release_images`** — galerie carrousel.
- `release_id` FK, `path`, `sort_order`

**`editions`** — une édition d'une release (初回限定盤A, 通常盤, …).
- `id` PK
- `release_id` FK
- `name` nullable (NULL pour DVD/BD/VHS sans édition multiple)
- `image_path`
- `price_raw` (string : "￥2,090（税抜価格 ￥1,900）")
- `price_jpy` INT nullable (parsé)
- `note`
- `sort_order`

**`discs`** — un disque physique d'une édition.
- `id` PK
- `edition_id` FK
- `disc_type` (`CD`, `BD`, `DVD`, `MD`, `VHS`)
- `catalog_no` indexé
- `sort_order`

**`tracks`** — un track sur un disc.
- `id` PK
- `disc_id` FK
- `index_no` (le `index` du JSON)
- `title`
- `suffix` nullable ("(Instrumental)", "(Music Video)", "(Dance Shot Ver.)")
- `duration_seconds` INT nullable
- `song_id` FK songs nullable (résolu plus tard, voir plus bas)

**`track_credits`**
- `track_id` FK
- `role` (作詞, 作曲, 編曲, 歌, 出演…)
- `credit_text` (peut être plusieurs personnes dans une seule string — on garde brut)
- `artist_id` FK artists nullable (résolu si on retrouve la personne)

**`songs`** — *identité canonique* d'une chanson, indépendante d'une release.
- `id` PK
- `title_canonical`
- `extra` JSON
- Une song peut avoir N tracks (singles + albums + instrumentaux + MV…). La résolution (`tracks.song_id`) se fait dans un step de l'importer par `(title sans suffix, artiste principal)`. Pas grave si imparfait au début, on peut l'affiner.

**`video_clips`** — préparé pour quand le scraper ajoutera les IDs YouTube.
- `id` PK
- `song_id` FK songs nullable
- `track_id` FK tracks nullable (pour un MV qui n'apparaît que sur un BD précis)
- `provider` (`youtube`, `niconico`, `hp_site`, …)
- `external_id` (ex: l'ID YouTube)
- `kind` (`mv`, `dance_shot`, `making_of`, `live`)
- `url` calculée ou stockée

### Domaine "perso" (jamais touché par l'importer)

**`collection_items`** — possession d'une édition.
- `id` PK
- `edition_id` FK editions
- `owned` BOOL
- `condition` enum nullable (`mint`, `good`, `fair`, `damaged`)
- `location` (étagère, boîte, "chez parents")
- `acquired_date`, `acquired_price`, `acquired_from`
- `notes` TEXT
- Index unique `edition_id` (une seule entrée perso par édition).

**`iso_files`** — un fichier ISO/MKV/etc. sur le NAS, lié à un disque.
- `id` PK
- `disc_id` FK discs nullable (NULL = ISO orphelin pas encore rattaché)
- `nas_path` (string complet, ex: `\\NAS\hp\BD\HKBN-50852.iso`)
- `relative_path` (chemin sous une racine connue, pour portabilité)
- `size_bytes`
- `format` (`iso`, `mkv`, `mp4`, `mds+mdf`, `folder`)
- `sha256` nullable (calculé lazy, optionnel)
- `last_seen_at` (mise à jour à chaque scan)
- `present` BOOL (false si plus trouvé au dernier scan, on garde l'entrée)
- Index unique `nas_path`.

**`tags`** + **`item_tags`** (optionnel, pour annoter releases/songs/editions librement) — *à ne pas implémenter en V1*, mentionné juste pour ne pas se peindre dans un coin.

---

## Importer (`importer/import_scraper.py`)

CLI :
```bash
py -m importer.import_scraper --all
py -m importer.import_scraper --releases
py -m importer.import_scraper --members
py -m importer.import_scraper --release 7506
py -m importer.import_scraper --year 2025
```

Comportement :
- **Idempotent** : upsert sur `(source, external_id)` pour artists/releases/members, sur `(release_id, sort_order)` pour editions, etc.
- **Ne touche jamais** `collection_items` ni `iso_files`.
- **Détecte les suppressions côté source** : si une release n'apparaît plus dans le catalogue, on log un warning mais on ne supprime pas (préserve les liens collection/ISO).
- **Lit** `scraper/releases/version.json`, `artist_list.json`, `<year>_releases.json`, `<id>.json`, `members/<id>.json`.
- **Réutilise** la logique de résolution de noms (`profilesById[id].nameJa → nameEn → slug`) et la résolution récursive `kind: "unit"` de `artist_list.json`.
- **Parse** `price_raw` → `price_jpy` (regex `￥([0-9,]+)`), `duration` `MM:SS` → secondes, `releaseDate` (formats variables : `2025.10.8`, `1998-12-12`).
- **Résolution songs** : passe finale qui regroupe `tracks` par `(title normalisé sans suffix, artist_id)` → crée/lie une `songs.id`.

Fichiers à lire pour s'inspirer :
- `scraper/SCRAPER.md` (schémas JSON complets, arborescence, règles de merge)
- `scraper/CLAUDE.md` (pitfalls JSON, profilesById vs artistsById)

---

## Scanner NAS (`nas/scan_iso.py`)

CLI :
```bash
py -m nas.scan_iso --root "\\NAS\hp" --root "\\NAS\perfume"
py -m nas.scan_iso --rescan-missing  # recheck les `present=false`
```

Comportement :
- Walk récursif des `--root`, filtre extensions `.iso .mkv .mp4 .mds`.
- Upsert dans `iso_files` par `nas_path`.
- **Auto-link** vers `discs.catalog_no` si le nom de fichier match (regex `[A-Z]{2,4}-\d{4,5}`). Sinon `disc_id = NULL`, l'utilisateur lie depuis l'UI.
- Marque `present=false` les entrées non revues lors d'un scan complet.

Config dans `config.py` : `NAS_ROOTS = [...]`. Pas de credentials stockés en DB.

---

## Webapp FastAPI

Routes principales (V1) :

| Route | Vue |
|---|---|
| `/` | Dashboard : nb artistes / releases / éditions possédées / ISO indexés |
| `/artists` | Liste paginée, filtres `source`, `kind` |
| `/artists/<slug>` | Détail artiste + discographie + membres (récursif unit) |
| `/releases` | Liste, filtres année / catégorie / artiste / `owned=true` |
| `/release/<id>` | Détail : éditions, discs, tracks, crédits, **bouton "je possède"**, **liens ISO par disque** |
| `/songs/<id>` | Toutes les apparitions d'une chanson (single, album, BD MV) |
| `/collection` | Mes éditions possédées, vue grid avec covers |
| `/iso` | Liste des ISO indexés, filtre orphelins (`disc_id IS NULL`) |
| `/iso/<id>/open` | Ouvre / stream l'ISO (lien `file://` ou route de stream local) |
| `/search?q=…` | Full-text basique sur titres releases/songs/artists |
| `/admin/import` | Bouton "réimporter" (lance l'import en background) |
| `/admin/scan-nas` | Bouton "rescan NAS" |

Stack technique :
- **FastAPI** + **Jinja2Templates** pour les vues serveur, **HTMX** côté client pour les actions collection (toggle owned, lier un ISO orphelin) sans JS framework.
- **SQLAlchemy 2.x** (sync suffit pour usage local) avec `DATABASE_URL` lu depuis env / `config.py`. Le code reste identique entre `sqlite:///hp.db` et `mysql+pymysql://user:pass@host/hp`.
- **Alembic** pour les migrations dès le début (le passage SQLite→MySQL en bénéficiera).
- Service d'images : reprendre la logique de `scraper/server.py` (servir local, fallback proxy helloproject.com, `Cache-Control: max-age=86400`).

---

## Étapes d'implémentation

1. **Setup projet** : `pyproject.toml`, deps (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `pymysql`, `jinja2`, `python-multipart`, `requests`).
2. **`db/models.py`** : tous les modèles ci-dessus, génération `schema.sql` pour SQLite via `CREATE TABLE` dump.
3. **Alembic init + première migration**.
4. **`importer/import_scraper.py`** : commencer par artists+members (le plus simple, déjà bien structuré), puis releases, puis editions/discs/tracks, puis credits, puis résolution songs.
5. **Scan NAS** minimal : walk + upsert + auto-link par `catalog_no`.
6. **Webapp V1** : routes `/`, `/releases`, `/release/<id>`, `/collection`, toggle owned, `/iso`. Templates en réutilisant le HTML de `scraper/server.py`.
7. **Polish** : search, songs view, admin actions.

---

## Vérification end-to-end

- `py -m importer.import_scraper --all` sur les JSON existants → checker en SQLite que counts cohérents : `SELECT COUNT(*) FROM releases` ≈ nb fichiers `releases/<id>.json`, `artists` ≈ entrées de `profilesById`.
- Rerun → 0 modification (idempotence).
- Créer un ISO bidon nommé `HKBN-50852.iso` dans un dossier de test → `py -m nas.scan_iso --root <dossier>` → ISO lié au bon disc via catalog_no.
- `uvicorn webapp.main:app --reload` → ouvrir `/release/7506`, cocher "owned", refresh → état persiste. Cliquer un ISO → s'ouvre.
- Migration vers MySQL : changer `DATABASE_URL`, `alembic upgrade head`, relancer importer → même résultat.

---

## Critical files (à modifier / créer)

- **Créer** : `db/models.py`, `db/schema.sql`, `db/migrations/`, `importer/import_scraper.py`, `nas/scan_iso.py`, `webapp/main.py`, `webapp/routes/*.py`, `webapp/templates/*.html`, `config.py`, `pyproject.toml`.
- **Lire pour s'inspirer** : `scraper/server.py` (DataStore, profile_name, resolve_members, image proxy), `scraper/CLAUDE.md` (pitfalls), `scraper/scraper.py` (formats des JSON produits).
- **Inchangé** : `scraper/scraper.py`, `scraper/archiver.py`.
