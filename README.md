# hp-database

Base de données personnelle Hello! Project — artistes, releases, collection physique, ISOs NAS.

## Prérequis

- Python 3.11+
- Le répertoire `scraper/` peuplé (voir `scraper/README.md` pour lancer le scraper)

## Installation

```powershell
# Créer et activer un venv
py -m venv .venv
.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r requirements.txt
```

## Configuration

Par défaut, l'appli utilise SQLite (`hp.db` à la racine). Pour changer :

```powershell
$env:DATABASE_URL = "sqlite:///hp.db"                        # SQLite (défaut)
$env:DATABASE_URL = "mysql+pymysql://user:pass@host/hp_db"   # MySQL
$env:NAS_ROOTS = "\\nas\isos,D:\isos"                        # dossiers ISO (optionnel)
```

## Importer les données du scraper

L'import est idempotent — il peut être relancé sans risque à tout moment. Les données personnelles (collection, ISOs) ne sont jamais écrasées.

```powershell
# Tout importer d'un coup (artistes + releases + résolution des songs)
py -m importer.import_scraper --all

# Importer uniquement les artistes (groupes + membres)
py -m importer.import_scraper --artists
py -m importer.import_scraper --members

# Importer toutes les releases (catalogue + détails)
py -m importer.import_scraper --releases

# Importer une seule release (par son ID scraper)
py -m importer.import_scraper --release 7506

# Importer une année complète
py -m importer.import_scraper --year 2025

# Résoudre les songs uniquement (regroupe les tracks identiques)
py -m importer.import_scraper --songs
```

### Ordre recommandé pour un premier import

```powershell
py -m importer.import_scraper --all
```

Cela exécute dans l'ordre : artistes → membres → catalogue → détails → résolution songs.

## Lancer le serveur web

```powershell
uvicorn webapp.main:app --reload
```

Ouvre ensuite [http://127.0.0.1:8000](http://127.0.0.1:8000).

Pour changer le port :

```powershell
uvicorn webapp.main:app --reload --port 8001
```

## Scanner les ISOs du NAS

```powershell
py -m nas.scan_iso --root "\\nas\isos"
```

## Migrations de base de données (Alembic)

```powershell
# Appliquer les migrations
alembic upgrade head

# Créer une nouvelle migration après modification des modèles
alembic revision --autogenerate -m "description"
```

## Structure du projet

```
importer/
  import_scraper.py   — CLI d'import depuis scraper/
nas/
  scan_iso.py         — scan des fichiers ISO sur le NAS
db/
  models.py           — modèles SQLAlchemy
  session.py          — engine + get_db()
  migrations/         — Alembic
webapp/
  main.py             — app FastAPI
  routes/             — artistes, releases, collection, ISOs, admin
  templates/          — Jinja2 (thème sombre)
scraper/              — données JSON générées par le scraper (source de vérité)
config.py             — DATABASE_URL, NAS_ROOTS, SCRAPER_DIR
```
