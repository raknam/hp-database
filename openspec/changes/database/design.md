## Context

Le projet part de zéro — pas de code applicatif, pas de schéma. Le seul asset existant est un dump phpMyAdmin (`rsrc/kollektion.sql`) contenant ~1 700 items dans une structure plate `items` + `metadata` (clé-valeur). Ce dump sera migré plus tard mais n'est pas concerné par cette spec.

Le domaine est le Hello! Project, une organisation d'idoles japonaises où les groupes évoluent constamment : les membres rejoignent (souvent par "générations" numérotées), graduent, passent d'un groupe à l'autre, et participent à des unités temporaires ou des shuffles.

Une release (single, album) peut avoir plusieurs éditions physiques (Limited A, Regular, etc.), chacune avec son propre code catalogue et barcode. Une release peut impliquer plusieurs groupes/artistes (collaborations, shuffle units).

Cible : MariaDB 12.1.2+, `utf8mb4`/`utf8mb4_unicode_ci`.

## Goals / Non-Goals

**Goals:**
- Schéma relationnel normalisé pour le catalogue musical HP : artistes, groupes, membership, releases, éditions
- Relation N-M artistes↔groupes avec historique temporel (join/graduation)
- Relation N-M releases↔artistes/groupes pour les collaborations
- Noms bilingues (romaji + japonais) sur artistes et groupes
- Media type porté par l'édition (pas par la release)
- Scripts de migration SQL exécutables from scratch

**Non-Goals:**
- Code applicatif, API, ou UI
- Import de données depuis le dump legacy
- Chansons / tracklists
- Labels / maisons de disques
- Collection personnelle (spec séparée avec auth OIDC)
- Concerts, événements, tournées
- Multi-utilisateur

## Decisions

### 1. Relation N-M artistes↔groupes via `group_members`

```
artists ──N:M──▶ groups
         via group_members
         (joined_date, left_date)
```

Un artiste peut appartenir à plusieurs groupes simultanément ou successivement. `left_date` NULL = membre actif. Pas de champ "generation" pour l'instant (pourra être ajouté).

**Pourquoi N-M plutôt que 1-N :** C'est la réalité du HP — Sayashi Riho est passée par Morning Musume puis ANGERME. Les membres de shuffle units appartiennent à leur groupe principal en même temps.

### 2. Relation N-M releases↔artistes/groupes via `release_artists`

Une release peut impliquer plusieurs artistes ou groupes. La join table `release_artists` lie une release soit à un `artist_id`, soit à un `group_id` (l'un des deux, pas les deux).

**Alternative considérée :** FK simple `group_id` sur `releases`. Rejetée car les collaborations et shuffles sont fréquents dans le HP.

### 3. catalog_code sur releases + covers en fichiers locaux

La release porte un `catalog_code` (le code du premier disque, ex: "EPCE-5645") qui sert à la fois d'identifiant métier et de clé pour retrouver la cover sur le filesystem (convention de nommage, ex: `covers/EPCE-5645.jpg`). Pas de colonne cover/URL en base — les images sont stockées localement.

Chaque édition a aussi son propre `catalog_code` et `barcode` (identifiants du produit physique spécifique).

```
releases (logique)        editions (physique)
┌──────────────┐         ┌──────────────────┐
│ title        │──1:N──▶ │ name (Limited A)  │
│ release_date │         │ catalog_code      │
│ catalog_code │         │ barcode           │
│ release_type │         │ media_type (CD…)  │
└──────────────┘         └──────────────────┘
```

Le `media_type` est sur l'édition car pour un même single, Limited A peut être CD+DVD et Regular CD seul.

### 4. Noms bilingues : `name` + `name_ja`

Artistes et groupes ont `name` (romaji, ex: "Fukumura Mizuki") et `name_ja` (japonais, ex: "譜久村聖"). `name_ja` est nullable (certaines unités ont des noms en anglais uniquement).

### 5. ENUMs pour les ensembles bornés

- `releases.release_type` : `single`, `album`, `best_of`, `mini_album`, `other`
- `editions.media_type` : `CD`, `DVD`, `Blu-ray`, `CD+DVD`, `CD+Blu-ray`, `photobook`, `other`
- `groups.group_type` : `group`, `unit`, `shuffle`, `solo`

**Pourquoi ENUM :** Intégrité des données au niveau DB. Ces valeurs sont propres au domaine et changent rarement. Extensible via `ALTER TABLE MODIFY COLUMN` si besoin.

### 6. Organisation des migrations

Un répertoire `migrations/` avec des fichiers SQL numérotés séquentiellement :
- `001_create_artists.sql`
- `002_create_groups.sql`
- etc.

Pas de framework de migration (Flyway, Liquibase) pour l'instant — des scripts SQL purs exécutables avec le client `mysql`.

## Risks / Trade-offs

- **ENUM rigidité** → Acceptable. Les valeurs sont stables dans le domaine HP. Extension simple via ALTER TABLE.
- **Pas de generation sur group_members** → Choix délibéré de garder le schéma minimal. Ajout futur via ALTER TABLE ADD COLUMN sans impact.
- **release_artists avec artist_id XOR group_id** → Un peu moins propre qu'un polymorphisme, mais simple et explicite. CHECK constraint pour garantir qu'exactement un des deux est non-NULL.
- **Pas de soft deletes** → Hard deletes avec CASCADE. Acceptable pour un outil personnel/référence.
