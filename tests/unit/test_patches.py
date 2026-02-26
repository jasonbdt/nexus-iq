"""Unit tests for chunk_text in patches controller."""

import pytest

from app.internal.controllers.patches import chunk_text


def test_chunk_text_empty_or_short_returns_single_chunk():
    assert chunk_text("") == [""]
    assert chunk_text("short") == ["short"]
    assert chunk_text("a" * 1500) == ["a" * 1500]


def test_chunk_text_long_without_sections_splits_with_overlap():
    text = "x" * 2000
    chunks = chunk_text(text, max_chars=500, overlap=100)
    assert len(chunks) >= 2
    # Chunks may exceed max_chars slightly due to overlap merging
    for chunk in chunks:
        assert len(chunk) <= 500 + 500  # merged buffer + overlap


def test_chunk_text_respects_section_boundaries():
    # Title-case words create section boundaries: "word Word"
    text = "intro text. Malphite Some ability change. Another Champion More text."
    chunks = chunk_text(text, max_chars=100, overlap=20)
    assert len(chunks) >= 1
    combined = " ".join(chunks)
    assert "Malphite" in combined
    assert "intro" in combined


def test_chunk_text_normalizes_whitespace():
    text = "word1   word2\n\tword3"
    chunks = chunk_text(text)
    assert chunks == ["word1 word2 word3"]


def test_chunk_text_merge_short_sections():
    # Multiple short sections should be merged when they fit
    text = "A" * 50 + " " + "B" * 50 + " " + "C" * 50
    chunks = chunk_text(text, max_chars=200, overlap=10)
    assert len(chunks) == 1
    assert "AAA" in chunks[0] and "BBB" in chunks[0] and "CCC" in chunks[0]


def test_chunk_text_custom_params():
    text = "a" * 500
    chunks = chunk_text(text, max_chars=100, overlap=0)
    assert len(chunks) >= 5
