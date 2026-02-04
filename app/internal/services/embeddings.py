import os

from openai import OpenAI


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def embed_text(text: str) -> list[float]:
    """Embed a single text using text-embedding-3-small."""
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL"),
        input=text
    )

    return response.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts in a batch."""
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL"),
        input=texts
    )

    return [item.embedding for item in response.data]
