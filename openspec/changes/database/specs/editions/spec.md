## ADDED Requirements

### Requirement: Table editions
La base de données DOIT contenir une table `editions` pour stocker les produits physiques liés à une release. Chaque édition DOIT avoir un `id` (PK auto-increment), `release_id` (FK vers `releases.id`, NOT NULL), `name` (VARCHAR, NOT NULL — ex: "Limited Edition A", "Regular Edition"), `media_type` (ENUM: `CD`, `DVD`, `Blu-ray`, `CD+DVD`, `CD+Blu-ray`, `photobook`, `other`), `catalog_code` (VARCHAR, nullable, UNIQUE — ex: "EPCE-5645"), `barcode` (VARCHAR(13), nullable, UNIQUE — EAN-13), et les timestamps `created_at`/`updated_at`.

#### Scenario: Création d'une édition limitée CD+DVD
- **WHEN** on insère une édition avec `release_id` valide, `name` = "Limited Edition A", `media_type` = "CD+DVD", `catalog_code` = "EPCE-5645", `barcode` = "4942463564520"
- **THEN** l'édition est créée et liée à sa release

#### Scenario: Création d'une édition régulière CD seul
- **WHEN** on insère une édition pour la même release avec `name` = "Regular Edition", `media_type` = "CD", un autre `catalog_code` et `barcode`
- **THEN** l'édition est créée — une release peut avoir plusieurs éditions

#### Scenario: Édition sans barcode connu
- **WHEN** on insère une édition avec `barcode` = NULL et `catalog_code` = NULL
- **THEN** l'édition est créée (les deux sont nullables)

### Requirement: Unicité des identifiants physiques
`catalog_code` et `barcode` DOIVENT chacun avoir une contrainte UNIQUE (quand non-NULL) pour éviter les doublons de produits physiques.

#### Scenario: Doublon de barcode refusé
- **WHEN** une édition avec `barcode` = "4942463564520" existe déjà et on tente d'en insérer une autre avec le même barcode
- **THEN** l'insertion échoue (contrainte UNIQUE)

#### Scenario: Doublon de catalog_code refusé
- **WHEN** une édition avec `catalog_code` = "EPCE-5645" existe déjà et on tente d'en insérer une autre avec le même code
- **THEN** l'insertion échoue (contrainte UNIQUE)

### Requirement: Intégrité référentielle editions→releases
La FK `release_id` DOIT référencer `releases.id` avec `ON DELETE CASCADE`.

#### Scenario: Suppression d'une release cascade sur éditions
- **WHEN** on supprime une release qui a des éditions
- **THEN** toutes ses éditions sont supprimées automatiquement
