"""Load League of Legends patch notes via LangChain WebBaseLoader and split for indexing."""

import bs4
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..controllers.patches import PATCH_NOTES_BROWSER_HEADERS


def load_patch_notes_documents(url: str) -> list[Document]:
    """Fetch patch HTML and return Documents scoped to ``#patch-notes-container``."""
    loader = WebBaseLoader(
        web_paths=(url,),
        header_template=PATCH_NOTES_BROWSER_HEADERS,
        bs_kwargs={
            "parse_only": bs4.SoupStrainer(id="patch-notes-container"),
        },
    )
    return loader.load()


def split_patch_documents(
    docs: list[Document],
    *,
    patch_version: float,
    source_url: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 300,
) -> list[Document]:
    """Split loaded patch notes into chunks with metadata for Qdrant filtering."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    splits = splitter.split_documents(docs)
    for i, doc in enumerate(splits):
        doc.metadata["source"] = source_url
        doc.metadata["patch_version"] = patch_version
        doc.metadata["chunk_index"] = i
    return splits
