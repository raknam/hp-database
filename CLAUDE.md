# hp-database

Local web app to browse Hello! Project releases, manage a physical collection, and open ISOs on NAS directly in VLC.

## Memory

Project context, architecture decisions, known gaps, and user preferences are documented in `.claude/memory/`. Read `MEMORY.md` there for the index. These files are gitignored and local only.

## Quick start

```bat
run-debug.bat        # starts uvicorn --reload on port 8001
```

## Key commands

```powershell
py -m importer.import_scraper --all                          # import (catalogue: current+next year only)
py -m importer.import_scraper --all --incremental            # only changed release files
py -m importer.import_scraper --all --all-years              # initial setup: catalogue all years
py -m nas.scan_iso --root "T:\J-Music\Hello!Pro"  # index ISOs
py -m nas.scan_iso --root "T:\J-Music\Hello!Pro" --debug
```

## Stack

FastAPI · SQLAlchemy 2.x (sync) · SQLite WAL · Alembic · Jinja2 · HTMX
