# CLAUDE.md

Scraper Hello! Project → JSON local. `scraper.py` = site actif ; `archiver.py` = Wayback Machine + up-front-works.jp.  
Référence complète (commandes, schémas, arborescence) : **`SCRAPER.md`**.

## Conventions non-évidentes

- `artist_list.json` : les noms sont dans `profilesById[id].nameJa/nameEn`, **pas** dans `artistsById`.
- `artistRelation[group_id]` : `kind: "unit"` = sous-groupe (ex. BEYOOOOONDS → CHICA#TETSU). Résolution récursive nécessaire pour lister les vrais membres.
- `color` membre : objet `{ "name": "...", "hex": "#..." }`, pas une string.
- IDs synthétiques : 900000–999998 = anciennes membres Wayback (MD5 du slug) ; 800000–899998 = artistes UFW (MD5 de `"ufw:" + slug`).
- `archiver.py consolidate` écrit dans `members/<id>.json` (ID synthétique), pas dans `staging/`.
- `has_grad: true` dans `members/<id>.json` = membre graduée consolidée.

## Pitfalls

- Anciens `<year>_releases.json` (années 2000–2010) : JSON invalide (caractères de contrôle). `update` sauvegarde le texte brut et warn si parse impossible.
- `track.credits` et `track.suffix` : absents si vides — ne pas assumer `null`.
- Tous les scripts s'exécutent depuis `scraper/` (chemins relatifs au CWD).
- `collect_ids` lit `releases/*_releases.json` — lancer `update` d'abord si ces fichiers manquent.
- Images membres actifs : peuvent contenir des URLs Wayback si enrichis par `enrich --images`.
