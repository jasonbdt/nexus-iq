"""Download Riot Data Dragon (dragontail) into the CDN cache when enabled."""

from __future__ import annotations

import json
import logging
import os
import tarfile
import tempfile
from pathlib import Path

import requests

from .ddragon_config import ddragon_cdn_root

VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DRAGONTAIL_URL = "https://ddragon.leagueoflegends.com/cdn/dragontail-{version}.tgz"


def sync_on_start_enabled() -> bool:
    val = os.getenv("DDRAGON_SYNC_ON_START", "").strip().lower()
    return val in ("1", "true", "yes")


def _pick_version(log: logging.Logger) -> str:
    explicit = os.getenv("DDRAGON_PATCH_VERSION", "").strip()
    if explicit:
        return explicit
    resp = requests.get(VERSIONS_URL, timeout=60)
    resp.raise_for_status()
    versions = json.loads(resp.text)
    if not versions:
        raise RuntimeError("Empty versions list from Data Dragon API")
    chosen = versions[0]
    os.environ["DDRAGON_PATCH_VERSION"] = chosen
    log.warning(
        "DDRAGON_PATCH_VERSION unset; using latest API patch %s "
        "(ensure frontend CDN URLs use the same patch).",
        chosen,
    )
    return chosen


def _marker_path(cdn_root: Path, version: str) -> Path:
    return cdn_root / version / "data" / "en_US" / "summoner.json"


def ensure_ddragon_cached_sync(log: logging.Logger | None = None) -> None:
    """
    If DDRAGON_SYNC_ON_START is set, download dragontail when the patch folder
    is missing or incomplete.
    """
    log = log or logging.getLogger(__name__)
    if not sync_on_start_enabled():
        return

    cdn_root = ddragon_cdn_root()
    version = _pick_version(log)
    marker = _marker_path(cdn_root, version)
    if marker.is_file():
        log.info("Data Dragon patch %s already present under %s", version, cdn_root)
        return

    url = DRAGONTAIL_URL.format(version=version)
    log.info("Downloading Data Dragon %s from %s", version, url)
    cdn_root.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(suffix=".tgz", dir=str(cdn_root), delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with requests.get(url, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as out:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)

        with tarfile.open(tmp_path, "r:gz") as archive:
            archive.extractall(path=str(cdn_root), filter="data")

        if not marker.is_file():
            raise RuntimeError(
                f"Data Dragon sync finished but marker file missing: {marker}"
            )
        log.info("Data Dragon %s extracted to %s", version, cdn_root)
    finally:
        tmp_path.unlink(missing_ok=True)
