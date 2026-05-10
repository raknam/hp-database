import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
SCRAPER_DIR = BASE_DIR / "scraper"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'hp.db'}")
NAS_ROOTS: list[str] = [r for r in os.getenv("NAS_ROOTS", "").split(",") if r]
SITE_URL = "https://helloproject.com"
