import psycopg2
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url is None:
        raise ValueError("DATABASE_URL not set!")

    # Парсим URL (Railway даёт URL вида postgresql://...)
    result = urlparse(db_url)

    return psycopg2.connect(
        host=result.hostname,
        port=result.port,
        database=result.path.lstrip("/"),
        user=result.username,
        password=result.password,
        sslmode="require"  # Railway требует SSL
    )
