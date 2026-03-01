## Why

Le projet a besoin d'un schéma relationnel pour modéliser le catalogue musical du Hello! Project. Actuellement il n'existe aucun schéma — seulement un dump SQL legacy (`rsrc/kollektion.sql`) avec une structure plate items + metadata clé-valeur qui ne permet pas d'exprimer les relations entre artistes, groupes, releases et éditions. Ce schéma est le socle sur lequel tout le reste sera construit : site web, import de données, et plus tard gestion de collection personnelle.

## What Changes

- Création du schéma MariaDB pour le catalogue musical HP : artistes, groupes, releases, éditions physiques
- Modélisation de l'appartenance artistes↔groupes en N-M avec dates (join/left) pour capturer l'évolution constante des groupes HP
- Scripts de migration SQL pour créer le schéma from scratch
- Encodage `utf8mb4`/`utf8mb4_unicode_ci` partout (le japonais est omniprésent)

## Capabilities

### New Capabilities
- `artists`: Artistes/membres — données biographiques, noms en romaji et japonais
- `groups`: Groupes et unités — nom, période d'activité, type (groupe, unité, shuffle, solo)
- `membership`: Relation N-M artistes↔groupes avec dates de join/graduation
- `releases`: Releases musicales — singles, albums, best-of, etc.
- `editions`: Produits physiques liés à une release — chacun avec son propre code catalogue et barcode

### Modified Capabilities

_(aucune — premier schéma)_

## Impact

- Nouveaux scripts de migration SQL dans un répertoire `migrations/`
- Le dump existant `rsrc/kollektion.sql` n'est pas modifié (servira de source de données dans une spec future)
- Pas de code applicatif — cette spec est schema-only
