import json
from typing import Optional, List
from db import get_db_connection
from models.episode import BatchRecord

def _row_to_batch(row) -> BatchRecord:
    return BatchRecord(
        batch_id=row["batch_id"],
        object_class=row["object_class"],
        created_at=row["created_at"],
        target_episodes=row["target_episodes"],
        completed_episodes=row["completed_episodes"],
        status=row["status"],
        randomization_params=row["randomization_params"],
        target_hz=row["target_hz"],
    )

def create_batch(batch: BatchRecord, db_path: Optional[str] = None) -> BatchRecord:
    """Insert a new batch record into SQLite."""
    params_str = batch.randomization_params
    if isinstance(params_str, dict):
        params_str = json.dumps(params_str)

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO batches (
                batch_id, object_class, created_at, target_episodes,
                completed_episodes, status, randomization_params, target_hz
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.batch_id,
                batch.object_class,
                batch.created_at,
                batch.target_episodes,
                batch.completed_episodes,
                batch.status,
                params_str,
                batch.target_hz,
            ),
        )
        conn.commit()
    return batch

def get_batch(batch_id: str, db_path: Optional[str] = None) -> Optional[BatchRecord]:
    """Get a batch record by batch_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM batches WHERE batch_id = ?", (batch_id,))
        row = cursor.fetchone()
        return _row_to_batch(row) if row else None

def update_batch_status(batch_id: str, status: str, db_path: Optional[str] = None) -> bool:
    """Update status of a batch ('running', 'paused', 'completed', 'crashed')."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE batches SET status = ? WHERE batch_id = ?",
            (status, batch_id),
        )
        conn.commit()
        return cursor.rowcount > 0

def increment_completed_episodes(batch_id: str, db_path: Optional[str] = None) -> int:
    """Increment the completed_episodes count for a batch and return the new count."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE batches SET completed_episodes = completed_episodes + 1 WHERE batch_id = ?",
            (batch_id,),
        )
        conn.commit()
        cursor = conn.execute(
            "SELECT completed_episodes FROM batches WHERE batch_id = ?", (batch_id,)
        )
        row = cursor.fetchone()
        return row["completed_episodes"] if row else 0

def list_batches(limit: int = 100, db_path: Optional[str] = None) -> List[BatchRecord]:
    """List batches ordered by created_at descending."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM batches ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        return [_row_to_batch(row) for row in rows]
