import os


APP_ENV = os.getenv("APP_ENV", "dev")

DB_USER = os.getenv("DATABASE_USER")
DB_NAME = os.getenv("DATABASE_NAME")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_URL=f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@nexus-iq-database-1/{DB_NAME}"

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRES_IN"))

RIOT_API_KEY = os.getenv("RIOT_API_KEY")
RIOT_API_BASE = "https://!PLATFORM_OR_REGION!.api.riotgames.com"
SUMMONER_TTL_MINUTES = 0.5
