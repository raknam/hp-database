## ADDED Requirements

### Requirement: Table releases
La base de données DOIT contenir une table `releases` pour stocker les releases musicales (entités logiques). Chaque release DOIT avoir un `id` (PK auto-increment), `title` (VARCHAR, NOT NULL), `title_ja` (VARCHAR, nullable), `release_type` (ENUM: `single`, `album`, `best_of`, `mini_album`, `other`), `release_date` (DATE, nullable), `catalog_code` (VARCHAR, nullable, UNIQUE — code catalogue du premier disque, ex: "EPCE-5645", sert aussi à identifier le fichier cover sur le filesystem), et les timestamps `created_at`/`updated_at`.

#### Scenario: Création d'un single
- **WHEN** on insère une release avec `title` = "Suki da Suki da Suki da", `release_type` = "single", `release_date` = "2024-10-02"
- **THEN** la release est créée avec un `id` auto-généré

#### Scenario: Release sans date connue
- **WHEN** on insère une release avec `release_date` = NULL
- **THEN** la release est créée (la date est nullable)

#### Scenario: Validation du release_type
- **WHEN** on tente d'insérer une release avec `release_type` = "EP"
- **THEN** l'insertion échoue (valeur ENUM invalide)

### Requirement: Table release_artists (N-M releases↔artistes/groupes)
La base de données DOIT contenir une table `release_artists` pour lier les releases aux artistes et/ou groupes qui y participent. Chaque entrée DOIT avoir un `id` (PK), `release_id` (FK vers `releases.id`, NOT NULL), `artist_id` (FK vers `artists.id`, nullable), `group_id` (FK vers `groups.id`, nullable). Exactement un des deux (`artist_id` ou `group_id`) DOIT être non-NULL (CHECK constraint).

#### Scenario: Release d'un groupe
- **WHEN** on insère une entrée `release_artists` avec `release_id` valide, `group_id` correspondant à "Morning Musume", `artist_id` = NULL
- **THEN** l'entrée est créée, liant la release au groupe

#### Scenario: Release collaboration multi-groupes
- **WHEN** on insère deux entrées pour la même `release_id` — une avec `group_id` "Morning Musume" et une avec `group_id` "ANGERME"
- **THEN** les deux entrées coexistent, la release est attribuée aux deux groupes

#### Scenario: Contrainte XOR artist/group
- **WHEN** on tente d'insérer une entrée avec `artist_id` = NULL ET `group_id` = NULL
- **THEN** l'insertion échoue (CHECK constraint : exactement un doit être non-NULL)

#### Scenario: Cascade sur suppression de release
- **WHEN** on supprime une release qui a des entrées dans `release_artists`
- **THEN** toutes les entrées associées dans `release_artists` sont supprimées (ON DELETE CASCADE)
