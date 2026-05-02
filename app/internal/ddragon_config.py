"""Resolved paths and patch version for Data Dragon static assets."""

import os
from pathlib import Path


def ddragon_cdn_root() -> Path:
    """Directory whose children are patch folders (e.g. ``16.7.1/img``)."""
    raw = os.getenv("DDragon_CACHE_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    repo_root = Path(__file__).resolve().parent.parent.parent
    return (repo_root / "ddragon" / "cdn").resolve()


def ddragon_patch_version() -> str:
    """Patch folder name under the CDN root (must match frontend asset URLs)."""
    return os.getenv("DDRAGON_PATCH_VERSION", "16.7.1").strip()


def ddragon_data_path(locale_rel: str) -> Path:
    """Path under ``<cdn>/<patch>/data/...`` (e.g. ``en_US/summoner.json``)."""
    base = ddragon_cdn_root() / ddragon_patch_version() / "data"
    return (base / locale_rel).resolve()

