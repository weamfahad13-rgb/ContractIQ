from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from contractiq.config import DATABASE_URL

SCHEMA = Path(__file__).with_name("schema.sql")


def connect() -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    register_vector(conn)
    return conn


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text(encoding="utf-8"))
