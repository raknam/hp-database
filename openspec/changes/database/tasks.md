## 1. Structure du projet

- [ ] 1.1 Créer le répertoire `migrations/`

## 2. Tables de base (sans FK)

- [ ] 2.1 Migration `001_create_artists.sql` — table `artists` (id, name, name_ja, birthday, created_at, updated_at) avec UNIQUE sur name
- [ ] 2.2 Migration `002_create_groups.sql` — table `groups` (id, name, name_ja, group_type ENUM, started_date, ended_date, created_at, updated_at) avec UNIQUE sur name

## 3. Table de membership

- [ ] 3.1 Migration `003_create_group_members.sql` — table `group_members` (id, artist_id FK, group_id FK, joined_date, left_date, created_at, updated_at) avec ON DELETE CASCADE sur les deux FK

## 4. Tables releases et éditions

- [ ] 4.1 Migration `004_create_releases.sql` — table `releases` (id, title, title_ja, release_type ENUM, release_date, catalog_code UNIQUE nullable, created_at, updated_at)
- [ ] 4.2 Migration `005_create_release_artists.sql` — table `release_artists` (id, release_id FK, artist_id FK nullable, group_id FK nullable, created_at, updated_at) avec CHECK constraint XOR artist_id/group_id, ON DELETE CASCADE
- [ ] 4.3 Migration `006_create_editions.sql` — table `editions` (id, release_id FK, name, media_type ENUM, catalog_code UNIQUE nullable, barcode UNIQUE nullable, created_at, updated_at) avec ON DELETE CASCADE

## 5. Validation

- [ ] 5.1 Script `migrations/run_all.sh` pour exécuter toutes les migrations dans l'ordre
- [ ] 5.2 Tester l'exécution complète sur une base vide
