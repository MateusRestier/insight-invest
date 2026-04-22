import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

def get_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "stocks"),
        user=os.getenv("DB_USER", "user"),
        password=os.getenv("DB_PASS", "password"),
        port=os.getenv("DB_PORT", "5432")
    )
    conn.autocommit = True  # garante leitura dos dados mais recentes (sem transação implícita)
    return conn
