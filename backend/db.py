import os
import sqlite3
from typing import Optional
from config import settings
from models.db_models import CREATE_BATCHES_TABLE_SQL, CREATE_EPISODES_TABLE_SQL, CREATE_INDEXES_SQL

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite database connection with row factory and WAL mode enabled."""
    path = db_path or settings.sqlite_db_path
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(CREATE_BATCHES_TABLE_SQL)
        cursor.execute(CREATE_EPISODES_TABLE_SQL)
        for index_sql in CREATE_INDEXES_SQL:
            cursor.execute(index_sql)
        conn.commit()
