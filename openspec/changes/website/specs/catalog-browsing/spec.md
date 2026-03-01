## ADDED Requirements

### Requirement: Page liste des artistes
Le site DOIT fournir une page `/artists` affichant la liste de tous les artistes du catalogue, avec leur nom (romaji) et nom japonais.

#### Scenario: Consultation de la liste des artistes
- **WHEN** un visiteur accède à `/artists`
- **THEN** la page affiche la liste de tous les artistes triés alphabétiquement par `name`

### Requirement: Page détail artiste
Le site DOIT fournir une page `/artists/:id` affichant les informations d'un artiste : nom, nom japonais, date de naissance, groupes (actuels et passés avec dates), et releases associées.

#### Scenario: Consultation d'un artiste existant
- **WHEN** un visiteur accède à `/artists/:id` avec un id valide
- **THEN** la page affiche les infos de l'artiste, ses groupes avec dates de join/left, et ses releases

#### Scenario: Artiste inexistant
- **WHEN** un visiteur accède à `/artists/:id` avec un id invalide
- **THEN** le site retourne une page 404

### Requirement: Page liste des groupes
Le site DOIT fournir une page `/groups` affichant la liste de tous les groupes avec leur nom, type, et période d'activité.

#### Scenario: Consultation de la liste des groupes
- **WHEN** un visiteur accède à `/groups`
- **THEN** la page affiche tous les groupes triés alphabétiquement par `name`

### Requirement: Page détail groupe
Le site DOIT fournir une page `/groups/:id` affichant les informations d'un groupe : nom, nom japonais, type, période d'activité, membres (actuels et anciens avec dates), et discographie.

#### Scenario: Consultation d'un groupe existant
- **WHEN** un visiteur accède à `/groups/:id` avec un id valide
- **THEN** la page affiche les infos du groupe, ses membres avec dates, et sa discographie

#### Scenario: Distinction membres actuels et anciens
- **WHEN** un visiteur consulte la page d'un groupe qui a des membres actifs (`left_date` NULL) et des anciens membres
- **THEN** la page sépare les membres actuels des anciens membres

### Requirement: Page liste des releases
Le site DOIT fournir une page `/releases` affichant la liste des releases avec titre, type, date, et artistes/groupes associés.

#### Scenario: Consultation de la liste des releases
- **WHEN** un visiteur accède à `/releases`
- **THEN** la page affiche les releases triées par date de sortie (plus récentes en premier)

#### Scenario: Filtrage par type de release
- **WHEN** un visiteur filtre par `release_type` (ex: "single")
- **THEN** seules les releases de ce type sont affichées

### Requirement: Page détail release
Le site DOIT fournir une page `/releases/:id` affichant les informations d'une release : titre, titre japonais, type, date, artistes/groupes, cover, et liste des éditions avec leur media_type, catalog_code et barcode.

#### Scenario: Consultation d'une release avec éditions
- **WHEN** un visiteur accède à `/releases/:id` avec un id valide
- **THEN** la page affiche les infos de la release, sa cover, et la liste de ses éditions

### Requirement: Recherche dans le catalogue
Le site DOIT fournir une page `/search` permettant de rechercher par mots-clés dans les artistes, groupes et releases (noms romaji et japonais, titres).

#### Scenario: Recherche avec résultats
- **WHEN** un visiteur cherche "Morning Musume"
- **THEN** les résultats affichent le groupe, ses membres, et ses releases correspondants

#### Scenario: Recherche sans résultat
- **WHEN** un visiteur cherche un terme qui ne correspond à rien
- **THEN** la page affiche un message indiquant qu'aucun résultat n'a été trouvé
