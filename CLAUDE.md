# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A comprehensive Hello! Project database with a personal collection management system. Hello! Project is a Japanese idol organization (Morning Musume, ANGERME, Juice=Juice, etc.).

**Goals:**
- Build a complete Hello! Project reference database (artists, releases, etc.)
- Provide personal collection tracking (CDs, DVDs, Blu-rays, photobooks)
- Expose the catalog via a public website, with authenticated collection management

**Current state:** Specification phase — 3 OpenSpec changes are defined and ready for implementation. No application code or schema exists yet. The `rsrc/` directory contains a legacy SQL dump from an existing personal collection (`kollektion`) that will serve as seed data later.

## OpenSpec Changes (implementation order)

### 1. `database` — Catalog schema (ready to apply)
MariaDB schema for the HP music catalog. Tables:
- `artists` (name, name_ja, birthday) — UNIQUE on name
- `groups` (name, name_ja, group_type ENUM, started_date, ended_date)
- `group_members` — N-M artists↔groups with joined_date/left_date (NULL = active)
- `releases` (title, title_ja, release_type ENUM, release_date, catalog_code UNIQUE) — catalog_code = code of the first disc, also used to locate cover image files on disk
- `release_artists` — N-M releases↔artists/groups with CHECK(artist_id XOR group_id)
- `editions` (name, media_type ENUM, catalog_code UNIQUE, barcode UNIQUE) — physical products linked to a release

Key design decisions:
- Covers are local files identified by release catalog_code (e.g. `covers/EPCE-5645.jpg`), not URLs in the DB
- media_type lives on editions, not releases (Limited A = CD+DVD, Regular = CD)
- Names are bilingual: `name` (romaji) + `name_ja` (Japanese, nullable)
- Pure SQL migrations in `migrations/` (001–006), no framework

### 2. `website` — Public catalog site (stack TBD)
Website to browse the HP catalog. Stack-agnostic spec (framework not chosen yet).
- Pages: artists, groups, releases (list + detail), search, covers
- Read-only public access, no admin UI
- Covers served as static files from `covers/` directory

### 3. `my-collection` — Auth + personal collection (depends on website)
Authentication via OIDC Google + personal collection management.
- `users` table (oidc_sub, email) — minimal, Google-only
- `collection_items` table — N-M users↔editions with optional notes, UNIQUE(user_id, edition_id)
- Pages: /my-collection, add/remove buttons on release pages, login/logout

## Database

- **Engine:** MariaDB 12.1.2+ with InnoDB
- **Character set:** `utf8mb4` / `utf8mb4_unicode_ci` throughout

### Legacy dump

```bash
mysql -u <user> -p kollektion < rsrc/kollektion.sql
```

The `rsrc/kollektion.sql` dump contains ~1,700 items in a flat `items` + `metadata` (key-value) structure. This is seed data for future migration into the new schema — do not modify it.

## Conventions

- **Working language:** French (conversations, specs, proposals), but all code, SQL, variable names, and technical identifiers are in English
- **Workflow:** OpenSpec for structured changes (`openspec/`). Use `/opsx:apply` to implement, `/opsx:propose` to create new changes.
- **Migrations:** Pure SQL files in `migrations/`, numbered sequentially (001, 002, …)
- **Covers:** Local image files identified by catalog_code, not stored in the DB

## Repository Layout

```
openspec/      Change management (proposals, designs, specs, tasks)
  changes/
    database/       Catalog schema — ready to implement
    website/        Public website — ready to implement
    my-collection/  Auth + collection — ready to implement
rsrc/          Legacy SQL dump (kollektion.sql)
```
