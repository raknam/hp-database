# Plan : restructuration arborescence + pre-html + consolidation

## Contexte

`archiver.py` scrape les membres graduées via Wayback Machine. L'ère `html` (avr. 2014 – jan. 2025) est implémentée et un fetch est en cours (~61/146 membres fetchés). Ce plan couvre la restructuration complète de l'arborescence, le branchement de l'ère `pre-html`, la commande `consolidate`, et la refonte de la documentation.

**Contrainte** : attendre la fin du fetch `py archiver.py fetch --source helloproject --era html` avant de restructurer.

---

## Étape 0 — Importer ce qui existe (maintenant, avant restructuration)

```powershell
py -m importer.import_scraper --all
```

Les 61 membres `has_grad:true` déjà fetchés sont importables immédiatement. Pas de conflit avec le fetch en cours.

---

## Étape 1 — Cleanup (après fin du fetch)

**Supprimer** :
- `scraper/server.py`
- `scraper/WEBSERVER.md`
- `scraper/FORMER_MEMBERS_PLAN.md`
- Fichiers HTML de test : `scraper/mm_group_flash.html`, `scraper/mm_ishida_flash.html`, `scraper/mm_oda_flash.html`, `scraper/mm_profile_2014.html`, `scraper/ayumin_old.html`, `scraper/oda_old.html`

**Mettre à jour** `scraper/CLAUDE.md` :
- Retirer refs server.py et WEBSERVER.md
- Mettre à jour la structure des fichiers (nouvelle arborescence)
- Mettre à jour les commandes disponibles

---

## Étape 2 — Nouvelle arborescence (migration)

### Avant
```
members/
  <id>.json          # actifs (scraper.py) + has_grad (archiver html) + upfront
  former_discovered.json
  ufw_artists_discovered.json
cache/
  <id>.html          # cache releases HP
  <slug>.html        # cache membres HP actifs
  archive/           # cache Wayback membres
  upfront/           # cache releases UFW
  cdjapan/
  cdx_member_index.json
```

### Après
```
members/
  <id>.json          # actifs (scraper.py) + consolidés finaux (archiver)
  staging/
    html/            # brut Wayback 2014-2025 (migré depuis members/<id>.json has_grad:true)
    pre-html/        # brut Wayback 2012-2014
    flash/           # brut Wayback ≤2011 (futur)
    upfront/         # brut UFW artists (migré depuis members/<id>.json source:upfront)
  artist_registry.json   # remplace former_discovered.json + ufw_artists_discovered.json
cache/
  members/
    html/            # cache Wayback membres (migré depuis cache/archive/)
    pre-html/        # cache Wayback pre-html
    flash/           # futur
  releases/
    hp/              # cache releases HP (migré depuis cache/<id>.html)
    upfront/         # cache releases UFW (migré depuis cache/upfront/)
  cdjapan/
  cdx_member_index.json
```

### Script de migration (Python)
- `members/<id>.json` avec `has_grad:true` → `members/staging/html/<slug>.json`
- `members/<id>.json` avec `source:upfront` → `members/staging/upfront/<slug>.json`
- `cache/archive/*` → `cache/members/html/*`
- `cache/upfront/*` → `cache/releases/upfront/*`
- `cache/<id>.html` (numérique) → `cache/releases/hp/<id>.html`
- `former_discovered.json` + `ufw_artists_discovered.json` → `artist_registry.json` (nouveau format)

**Note** : après migration, les fichiers html déjà fetchés seront dans `staging/html/` avec un nouveau nom (`<slug>.json`). Le fetch re-parsera ces membres rapidement depuis le cache HTML (pas de re-téléchargement).

---

## Étape 3 — Mise à jour `archiver.py`

### Constantes
```python
CACHE_DIR           = Path("cache") / "members" / "html"      # était cache/archive
PRE_CACHE_DIR       = Path("cache") / "members" / "pre-html"
UFW_CACHE_DIR       = Path("cache") / "releases" / "upfront"  # était cache/upfront
HP_CACHE_DIR        = Path("cache") / "releases" / "hp"

STAGING_HTML_DIR    = MEMBERS_DIR / "staging" / "html"
STAGING_PRE_DIR     = MEMBERS_DIR / "staging" / "pre-html"
STAGING_FLASH_DIR   = MEMBERS_DIR / "staging" / "flash"
STAGING_UFW_DIR     = MEMBERS_DIR / "staging" / "upfront"

ARTIST_REGISTRY_FILE = MEMBERS_DIR / "artist_registry.json"   # remplace DISCOVERED_FILE + UFW_ARTISTS_DISCOVERED_FILE

ERA_PRE_FROM = "20120101"
ERA_PRE_TO   = "20140424"
ERA_FLASH_FROM = "20090101"
ERA_FLASH_TO   = "20120101"
```

Ajouter `"flash"` à `SOURCE_ERAS` (discover/fetch = "not yet implemented").

### `normalize_name()` (nouveau helper)
```python
import unicodedata
def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name).strip()
```

