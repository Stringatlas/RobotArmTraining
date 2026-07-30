from typing import Optional, List
from db import get_db_connection
from models.episode import EpisodeRecord

def _row_to_episode(row) -> EpisodeRecord:
    return EpisodeRecord(
        episode_id=row["episode_id"],
        batch_id=row["batch_id"],
        object_class=row["object_class"],
        language_instruction=row["language_instruction"],
        instruction_source=row["instruction_source"],
        success=bool(row["success"]),
        success_source=row["success_source"],
        hdf5_path=row["hdf5_path"],
        duration_s=row["duration_s"],
        n_frames=row["n_frames"],
        flagged_gap=bool(row["flagged_gap"]),
        yolo_confidence=row["yolo_confidence"],
        export_split=row["export_split"],
    )

def create_episode(episode: EpisodeRecord, db_path: Optional[str] = None) -> EpisodeRecord:
    """Insert a new episode record into SQLite."""
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO episodes (
                episode_id, batch_id, object_class, language_instruction,
                instruction_source, success, success_source, hdf5_path,
                duration_s, n_frames, flagged_gap, yolo_confidence, export_split
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode.episode_id,
                episode.batch_id,
                episode.object_class,
                episode.language_instruction,
                episode.instruction_source,
                1 if episode.success else 0,
                episode.success_source,
                episode.hdf5_path,
                episode.duration_s,
                episode.n_frames,
                1 if episode.flagged_gap else 0,
                episode.yolo_confidence,
                episode.export_split,
            ),
        )
        conn.commit()
    return episode

def get_episode(episode_id: str, db_path: Optional[str] = None) -> Optional[EpisodeRecord]:
    """Get an episode record by episode_id."""
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM episodes WHERE episode_id = ?", (episode_id,))
        row = cursor.fetchone()
        return _row_to_episode(row) if row else None

def update_episode_label(
    episode_id: str,
    success: Optional[bool] = None,
    language_instruction: Optional[str] = None,
    export_split: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """Update success state (setting success_source='human_override'), instruction, or export split."""
    fields = []
    values = []

    if success is not None:
        fields.append("success = ?")
        values.append(1 if success else 0)
        fields.append("success_source = ?")
        values.append("human_override")

    if language_instruction is not None:
        fields.append("language_instruction = ?")
        values.append(language_instruction)
        fields.append("instruction_source = ?")
        values.append("human_edited")

    if export_split is not None:
        fields.append("export_split = ?")
        values.append(export_split)

    if not fields:
        return False

    values.append(episode_id)
    query = f"UPDATE episodes SET {', '.join(fields)} WHERE episode_id = ?"

    with get_db_connection(db_path) as conn:
        cursor = conn.execute(query, tuple(values))
        conn.commit()
        return cursor.rowcount > 0

def list_episodes(
    batch_id: Optional[str] = None,
    object_class: Optional[str] = None,
    success: Optional[bool] = None,
    flagged_gap: Optional[bool] = None,
    export_split: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[str] = None,
) -> List[EpisodeRecord]:
    """List episodes filtered by batch_id, object_class, success, flagged_gap, export_split."""
    conditions = []
    values = []

    if batch_id is not None:
        conditions.append("batch_id = ?")
        values.append(batch_id)
    if object_class is not None:
        conditions.append("object_class = ?")
        values.append(object_class)
    if success is not None:
        conditions.append("success = ?")
        values.append(1 if success else 0)
    if flagged_gap is not None:
        conditions.append("flagged_gap = ?")
        values.append(1 if flagged_gap else 0)
    if export_split is not None:
        conditions.append("export_split = ?")
        values.append(export_split)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM episodes {where_clause} ORDER BY episode_id DESC LIMIT ? OFFSET ?"
    values.extend([limit, offset])

    with get_db_connection(db_path) as conn:
        cursor = conn.execute(query, tuple(values))
        rows = cursor.fetchall()
        return [_row_to_episode(row) for row in rows]
