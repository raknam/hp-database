from pathlib import Path


def image_subpath(filename: str) -> Path:
    """Return aa/bb/rest path for a filename — used to shard the images/ directory."""
    return Path(filename[:2]) / filename[2:4] / filename[4:]
