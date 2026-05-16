#!/usr/bin/env python3
"""
migrate_structure.py — restructure scraper arborescence (Étape 2 du PLAN.md)

Opérations :
  1. Crée les nouveaux répertoires
  2. Copie les fichiers vers leur nouvelle destination
  3. Vérifie les comptes (aborte si mismatch)
  4. Supprime les originaux
  5. Génère artist_registry.json depuis former_discovered + ufw_artists_discovered

Utilisation :
  py migrate_structure.py [--dry-run]
"""

import argparse
import json
import shutil
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Répertoires source / destination
# ---------------------------------------------------------------------------

MEMBERS_DIR     = Path("members")
CACHE_DIR       = Path("cache")

STAGING_HTML    = MEMBERS_DIR / "staging" / "html"
STAGING_UFW     = MEMBERS_DIR / "staging" / "upfront"

CACHE_MBR_HTML  = CACHE_DIR / "members" / "html"
CACHE_REL_UFW   = CACHE_DIR / "releases" / "upfront"
CACHE_REL_HP    = CACHE_DIR / "releases" / "hp"

ARTIST_REGISTRY = MEMBERS_DIR / "artist_registry.json"

FORMER_DISC     = MEMBERS_DIR / "former_discovered.json"
UFW_DISC        = MEMBERS_DIR / "ufw_artists_discovered.json"

OLD_ARCHIVE     = CACHE_DIR / "archive"
OLD_UFW_CACHE   = CACHE_DIR / "upfront"


def normalize(name: str) -> str:
    return unicodedata.normalize("NFKC", name).strip()


def copy_files(pairs: list[tuple[Path, Path]], dry_run: bool) -> list[tuple[Path, Path]]:
    """Copy src → dst for each pair. Returns list of copied pairs."""
    done = []
    for src, dst in pairs:
        if not src.exists():
            print(f"  WARN missing: {src}")
            continue
        if dry_run:
            print(f"  COPY {src} → {dst}")
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        done.append((src, dst))
    return done


def verify_copies(pairs: list[tuple[Path, Path]]) -> bool:
    ok = True
    for src, dst in pairs:
        if not dst.exists():
            print(f"  ERROR missing dst: {dst}")
            ok = False
        elif dst.stat().st_size != src.stat().st_size:
            print(f"  ERROR size mismatch: {dst}")
            ok = False
    return ok


def delete_originals(pairs: list[tuple[Path, Path]], dry_run: bool) -> None:
    for src, _ in pairs:
        if dry_run:
            print(f"  DEL {src}")
        elif src.exists():
            src.unlink()


# ---------------------------------------------------------------------------
# Étape A : membres has_grad → staging/html/<slug>.json
# ---------------------------------------------------------------------------

def migrate_html_members(dry_run: bool) -> list[tuple[Path, Path]]:
    pairs = []
    for f in sorted(MEMBERS_DIR.glob("*.json")):
        if f.name in ("former_discovered.json", "ufw_artists_discovered.json", "artist_registry.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  WARN cannot parse {f.name}: {e}")
            continue
        if d.get("has_grad"):
            slug = d.get("slug")
            if not slug:
                print(f"  WARN no slug in {f.name}, skipping")
                continue
            dst = STAGING_HTML / f"{slug}.json"
            pairs.append((f, dst))
    print(f"[A] html members : {len(pairs)} fichiers")
    return pairs


# ---------------------------------------------------------------------------
# Étape B : membres source:upfront → staging/upfront/<slug>.json
# ---------------------------------------------------------------------------

