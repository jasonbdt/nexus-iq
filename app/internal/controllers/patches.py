import re

from bs4 import BeautifulSoup

from ..logging import get_logger
from ..session import get_session

logger = get_logger(__name__)


BASE_URL = "https://www.leagueoflegends.com/en-us/news/game-updates"

async def parse_patch_notes(patch_version: float):
    session = get_session()
    patch_version = str(patch_version).replace('.', '-')
    request = await session.get(f"{BASE_URL}/patch-{patch_version}-notes/")

    if not request.ok:
        return None

    response = await request.text()
    soup = BeautifulSoup(response, "html.parser")
    patch_notes = soup.find("div", attrs={"id": "patch-notes-container"})

    all_chunks = []
    chunks = chunk_text(patch_notes.get_text(" ", strip=True))

    for i, chunk in enumerate(chunks):
        all_chunks.append({
            "text": chunk,
            "source": f"{BASE_URL}/patch-{patch_version}-notes/",
            "chunk_index": i
        })

    return all_chunks


def chunk_text(text: str, max_chars: int = 450, overlap: int = 75) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text]

    start = 0
    chunks = []

    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks
