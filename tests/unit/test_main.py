"""Unit tests for main app routes."""

import pytest


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == 200
    assert "message" in data


def test_cdn_path_traversal_blocked(client, tmp_path):
    """Path traversal via ../ should return 403."""
    response = client.get("/cdn/../../../etc/passwd")
    assert response.status_code in (403, 404)


def test_cdn_nonexistent_dir_returns_404(client):
    """When DDragon cache dir does not exist, /cdn/... returns 404."""
    response = client.get("/cdn/img/champion/Aatrox.png")
    assert response.status_code == 404
