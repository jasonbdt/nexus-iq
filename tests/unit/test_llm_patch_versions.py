"""Tests for patch-version range extraction and normalization."""

# Pytest injects fixtures by name into test parameters (pylint sees shadowing).
# pylint: disable=redefined-outer-name

from types import SimpleNamespace

import pytest

from app.internal.controllers import patches as patches_controller
from app.internal.services.llm import DeterminedPatchVersions, determine_patch_versions


@pytest.fixture
def patch_structured_output(monkeypatch):
    """Replace the structured-output runnable with a fixed return value."""

    def _apply(out: DeterminedPatchVersions) -> None:
        monkeypatch.setattr(
            "app.internal.services.llm._patch_versions_llm",
            SimpleNamespace(invoke=lambda *_a, **_kw: out),
        )

    return _apply


def test_determine_patch_versions_raises_stale_lte_to_catalog_latest(
    patch_structured_output,
):
    """Stale lte from an old default max is replaced when catalog latest is known."""
    patch_structured_output(DeterminedPatchVersions(gte=26.7, lte=26.4))
    result = determine_patch_versions(
        "Welche Änderungen gab es ab Patch 26.7 bis zum aktuellsten Patch?",
        catalog_latest_patch=26.9,
    )
    assert result.gte == 26.7
    assert result.lte == 26.9


def test_determine_patch_versions_keeps_explicit_upper_below_latest(
    patch_structured_output,
):
    """Explicit lte below catalog latest must stay unchanged."""
    patch_structured_output(DeterminedPatchVersions(gte=26.7, lte=26.8))
    result = determine_patch_versions(
        "Changes from 26.7 through 26.8?",
        catalog_latest_patch=26.9,
    )
    assert result.gte == 26.7
    assert result.lte == 26.8


@pytest.mark.asyncio
async def test_get_latest_patch_version_float_cached(monkeypatch):
    """Listing is called once; second read uses the in-process TTL cache."""
    patches_controller.clear_latest_patch_version_cache()
    calls = {"n": 0}

    async def fake_list():
        calls["n"] += 1
        return [
            {"version": "26.9", "url": "https://example/a"},
            {"version": "26.7", "url": "https://example/b"},
        ]

    monkeypatch.setattr(patches_controller, "list_available_patches", fake_list)
    assert await patches_controller.get_latest_patch_version_float() == 26.9
    assert calls["n"] == 1
    assert await patches_controller.get_latest_patch_version_float() == 26.9
    assert calls["n"] == 1
