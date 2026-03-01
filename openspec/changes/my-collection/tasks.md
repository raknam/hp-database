## 1. Migrations SQL

- [ ] 1.1 Migration `007_create_users.sql` — table `users` (id, oidc_sub UNIQUE, email, created_at, updated_at)
- [ ] 1.2 Migration `008_create_collection_items.sql` — table `collection_items` (id, user_id FK, edition_id FK, notes, created_at, updated_at) avec UNIQUE(user_id, edition_id) et ON DELETE CASCADE

## 2. Authentification OIDC Google

- [ ] 2.1 Configurer le client OIDC Google (client_id, client_secret, redirect_uri)
- [ ] 2.2 Implémenter le flow de connexion (redirect → callback → création/récupération user)
- [ ] 2.3 Implémenter la gestion de session (cookie/token selon le framework)
- [ ] 2.4 Implémenter la déconnexion

## 3. Pages collection

- [ ] 3.1 Page `/my-collection` — liste des éditions possédées avec infos release
- [ ] 3.2 Boutons ajout/retrait sur `/releases/:id` pour les utilisateurs connectés
- [ ] 3.3 Protection des routes authentifiées (redirect vers login si non connecté)