def migrate_upfront_members(dry_run: bool) -> list[tuple[Path, Path]]:
    pairs = []
    for f in sorted(MEMBERS_DIR.glob("*.json")):
        if f.name in ("former_discovered.json", "ufw_artists_discovered.json", "artist_registry.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("source") == "upfront":
            slug = d.get("slug")
            if not slug:
                print(f"  WARN no slug in {f.name}, skipping")
                continue
            dst = STAGING_UFW / f"{slug}.json"
            pairs.append((f, dst))
    print(f"[B] upfront members : {len(pairs)} fichiers")
    return pairs


# ---------------------------------------------------------------------------
# Étape C : cache/archive/* → cache/members/html/*
# ---------------------------------------------------------------------------

def migrate_archive_cache(dry_run: bool) -> list[tuple[Path, Path]]:
    if not OLD_ARCHIVE.exists():
        print("[C] cache/archive/ absent — skip")
        return []
    pairs = [(f, CACHE_MBR_HTML / f.name) for f in OLD_ARCHIVE.iterdir() if f.is_file()]
    print(f"[C] archive cache : {len(pairs)} fichiers")
    return pairs


# ---------------------------------------------------------------------------
# Étape D : cache/upfront/* → cache/releases/upfront/*
# ---------------------------------------------------------------------------

def migrate_upfront_cache(dry_run: bool) -> list[tuple[Path, Path]]:
    if not OLD_UFW_CACHE.exists():
        print("[D] cache/upfront/ absent — skip")
        return []
    pairs = [(f, CACHE_REL_UFW / f.name) for f in OLD_UFW_CACHE.iterdir() if f.is_file()]
    print(f"[D] upfront cache : {len(pairs)} fichiers")
    return pairs


# ---------------------------------------------------------------------------
# Étape E : cache/<id>.html (numériques) → cache/releases/hp/<id>.html
# ---------------------------------------------------------------------------

def migrate_hp_cache(dry_run: bool) -> list[tuple[Path, Path]]:
    pairs = []
    for f in CACHE_DIR.iterdir():
        if f.is_file() and f.suffix == ".html" and f.stem.isdigit():
            pairs.append((f, CACHE_REL_HP / f.name))
    print(f"[E] HP release cache : {len(pairs)} fichiers")
    return pairs


# ---------------------------------------------------------------------------
# Étape F : générer artist_registry.json
# ---------------------------------------------------------------------------

def build_artist_registry(dry_run: bool) -> None:
    registry: dict[str, dict] = {}

    # --- former_discovered.json ---
    if FORMER_DISC.exists():
        raw = json.loads(FORMER_DISC.read_text(encoding="utf-8"))
        # format: { group: [ { slug, group, nameJa, nameKana, firstSeen, lastSeen, ... } ] }
        for group, members in raw.items():
            for m in members:
                name = normalize(m.get("nameJa", ""))
                slug = m.get("slug", "")
                if not name:
                    continue
                entry = registry.setdefault(name, {"slug": slug, "eras": {}})
                if not entry["slug"] and slug:
                    entry["slug"] = slug
                html_era: dict = {"group": m.get("group", group)}
                if m.get("firstSeen"):
                    html_era["firstSeen"] = m["firstSeen"][:8]  # trim to YYYYMMDD
                if m.get("lastSeen"):
                    html_era["lastSeen"] = m["lastSeen"][:8]
                entry["eras"]["html"] = html_era
    else:
        print("  WARN former_discovered.json absent")

    # --- ufw_artists_discovered.json ---
    if UFW_DISC.exists():
        raw = json.loads(UFW_DISC.read_text(encoding="utf-8"))
        # format: [ { slug, nameJa } ]
        for m in raw:
            name = normalize(m.get("nameJa", ""))
            slug = m.get("slug", "")
            if not name:
                continue
            entry = registry.setdefault(name, {"slug": slug, "eras": {}})
            if not entry["slug"] and slug:
                entry["slug"] = slug
            entry["eras"]["upfront"] = {"slug": slug}
    else:
        print("  WARN ufw_artists_discovered.json absent")

    count = len(registry)
    print(f"[F] artist_registry : {count} entrées")

    if not dry_run:
        ARTIST_REGISTRY.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"    écrit → {ARTIST_REGISTRY}")
    else:
        print(f"    (dry-run) aurait écrit {ARTIST_REGISTRY}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool) -> None:
    print(f"{'=== DRY RUN ===' if dry_run else '=== MIGRATION ==='}")
    print()

    all_pairs: list[tuple[Path, Path]] = []

    all_pairs += migrate_html_members(dry_run)
    all_pairs += migrate_upfront_members(dry_run)
    all_pairs += migrate_archive_cache(dry_run)
    all_pairs += migrate_upfront_cache(dry_run)
    all_pairs += migrate_hp_cache(dry_run)

    print()
    print(f"Total fichiers à migrer : {len(all_pairs)}")

    if dry_run:
        print("\n(dry-run : aucune modification)")
        build_artist_registry(dry_run=True)
        return

    # Copy
    print("\n--- Copie ---")
    copied = copy_files(all_pairs, dry_run=False)

    # Verify
    print("--- Vérification ---")
    if not verify_copies(copied):
        print("ERREUR : vérification échouée. Originaux conservés.")
        sys.exit(1)
    print(f"  OK — {len(copied)} fichiers vérifiés")

    # Delete originals
    print("--- Suppression des originaux ---")
    delete_originals(copied, dry_run=False)

    # Remove now-empty source dirs
    for old_dir in (OLD_ARCHIVE, OLD_UFW_CACHE):
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
            print(f"  rmdir {old_dir}")

    # artist_registry.json
    print("\n--- artist_registry.json ---")
    build_artist_registry(dry_run=False)

    # Keep former_discovered / ufw_artists_discovered for reference (don't delete)
    print("\nMigration terminée.")
    print("Note : former_discovered.json et ufw_artists_discovered.json sont conservés.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Affiche les opérations sans les exécuter")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
