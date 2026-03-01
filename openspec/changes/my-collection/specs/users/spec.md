## ADDED Requirements

### Requirement: Table users
La base de données DOIT contenir une table `users` pour stocker les utilisateurs authentifiés. Chaque utilisateur DOIT avoir un `id` (PK auto-increment), `oidc_sub` (VARCHAR, NOT NULL, UNIQUE — identifiant subject du token OIDC Google), `email` (VARCHAR, NOT NULL), et les timestamps `created_at`/`updated_at`.

#### Scenario: Création d'un utilisateur à la première connexion
- **WHEN** un utilisateur se connecte via OIDC Google pour la première fois avec `sub` = "1234567890" et `email` = "user@gmail.com"
- **THEN** un enregistrement est créé dans `users` avec ces valeurs

#### Scenario: Unicité du sub OIDC
- **WHEN** un utilisateur avec `oidc_sub` = "1234567890" existe déjà et on tente d'en créer un autre avec le même `oidc_sub`
- **THEN** l'insertion échoue (contrainte UNIQUE)

### Requirement: Authentification OIDC Google
Le site DOIT permettre aux utilisateurs de se connecter via OIDC Google. Le flow DOIT rediriger vers Google, récupérer le token ID, extraire `sub` et `email`, et créer ou retrouver l'utilisateur correspondant.

#### Scenario: Première connexion
- **WHEN** un visiteur clique sur "Se connecter" et s'authentifie via Google
- **THEN** un compte utilisateur est créé et l'utilisateur est connecté sur le site

#### Scenario: Connexion ultérieure
- **WHEN** un utilisateur déjà enregistré se connecte via Google
- **THEN** l'utilisateur est retrouvé par son `oidc_sub` et connecté

#### Scenario: Déconnexion
- **WHEN** un utilisateur connecté clique sur "Se déconnecter"
- **THEN** sa session est détruite et il est redirigé vers la page d'accueil
