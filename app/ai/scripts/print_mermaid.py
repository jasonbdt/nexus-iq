"""Print the coach MVP LangGraph as Mermaid.

Usage (install dev deps first — see root README):

  uv run python -m app.ai.scripts.print_mermaid

Loads ``.env`` from the repository root so ``app.dependencies`` imports match
the backend configuration.
"""

from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")

from app.ai.graphs.coach_mvp import coach_graph_mermaid  # noqa: E402 pylint: disable=wrong-import-position


def main() -> None:
    """Write Mermaid diagram for the coach graph to stdout."""
    print(coach_graph_mermaid())


if __name__ == "__main__":
    main()