### Format `artist_registry.json`
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

### Brancher `pre-html`

**`discover_group_pre(group, force)`** (nouvelle fonction) :
- CDX sur `http://www.helloproject.com/<group>/profile.html` avec `matchType=prefix`
- Extrait slugs depuis URLs contenant `?id=<slug>` (regex `[?&]id=([^&]+)`)
- Fusionne dans `artist_registry.json`

**`fetch_member()` branche pre-html** (ligne ~1188, actuellement stub) :
- URL : `http://www.helloproject.com/<group>/profile.html?id=<slug>`
- Fetch Wayback `from=ERA_PRE_FROM, to=ERA_PRE_TO`, décodage Shift-JIS
- Utilise `parse_member_profile_pre()` existant (nameJa h3, nameKana, photos `#profileImage img`)
- Ignore `#questionList`
- Écrit dans `members/staging/pre-html/<slug>.json`

### Commande `consolidate`

```powershell
py archiver.py consolidate [--slug SLUG] [--force]
```

**Algorithme** :
1. Charge `artist_registry.json`
2. **Passe html** : pour chaque `staging/html/<slug>.json` → crée/confirme entrée registre
3. **Passe pre-html** : pour chaque `staging/pre-html/<slug>.json` → lookup nameJa → enrichit `members/<id>.json`
4. **Passe upfront** : pour chaque `staging/upfront/<slug>.json` (`kind:artist`) → lookup nameJa → ajoute photos + bio
5. Sauvegarde `artist_registry.json`

**Règles de merge** :

| Champ | Priorité |
|---|---|
| `details` (birthday, blood, origin) | html > pre-html > upfront |
| `nameJa`, `nameKana` | html > pre-html > upfront |
| `color` | html seulement |
| `bio` | upfront seulement |
| `images` | union html + pre-html + upfront (dédup par `Path(url).name`) |
| `sources` | liste ex. `["html", "pre-html", "upfront"]` |

---

## Étape 4 — Mise à jour `scraper.py`

- Cache releases HP : `cache/<id>.html` → `cache/releases/hp/<id>.html`
- Cache membres actifs : `cache/<slug>.html` → `cache/members/current/<slug>.html`

---

## Étape 5 — Nouveaux documents

### `scraper/SCRAPER.md` (refonte complète)
Livrable pour Opus (rewrite importer). Couvre :
- Arborescence complète des fichiers produits
- Schéma JSON de chaque type : `members/<id>.json` consolidé, `artist_registry.json`, releases HP, releases UFW
- Toutes les commandes (`scraper.py` + `archiver.py`)
- Règles de merge par ère

Remplace : `HP_CURRENT_DATA_STRUCTURE.md`, `HP_HTML_DATA_STRUCTURE.md`, `UFW_DATA_STRUCTURE.md`, ancien `SCRAPER.md`

### `scraper/CONSOLIDATION.md` (nouveau, doc évolutif)
- Logique de merge détaillée
- Format `artist_registry.json`
- Règles de priorité par ère
- Comment faire évoluer la consolidation (ajout ère flash, nouveaux champs)

---

## Barcodes — intégration importer

`releases/barcodes.json` est maintenant un `dict[catalogNo, { jan?, cdjapan?, ... }]`.
L'importer (`importer/import_scraper.py`) ne lit pas encore ce fichier.

**À faire** : lors de l'import d'une release HP ou UFW, lire `barcodes.json` et injecter `entry["jan"]` (si présent) dans le modèle de release importé (table ou champ à définir selon le schéma DB).

---

## Ordre d'exécution

1. **Maintenant** : `py -m importer.import_scraper --all` (importer ce qui existe)
2. **Attendre** : fin du fetch html en cours
3. **Cleanup** : supprimer server.py, WEBSERVER.md, FORMER_MEMBERS_PLAN.md, fichiers HTML test
4. **Migration** : script Python arborescence + nouveau format artist_registry.json
5. **Code** : mettre à jour archiver.py (constantes, pre-html, consolidate) + scraper.py (cache paths)
6. **Fetch pre-html** : `py archiver.py discover --source helloproject --era pre-html` puis fetch
7. **Consolidate** : `py archiver.py consolidate`
8. **Docs** : SCRAPER.md + CONSOLIDATION.md en parallèle du développement
9. **Mettre à jour** : scraper/CLAUDE.md

---

## Vérification

```powershell
# Après migration
ls members/staging/html/     # ~146 fichiers .json (tous les membres html-era)
ls members/staging/upfront/  # ~42 fichiers .json

# Pre-html
py archiver.py discover --source helloproject --era pre-html --group morningmusume
py archiver.py fetch    --source helloproject --era pre-html --group morningmusume
# → members/staging/pre-html/*.json : nameJa lisible, photos présentes

# Consolidate
py archiver.py consolidate
# → artist_registry.json peuplé
# → members/<id>.json d'un membre multi-sources :
#     sources: ["html", "pre-html", "upfront"]
#     images de plusieurs ères
#     details.生年月日 présent
```
