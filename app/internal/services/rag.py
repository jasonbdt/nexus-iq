"""Shared RAG retrieval used by coach and RAG routers (retrieve → context string).

Follows the two-step pattern from LangChain RAG docs: similarity search, then the
caller runs generation with ``app.internal.services.llm``.
"""

from .llm import DeterminedPatchVersions
from .vector_store import patch_notes_query_filter, patch_vector_store


async def build_rag_context(
    question: str,
    patch_versions: DeterminedPatchVersions,
    keywords: list[str] | None,
    top_k: int = 15,
) -> str:
    """Retrieve similar patch-note chunks and return a context string.

    Step 1 (retrieve): ``QdrantVectorStore.similarity_search`` with version / keyword
    filters. Step 2 (generate) is performed by the caller via ``llm`` helpers.
    """
    store = patch_vector_store()
    qfilter = patch_notes_query_filter(patch_versions, keywords or None)
    docs = await store.asimilarity_search(
        query=question,
        k=top_k,
        filter=qfilter,
    )
    parts = []
    for doc in docs:
        pv = doc.metadata.get("patch_version", "")
        parts.append(f"[Patch {pv}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)
