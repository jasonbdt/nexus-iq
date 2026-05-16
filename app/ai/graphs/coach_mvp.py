"""Coach MVP graph: LangGraph shell around the LangChain supervisor agent."""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.ai.nodes.supervisor import supervisor_node
from app.ai.schemas.state import CoachGraphState


def build_coach_graph() -> StateGraph:
    """Construct the uncompiled state graph (use for Mermaid / tests)."""
    graph = StateGraph(CoachGraphState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", END)
    return graph


@lru_cache(maxsize=1)
def get_coach_compiled_graph():
    """Singleton compiled graph (no checkpointer in MVP)."""
    return build_coach_graph().compile()


def coach_graph_mermaid() -> str:
    """Mermaid diagram for documentation / debugging."""
    return get_coach_compiled_graph().get_graph().draw_mermaid()
