import os
import sqlite3

from app.paths import ensure_runtime_file

DB_PATH = ensure_runtime_file(os.path.join("app", "database", "kino.db"), seed_from_resource=True)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS comparisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            user_play TEXT NOT NULL,
            real_result TEXT NOT NULL,
            hit_count INTEGER NOT NULL,
            percentage REAL NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS draw_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            numbers TEXT NOT NULL,
            total_sum INTEGER NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trained_at TEXT NOT NULL,
            training_draws INTEGER NOT NULL,
            model_precision REAL NOT NULL,
            scores_json TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS strategy_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT,
            precision REAL,
            diff REAL,
            date TEXT
        )
        """
    )

    conn.commit()
    conn.close()
