"""Shared RAG context-building helper used by the coach and RAG routers."""

from .embeddings import embed_text
from .llm import DeterminedPatchVersions
from .vector_store import search_similar


async def build_rag_context(
    question: str,
    patch_versions: DeterminedPatchVersions,
    keywords: list[str] | None,
    top_k: int = 15,
) -> str:
    """Embed *question*, search for similar patch-note chunks, and return a formatted context string.

    Args:
        question: The user question (or resolved question) to embed.
        patch_versions: Version range filter returned by ``determine_patch_versions``.
        keywords: Optional keyword list returned by ``extract_keywords``.
        top_k: Maximum number of chunks to include in the context.

    Returns:
        A single string with each matching chunk prefixed by its patch version,
        separated by horizontal rules.
    """
    query_embedding = await embed_text(question)
    results = await search_similar(
        query_embedding, patch_versions, top_k=top_k, keywords=keywords or None
    )
    parts = [f"[Patch {r['patch_version']}]\n{r['text']}" for r in results]
    return "\n\n---\n\n".join(parts)
