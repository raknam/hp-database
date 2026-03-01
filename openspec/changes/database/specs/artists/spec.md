## ADDED Requirements

### Requirement: Table artists
La base de données DOIT contenir une table `artists` pour stocker les membres/solistes du Hello! Project. Chaque artiste DOIT avoir un `id` (PK auto-increment), `name` (romaji, NOT NULL), `name_ja` (japonais, nullable), `birthday` (DATE, nullable), et les timestamps `created_at`/`updated_at`.

#### Scenario: Création d'un artiste avec nom bilingue
- **WHEN** on insère un artiste avec `name` = "Fukumura Mizuki" et `name_ja` = "譜久村聖"
- **THEN** l'artiste est créé avec les deux noms et un `id` auto-généré

#### Scenario: Création d'un artiste sans nom japonais
- **WHEN** on insère un artiste avec `name` = "Jang Dayeon" et `name_ja` = NULL
- **THEN** l'artiste est créé avec `name_ja` NULL

#### Scenario: Nom romaji obligatoire
- **WHEN** on tente d'insérer un artiste avec `name` = NULL
- **THEN** l'insertion échoue (contrainte NOT NULL)

### Requirement: Unicité du nom
La table `artists` DOIT avoir une contrainte UNIQUE sur `name` pour éviter les doublons.

#### Scenario: Doublon refusé
- **WHEN** un artiste "Fukumura Mizuki" existe déjà et on tente d'en insérer un autre avec le même `name`
- **THEN** l'insertion échoue (contrainte UNIQUE)
