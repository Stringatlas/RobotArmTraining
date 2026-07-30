CREATE_BATCHES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id TEXT PRIMARY KEY,
    object_class TEXT NOT NULL,
    created_at TEXT NOT NULL,
    target_episodes INTEGER NOT NULL,
    completed_episodes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    randomization_params TEXT NOT NULL DEFAULT '{}',
    target_hz REAL NOT NULL DEFAULT 30.0
);
"""

CREATE_EPISODES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    object_class TEXT NOT NULL,
    language_instruction TEXT NOT NULL,
    instruction_source TEXT NOT NULL DEFAULT 'auto_template',
    success INTEGER NOT NULL DEFAULT 1,
    success_source TEXT NOT NULL DEFAULT 'auto',
    hdf5_path TEXT NOT NULL,
    duration_s REAL NOT NULL DEFAULT 0.0,
    n_frames INTEGER NOT NULL DEFAULT 0,
    flagged_gap INTEGER NOT NULL DEFAULT 0,
    yolo_confidence REAL,
    export_split TEXT NOT NULL DEFAULT 'unassigned',
    FOREIGN KEY (batch_id) REFERENCES batches(batch_id) ON DELETE CASCADE
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_episodes_batch_id ON episodes(batch_id);",
    "CREATE INDEX IF NOT EXISTS idx_episodes_object_class ON episodes(object_class);",
    "CREATE INDEX IF NOT EXISTS idx_episodes_success ON episodes(success);",
    "CREATE INDEX IF NOT EXISTS idx_episodes_export_split ON episodes(export_split);"
]
