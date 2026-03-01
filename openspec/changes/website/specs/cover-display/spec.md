## ADDED Requirements

### Requirement: Affichage de la cover d'une release
Le site DOIT afficher l'image de couverture d'une release en se basant sur son `catalog_code`. Le fichier image est stocké localement dans un répertoire `covers/` et nommé d'après le catalog_code (ex: `covers/EPCE-5645.jpg`).

#### Scenario: Cover existante
- **WHEN** une release a un `catalog_code` = "EPCE-5645" et le fichier `covers/EPCE-5645.jpg` existe
- **THEN** l'image est affichée sur la page de la release et dans les listes

#### Scenario: Cover absente
- **WHEN** une release a un `catalog_code` mais aucun fichier cover correspondant n'existe
- **THEN** un placeholder (image par défaut) est affiché à la place

#### Scenario: Release sans catalog_code
- **WHEN** une release a un `catalog_code` NULL
- **THEN** un placeholder est affiché
