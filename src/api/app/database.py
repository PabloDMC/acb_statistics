import duckdb

from src.common.config import DATABASE_PATH

def get_connection():
    conn = duckdb.connect(DATABASE_PATH, read_only=True)
    return conn