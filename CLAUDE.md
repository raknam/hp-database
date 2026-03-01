# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A comprehensive Hello! Project database with a personal collection management system. Hello! Project is a Japanese idol organization (Morning Musume, ANGERME, Juice=Juice, etc.).

**Goals:**
- Build a complete Hello! Project reference database (artists, releases, etc.)
- Provide personal collection tracking (CDs, DVDs, Blu-rays, photobooks)

**Current state:** Early stage — the `rsrc/` directory contains a SQL dump from an existing personal collection (`kollektion`) that serves as seed data.

## Database

- **Engine:** MariaDB 12.1.2+ with InnoDB
- **Character set:** `utf8mb4` / `utf8mb4_unicode_ci` throughout
- **Dump tool:** phpMyAdmin 5.2.3 (French locale)

### Restoring

```bash
mysql -u <user> -p kollektion < rsrc/kollektion.sql
```

Ensure the target MySQL/MariaDB client uses UTF-8 — the data contains Japanese text (titles, artist names).

## Schema

Two tables with a one-to-many relationship:

### `items`
The core collection registry. Each row is a physical media item identified by EAN-13 `barcode` and Japanese catalog `code` (e.g. `EPCE-5645`). Both columns have UNIQUE constraints but are nullable.

- `status` — tracks sync state with an external data source: `new`, `updated`, `not_online`
- `kind` — media origin: `Japanese` (default), `South Korea`, `Movie`, `Game`, `Unknown`

### `metadata`
Key-value store for item attributes. `item_id` references `items.id` with `ON DELETE CASCADE`.

Common keys: `cover` (image URL from CDJapan/Neowing), `group` (artist), `title`, `type` (CD, DVD, Blu-ray, BOOK, etc.), `release_date`.

## Conventions

- **Working language:** French (conversations, comments in specs/proposals), but all code, SQL, variable names, and technical identifiers are in English
- **Workflow:** OpenSpec for structured changes (`openspec/`)

## Repository Layout

```
openspec/      Change management (proposals, designs, specs, tasks)
rsrc/          SQL dump files
```
