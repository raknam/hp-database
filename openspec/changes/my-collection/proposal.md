## Why

Le catalogue HP est public, mais la gestion de collection est personnelle. Il faut pouvoir s'authentifier pour gérer sa propre collection (quelles éditions on possède). L'authentification via OIDC Google évite de gérer des mots de passe.

## What Changes

- Création d'une table `users` pour les utilisateurs authentifiés via OIDC Google (sub + email)
- Création d'une table `collection_items` pour le lien user↔édition (ownership simple avec notes)
- Ajout des pages de gestion de collection sur le site (dépend de la change `website`)
- Intégration du flow OIDC Google pour l'authentification

## Capabilities

### New Capabilities
- `users`: Table utilisateurs avec identifiant OIDC Google (sub) et email
- `collection`: Gestion de la collection personnelle — ajout/retrait d'éditions, notes, vue d'ensemble

### Modified Capabilities

_(aucune)_

## Impact

- Nouvelles migrations SQL dans `migrations/` (suite de la numérotation)
- Dépendance sur `editions` (change `database`) et sur le site web (change `website`)
- Ajout d'une dépendance externe : provider OIDC Google
- Gestion de sessions côté applicatif
