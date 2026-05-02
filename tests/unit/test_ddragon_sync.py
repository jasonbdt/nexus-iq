"""Tests for Data Dragon startup sync."""


def test_sync_skipped_when_disabled(monkeypatch, tmp_path):
    monkeypatch.delenv("DDRAGON_SYNC_ON_START", raising=False)
    monkeypatch.setenv("DDragon_CACHE_DIR", str(tmp_path))

    from app.internal.ddragon_sync import ensure_ddragon_cached_sync

    ensure_ddragon_cached_sync()
    assert not any(tmp_path.iterdir()) or not (tmp_path / "16.7.1").exists()


def test_sync_skips_when_marker_present(monkeypatch, tmp_path):
    monkeypatch.setenv("DDRAGON_SYNC_ON_START", "true")
    monkeypatch.setenv("DDRAGON_PATCH_VERSION", "16.7.1")
    monkeypatch.setenv("DDragon_CACHE_DIR", str(tmp_path))
    marker = tmp_path / "16.7.1" / "data" / "en_US" / "summoner.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")

    from app.internal import ddragon_sync

    called = []

    def _fail(*_a, **_k):
        called.append(True)
        raise AssertionError("requests should not run when cache is warm")

    monkeypatch.setattr(ddragon_sync.requests, "get", _fail)

    ddragon_sync.ensure_ddragon_cached_sync()
    assert not called


def test_ddragon_data_path_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DDragon_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("DDRAGON_PATCH_VERSION", "16.7.1")

    from app.internal.ddragon_config import ddragon_data_path

    expected = (tmp_path / "16.7.1" / "data" / "en_US" / "summoner.json").resolve()
    assert ddragon_data_path("en_US/summoner.json").resolve() == expected
