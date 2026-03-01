## ADDED Requirements

### Requirement: Table group_members
La base de données DOIT contenir une table `group_members` pour modéliser la relation N-M entre artistes et groupes avec historique temporel. Chaque entrée DOIT avoir un `id` (PK auto-increment), `artist_id` (FK vers `artists.id`, NOT NULL), `group_id` (FK vers `groups.id`, NOT NULL), `joined_date` (DATE, nullable), `left_date` (DATE, nullable — NULL = membre actif), et les timestamps `created_at`/`updated_at`.

#### Scenario: Artiste rejoint un groupe
- **WHEN** on insère une entrée avec `artist_id` correspondant à "Fukumura Mizuki", `group_id` correspondant à "Morning Musume", `joined_date` = "2011-01-02", `left_date` = NULL
- **THEN** l'entrée est créée et indique que l'artiste est membre actif depuis cette date

#### Scenario: Artiste qui a gradué
- **WHEN** on insère une entrée avec `joined_date` = "2011-01-02" et `left_date` = "2023-12-11"
- **THEN** l'entrée est créée et indique une période de membership complète

#### Scenario: Artiste dans plusieurs groupes simultanément
- **WHEN** un artiste a une entrée active (left_date = NULL) dans "Morning Musume" et on insère une nouvelle entrée active pour "Morning Musume '24"
- **THEN** les deux entrées coexistent (un artiste peut être dans plusieurs groupes)

### Requirement: Intégrité référentielle membership
Les FK `artist_id` et `group_id` DOIVENT référencer respectivement `artists.id` et `groups.id` avec `ON DELETE CASCADE`.

#### Scenario: Suppression d'un artiste cascade sur membership
- **WHEN** on supprime un artiste qui a des entrées dans `group_members`
- **THEN** toutes ses entrées de membership sont supprimées automatiquement

#### Scenario: FK invalide refusée
- **WHEN** on tente d'insérer une entrée avec un `artist_id` qui n'existe pas dans `artists`
- **THEN** l'insertion échoue (contrainte FK)
