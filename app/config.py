"""Environment configuration loaded by the composition root, never at import time."""
# One immutable record for the existing deployment configuration.
# pylint: disable=too-many-instance-attributes
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings retaining the existing environment variable names."""

    app_env: str
    database_url: str = field(repr=False)
    jwt_secret: str = field(repr=False)
    jwt_minutes: int
    riot_key: str = field(repr=False)
    redis_host: str
    openai_key: str = field(repr=False)
    embedding_model: str
    qdrant_host: str
    qdrant_port: int
    collection: str
    dimension: int
    namespace: str = field(repr=False)
    top_k: int

    @classmethod
    def from_environment(cls):
        """Read environment variables only when an API or worker starts."""
        user, password, name = (os.getenv(key) for key in
                                ('DATABASE_USER', 'DATABASE_PASSWORD', 'DATABASE_NAME'))
        return cls(
            app_env=os.getenv('APP_ENV', 'dev'),
            database_url=f'postgresql+psycopg2://{user}:{password}@nexus-iq-database-1/{name}',
            jwt_secret=os.environ['JWT_SECRET'], jwt_minutes=int(os.environ['JWT_EXPIRES_IN']),
            riot_key=os.environ['RIOT_API_KEY'], redis_host=os.getenv('REDIS_HOST', 'localhost'),
            openai_key=os.environ['OPENAI_API_KEY'],
            embedding_model=os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small'),
            qdrant_host=os.environ['QDRANT_HOST'], qdrant_port=int(os.environ['QDRANT_PORT']),
            collection=os.environ['QDRANT_COLLECTION_NAME'],
            dimension=int(os.environ['EMBEDDING_DIMENSION']), namespace=os.environ['APP_KEY'],
            top_k=int(os.getenv('TOP_K', '5')),
        )
