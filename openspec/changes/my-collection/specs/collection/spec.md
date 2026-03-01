## ADDED Requirements

### Requirement: Table collection_items
La base de données DOIT contenir une table `collection_items` pour stocker les éditions possédées par un utilisateur. Chaque entrée DOIT avoir un `id` (PK auto-increment), `user_id` (FK vers `users.id`, NOT NULL), `edition_id` (FK vers `editions.id`, NOT NULL), `notes` (TEXT, nullable), et les timestamps `created_at`/`updated_at`. Une contrainte UNIQUE DOIT exister sur `(user_id, edition_id)`.

#### Scenario: Ajout d'une édition à sa collection
- **WHEN** un utilisateur ajoute une édition à sa collection
- **THEN** une entrée est créée dans `collection_items` avec son `user_id` et l'`edition_id`

#### Scenario: Ajout avec notes
- **WHEN** un utilisateur ajoute une édition avec `notes` = "Acheté au concert de Budokan"
- **THEN** l'entrée est créée avec les notes

#### Scenario: Doublon refusé
- **WHEN** un utilisateur tente d'ajouter une édition qu'il possède déjà
- **THEN** l'insertion échoue (contrainte UNIQUE sur user_id + edition_id)

#### Scenario: Cascade sur suppression d'utilisateur
- **WHEN** un utilisateur est supprimé
- **THEN** toutes ses entrées de collection sont supprimées (ON DELETE CASCADE)

#### Scenario: Cascade sur suppression d'édition
- **WHEN** une édition est supprimée du catalogue
- **THEN** toutes les entrées de collection référençant cette édition sont supprimées (ON DELETE CASCADE)

### Requirement: Page ma collection
Le site DOIT fournir une page `/my-collection` accessible uniquement aux utilisateurs authentifiés, affichant la liste des éditions qu'ils possèdent avec les infos de la release associée (titre, cover, artistes/groupes).

#### Scenario: Consultation de sa collection
- **WHEN** un utilisateur connecté accède à `/my-collection`
- **THEN** la page affiche toutes les éditions qu'il possède, groupées ou triées par release

#### Scenario: Accès non authentifié
- **WHEN** un visiteur non connecté accède à `/my-collection`
- **THEN** il est redirigé vers la page de connexion

### Requirement: Ajout/retrait depuis la page release
Le site DOIT permettre à un utilisateur connecté d'ajouter ou retirer une édition de sa collection directement depuis la page détail d'une release (`/releases/:id`).

#### Scenario: Ajout d'une édition depuis la page release
- **WHEN** un utilisateur connecté clique sur "Ajouter" à côté d'une édition sur `/releases/:id`
- **THEN** l'édition est ajoutée à sa collection et le bouton change en "Retirer"

#### Scenario: Retrait d'une édition depuis la page release
- **WHEN** un utilisateur connecté clique sur "Retirer" à côté d'une édition qu'il possède
- **THEN** l'édition est retirée de sa collection et le bouton revient à "Ajouter"
