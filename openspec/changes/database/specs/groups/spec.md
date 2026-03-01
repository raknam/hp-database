## ADDED Requirements

### Requirement: Table groups
La base de données DOIT contenir une table `groups` pour stocker les groupes et unités HP. Chaque groupe DOIT avoir un `id` (PK auto-increment), `name` (romaji, NOT NULL, UNIQUE), `name_ja` (japonais, nullable), `group_type` (ENUM: `group`, `unit`, `shuffle`, `solo`), `started_date` (DATE, nullable), `ended_date` (DATE, nullable), et les timestamps `created_at`/`updated_at`.

#### Scenario: Création d'un groupe actif
- **WHEN** on insère un groupe avec `name` = "Morning Musume", `group_type` = "group", `started_date` = "1997-09-14", `ended_date` = NULL
- **THEN** le groupe est créé et `ended_date` NULL indique qu'il est toujours actif

#### Scenario: Création d'une unité shuffle terminée
- **WHEN** on insère un groupe avec `name` = "Puripuri Pink", `group_type` = "shuffle", `started_date` = "2003-01-01", `ended_date` = "2003-12-31"
- **THEN** le groupe est créé avec ses dates de début et fin

#### Scenario: Validation du group_type
- **WHEN** on tente d'insérer un groupe avec `group_type` = "orchestra"
- **THEN** l'insertion échoue (valeur ENUM invalide)

### Requirement: Unicité du nom de groupe
La table `groups` DOIT avoir une contrainte UNIQUE sur `name`.

#### Scenario: Doublon refusé
- **WHEN** un groupe "ANGERME" existe déjà et on tente d'en insérer un autre avec le même `name`
- **THEN** l'insertion échoue (contrainte UNIQUE)
