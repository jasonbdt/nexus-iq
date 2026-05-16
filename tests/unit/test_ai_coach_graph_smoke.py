"""Smoke test: coach graph structure (imports require OPENAI env like other tests)."""

from app.ai.graphs.coach_mvp import build_coach_graph, coach_graph_mermaid


def test_coach_graph_builds_and_mermaid_nonempty():
    """Compiled graph exposes expected node names in Mermaid export."""
    g = build_coach_graph()
    assert g is not None
    m = coach_graph_mermaid()
    assert "supervisor" in m
    assert "retrieve_patch_notes" not in m
    assert "__end__" in m
