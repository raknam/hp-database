# CONSOLIDATION.md — Logique de merge des ères

Doc de référence pour `archiver.py consolidate`. Décrit les règles de priorité, le format `artist_registry.json`, et comment étendre la consolidation.

---

## Vue d'ensemble

La consolidation fusionne les données de plusieurs ères Wayback (+ UFW) en un seul fichier `members/<id>.json` par membre. Elle est non-destructive : les fichiers staging ne sont pas supprimés.

```
members/staging/html/<slug>.json      (html, 2014–2025, priorité haute)
members/staging/pre-html/<slug>.json  (pre-html, 2012–2014, priorité moyenne)
members/staging/upfront/<slug>.json   (upfront, priorité basse)
          ↓
members/<id>.json                     (consolidé, champ sources: [...])
```

---

## Règles de priorité par champ

| Champ        | html | pre-html | upfront | Notes |
|--------------|------|----------|---------|-------|
| `nameJa`     | ✓ prio 1 | ✓ prio 2 | ✓ prio 3 | Premier non-vide gagne |
| `nameKana`   | ✓ prio 1 | ✓ prio 2 | — | Absent UFW |
| `color`      | ✓ seulement | — | — | Présent uniquement ère html |
| `bio`        | — | — | ✓ seulement | Présent uniquement UFW |
| `details`    | ✓ prio 1 | ✓ prio 2 (setdefault) | — | Absent UFW |
| `images`     | union | union | union | Dédup par `Path(url).name` |
| `archivedUrl`| ✓ depuis html | — | — | |
| `sources`    | toujours présent | si staging existant | si staging existant | |

**Règle générale :** pour un champ scalaire, prendre la valeur de la source la plus prioritaire qui la contient. Pour `images`, union de toutes les sources avec déduplication sur le nom de fichier.

---

## Algorithme (cmd_consolidate)

1. Charger `artist_registry.json`
2. Itérer sur `staging/html/*.json` (source principale)
3. Pour chaque slug :
   a. Lire `staging/html/<slug>.json` → base du résultat
   b. Si `staging/pre-html/<slug>.json` existe → merger (nameJa/nameKana si manquants, details en setdefault, images)
   c. Si `staging/upfront/<slug>.json` existe et `kind == "artist"` → merger (nameJa si manquant, bio, images)
   d. Écrire `members/<id>.json` (id = `slug_to_id(slug)` = MD5 900000–999998)
4. Mettre à jour `artist_registry.json` avec nameJa confirmé si non présent

---

## Format `artist_registry.json`

```json
{
  "高橋愛": {
    "slug": "takahashi_ai",
    "eras": {
      "html":     { "group": "morningmusume", "firstSeen": "20140424", "lastSeen": "20141005" },
      "pre-html": { "group": "morningmusume" },
      "upfront":  { "slug": "takahashi_ai" }
    }
  },
  "__pre_slug__takahashi_ai": {
    "slug": "takahashi_ai",
    "eras": { "pre-html": { "group": "morningmusume" } }
  }
}
```

- Clés normales : `nameJa` (NFKC-normalisé) — membre dont le nom est connu
- Clés `__pre_slug__<slug>` : membre pre-html dont le nameJa n'est pas encore résolu (à résoudre après fetch)
- Mis à jour par : `migrate_structure.py` (initial), `discover --era pre-html`, `consolidate`

### Initialisation

`migrate_structure.py` construit le registre initial depuis :
- `former_discovered.json` → ères html (nameJa connu, firstSeen/lastSeen)
- `ufw_artists_discovered.json` → ère upfront (nameJa connu, slug)

### Mise à jour par discover pre-html

`discover --source helloproject --era pre-html` ajoute des entrées `__pre_slug__` pour chaque slug trouvé dans les URLs CDX. Le nameJa sera résolu lors du fetch (parsing du HTML Shift-JIS).

### Résolution des `__pre_slug__`

Après `fetch --era pre-html`, les fichiers `staging/pre-html/<slug>.json` contiennent le `nameJa` parsé. `consolidate` peut alors fusionner et nettoyer le registre.

---

## Commande consolidate

```powershell
py archiver.py consolidate                # tous les membres html staging
py archiver.py consolidate --slug takahashi_ai
py archiver.py consolidate --force        # écrase même si target existe déjà
```

`--force` nécessaire si un membre actif (pas `has_grad`) occupe déjà le slot `members/<id>.json`.

---

## Ajout de l'ère flash (futur)

Quand `staging/flash/` sera peuplé :
1. Ajouter `STAGING_FLASH_DIR` à la boucle de merge dans `cmd_consolidate`
2. Priorité : html > pre-html > flash > upfront
3. Parser : à définir (structure Flash différente, probablement texte brut ou XML)
4. Ajouter `"flash"` à `SOURCE_ERAS["helloproject"]` (déjà fait)

---

## Ajout de nouveaux champs

Pour ajouter un champ ex. `nameEn` depuis une nouvelle source :
1. Vérifier dans quelle ère il est disponible
2. Ajouter la logique dans `cmd_consolidate` au bloc correspondant
3. Mettre à jour ce doc + `SCRAPER.md` schéma membres

---

## Déduplication members actifs vs graduées

Cas particulier : un membre peut être à la fois dans `members/<id>.json` (actif, mis par `scraper.py`) et dans `staging/html/` (gradué, mis par `archiver.py fetch`).

Logique actuelle :
- Si `members/<id>.json` existe et `has_grad` est absent → membre actif → skip (sauf `--force`)
- Après graduation, relancer `consolidate --slug <slug>` pour consolider

Clé de match entre actif et graduée : `slug` (identique entre les deux sources).
