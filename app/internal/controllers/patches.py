import re

from bs4 import BeautifulSoup

from ..logging import get_logger
from ..session import get_session

logger = get_logger(__name__)


BASE_URL = "https://www.leagueoflegends.com/en-us/news/game-updates"
PATCH_LISTING_URL = "https://www.leagueoflegends.com/en-us/news/tags/patch-notes/"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def list_available_patches() -> list[dict]:
    """Return all patch-note entries found on the LoL news listing page.

    Each entry is a dict with keys ``version`` (e.g. ``"26.4"``) and
    ``url`` (the absolute URL to the patch notes article).
    """
    session = get_session()
    request = await session.get(PATCH_LISTING_URL, headers=_BROWSER_HEADERS)
    if not request.ok:
        logger.warning("Patch listing page returned %s", request.status)
        return []

    html = await request.text()
    soup = BeautifulSoup(html, "html.parser")

    patches: list[dict] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        # Match any slug that ends with a version-like pattern followed by -notes
        # e.g. /en-us/news/game-updates/patch-26-3-notes
        #      /en-us/news/game-updates/league-of-legends-patch-26-4-notes
        m = re.search(r"patch-(\d+)-(\d+)-notes", href)
        if not m:
            continue

        version = f"{m.group(1)}.{m.group(2)}"
        if version in seen:
            continue
        seen.add(version)

        absolute_url = (
            href if href.startswith("http")
            else f"https://www.leagueoflegends.com{href}"
        )
        patches.append({"version": version, "url": absolute_url})

    # Sort newest first (year desc, then patch number desc)
    patches.sort(
        key=lambda p: tuple(int(x) for x in p["version"].split(".")),
        reverse=True,
    )
    return patches


async def resolve_patch_url(patch_version: str) -> str | None:
    """Find the canonical URL for *patch_version* (e.g. ``"26.4"``) by
    consulting the live patch-notes listing page.

    Returns the absolute URL string, or ``None`` if not found.
    """
    patches = await list_available_patches()
    for entry in patches:
        if entry["version"] == patch_version:
            return entry["url"]
    return None


async def parse_patch_notes(patch_version: str):
    url = await resolve_patch_url(patch_version)

    if url is None:
        logger.warning("Could not resolve URL for patch %s", patch_version)
        return None

    logger.info("Fetching patch notes from %s", url)
    session = get_session()
    request = await session.get(url, headers=_BROWSER_HEADERS)

    if not request.ok:
        logger.warning("Patch notes page returned %s for %s", request.status, url)
        return None

    response = await request.text()
    soup = BeautifulSoup(response, "html.parser")
    patch_notes = soup.find("div", attrs={"id": "patch-notes-container"})

    if patch_notes is None:
        logger.warning("patch-notes-container not found at %s", url)
        return None

    all_chunks = []
    chunks = chunk_text(patch_notes.get_text(" ", strip=True))

    for i, chunk in enumerate(chunks):
        all_chunks.append({
            "text": chunk,
            "source": url,
            "chunk_index": i
        })

    return all_chunks


def chunk_text(text: str, max_chars: int = 1500, overlap: int = 300) -> list[str]:
    """Split *text* into overlapping chunks.

    Strategy:
    1. First split on champion/section boundaries (a word in Title Case followed
       by a second Title-Case word, preceded by whitespace — the pattern used
       throughout LoL patch notes for champion headings such as "Malphite",
       "Master Yi", "Nunu & Willump", etc.).
    2. If a section is still longer than *max_chars*, split it further with a
       sliding window so no context is lost.
    3. Adjacent sections that together fit within *max_chars* are merged so that
       short entries (e.g. a single-stat change) are not isolated.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return [text]

    # ── 1. Split on champion / section headings ───────────────────────────────
    # A heading is a sequence of 1-3 Title-Case words (possibly joined by "&")
    # that appears after a sentence-ending context (period, stat arrow, or the
    # very start of a section).  We look for the pattern:
    #   <space><UpperWord>[<space><UpperWord>]* followed by <space><UpperWord>
    # which reliably matches "Malphite M..." but not mid-sentence capitals.
    heading_re = re.compile(
        r'(?<=[a-z0-9)\]%])\s+(?=[A-Z][a-z])'   # after lowercase/digit → Title
    )

    sections = heading_re.split(text)

    # ── 2. Sub-split any section that exceeds max_chars ───────────────────────
    fine: list[str] = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            fine.append(section)
        else:
            # Sliding-window fallback for very long sections
            start = 0
            while start < len(section):
                end = min(start + max_chars, len(section))
                fine.append(section[start:end].strip())
                if end >= len(section):
                    break
                start = end - overlap

    # ── 3. Merge short adjacent sections so context is not fragmented ─────────
    merged: list[str] = []
    buf = ""
    for piece in fine:
        if not buf:
            buf = piece
        elif len(buf) + 1 + len(piece) <= max_chars:
            buf = buf + " " + piece
        else:
            merged.append(buf)
            # Start new buffer with overlap from previous chunk
            buf = buf[-overlap:] + " " + piece if overlap else piece

    if buf:
        merged.append(buf)

    return merged
