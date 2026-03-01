## Context

Les changes `database` (schéma catalogue) et `website` (site public) fournissent le socle. Cette change ajoute l'authentification utilisateur et la gestion de collection personnelle par-dessus.

Les utilisateurs s'authentifient via OIDC Google. On stocke le minimum : identifiant OIDC (`sub`) et email. La collection est un lien simple user↔édition avec notes optionnelles.

## Goals / Non-Goals

**Goals:**
- Table `users` avec identifiant OIDC Google et email
- Table `collection_items` reliant user↔édition avec notes optionnelles
- Flow d'authentification OIDC Google sur le site
- Pages de gestion de collection (voir sa collection, ajouter/retirer des éditions)

**Non-Goals:**
- Multi-provider OIDC (seulement Google)
- Wishlist
- Métadonnées enrichies sur la collection (condition, prix, date d'acquisition)
- Administration ou modération
- Partage public de sa collection

## Decisions

### 1. Identifiant OIDC : champ `oidc_sub`

La table `users` stocke le `sub` du token OIDC Google dans `oidc_sub` (VARCHAR, UNIQUE, NOT NULL). C'est l'identifiant stable de Google — il ne change jamais, contrairement à l'email.

**Alternative considérée :** Table séparée `user_identities` pour supporter plusieurs providers. Rejeté — on ne supporte que Google pour l'instant.

### 2. Collection = join table user↔édition

```
users ──N:M──▶ editions
      via collection_items
      (notes nullable)
```

Contrainte UNIQUE sur `(user_id, edition_id)` — un utilisateur ne peut posséder la même édition qu'une seule fois.

### 3. Pages collection (authentifiées)

```
/my-collection             → Vue d'ensemble de sa collection
/releases/:id              → Bouton "Ajouter à ma collection" (si connecté)
/login                     → Redirection vers OIDC Google
/logout                    → Déconnexion
```

Les pages collection ne sont accessibles qu'aux utilisateurs authentifiés. Le reste du site reste public.

## Risks / Trade-offs

- **Single provider OIDC** → Refactoring nécessaire si on ajoute d'autres providers. Acceptable pour le moment.
- **Pas de partage de collection** → La collection est privée. Fonctionnalité de partage possible plus tard.
- **Sessions** → Le mécanisme de session (cookie, JWT) dépendra du framework choisi dans la change `website`.
