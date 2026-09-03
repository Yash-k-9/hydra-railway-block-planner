"""
HYDRA - SQLite Database Layer
Uses Python's built-in sqlite3. No ORM.
"""

import os
import sqlite3

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BACKEND_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "data", "hydra.db")


def get_connection(db_path=None):
    """Return a sqlite3 connection with row_factory set to Row."""
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path=None):
    """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS maintenance_tasks (
        task_id         TEXT PRIMARY KEY,
        source_system   TEXT NOT NULL,
        department      TEXT NOT NULL,
        asset_id        TEXT,
        location_km     REAL,
        corridor_id     TEXT NOT NULL,
        task_type       TEXT,
        description     TEXT,
        severity        INTEGER,
        asset_criticality INTEGER,
        safety_impact   INTEGER,
        overdue_days    INTEGER DEFAULT 0,
        urgency         REAL DEFAULT 0,
        train_impact    REAL DEFAULT 0,
        duration_minutes INTEGER,
        requires_isolation INTEGER DEFAULT 0,
        due_date        TEXT,
        priority_score  REAL DEFAULT 0,
        priority_level  TEXT DEFAULT '',
        status          TEXT DEFAULT 'pending'
    );

    CREATE TABLE IF NOT EXISTS train_movements (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        train_id        TEXT NOT NULL,
        train_type      TEXT,
        corridor_id     TEXT NOT NULL,
        date            TEXT NOT NULL,
        start_time      TEXT NOT NULL,
        end_time        TEXT NOT NULL,
        is_confirmed    INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS blocks (
        block_id        TEXT PRIMARY KEY,
        plan_type       TEXT NOT NULL,        -- 'optimized' or 'baseline'
        corridor_id     TEXT NOT NULL,
        date            TEXT NOT NULL,
        start_time      TEXT NOT NULL,
        end_time        TEXT NOT NULL,
        duration_minutes INTEGER,
        departments     TEXT,                 -- comma-separated
        requires_isolation INTEGER DEFAULT 0,
        utilization     REAL DEFAULT 0,
        status          TEXT DEFAULT 'generated'
    );

    CREATE TABLE IF NOT EXISTS block_tasks (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        block_id        TEXT NOT NULL,
        task_id         TEXT NOT NULL,
        FOREIGN KEY (block_id) REFERENCES blocks(block_id),
        FOREIGN KEY (task_id) REFERENCES maintenance_tasks(task_id)
    );

    CREATE TABLE IF NOT EXISTS resources (
        resource_id     TEXT PRIMARY KEY,
        department      TEXT NOT NULL,
        name            TEXT NOT NULL,
        is_available    INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS simulation_events (
        event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type      TEXT NOT NULL,
        parameters      TEXT,                 -- JSON string
        created_at      TEXT,
        applied         INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS optimization_results (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_type       TEXT NOT NULL,
        total_blocks    INTEGER,
        total_block_hours REAL,
        tasks_completed INTEGER,
        critical_completed INTEGER,
        bundled_tasks   INTEGER,
        overdue_remaining INTEGER,
        optimization_time REAL,
        objective_value REAL,
        created_at      TEXT
    );
    """)

    conn.commit()
    return conn


def reset_db(db_path=None):
    """Drop and recreate all tables."""
    conn = get_connection(db_path)
    cur = conn.cursor()
    for table in ["block_tasks", "blocks", "simulation_events",
                   "optimization_results", "train_movements",
                   "resources", "maintenance_tasks"]:
        cur.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    conn.close()
    return init_db(db_path)


def insert_tasks(conn, tasks):
    """Insert a list of task dicts into maintenance_tasks table."""
    cur = conn.cursor()
    for t in tasks:
        cur.execute("""
            INSERT OR REPLACE INTO maintenance_tasks
            (task_id, source_system, department, asset_id, location_km,
             corridor_id, task_type, description, severity, asset_criticality,
             safety_impact, overdue_days, urgency, train_impact,
             duration_minutes, requires_isolation, due_date,
             priority_score, priority_level, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            t["task_id"], t["source_system"], t["department"],
            t.get("asset_id", ""), t.get("location_km", 0),
            t["corridor_id"], t.get("task_type", ""),
            t.get("description", ""),
            t.get("severity", 0), t.get("asset_criticality", 0),
            t.get("safety_impact", 0), t.get("overdue_days", 0),
            t.get("urgency", 0), t.get("train_impact", 0),
            t.get("duration_minutes", 0),
            1 if t.get("requires_isolation") else 0,
            t.get("due_date", ""),
            t.get("priority_score", 0), t.get("priority_level", ""),
            t.get("status", "pending"),
        ))
    conn.commit()


def insert_trains(conn, trains):
    """Insert a list of train-movement dicts."""
    cur = conn.cursor()
    for tr in trains:
        cur.execute("""
            INSERT INTO train_movements
            (train_id, train_type, corridor_id, date, start_time, end_time, is_confirmed)
            VALUES (?,?,?,?,?,?,?)
        """, (
            tr["train_id"], tr.get("train_type", ""),
            tr["corridor_id"], tr["date"],
            tr["start_time"], tr["end_time"],
            1 if tr.get("is_confirmed", True) else 0,
        ))
    conn.commit()


def get_all_tasks(conn):
    """Return all maintenance tasks as list of dicts."""
    rows = conn.execute("SELECT * FROM maintenance_tasks").fetchall()
    return [dict(r) for r in rows]


def get_all_trains(conn):
    """Return all train movements as list of dicts."""
    rows = conn.execute("SELECT * FROM train_movements").fetchall()
    return [dict(r) for r in rows]


def insert_default_resources(conn):
    """Create default crew resources."""
    resources = [
        ("ENG-A", "ENGINEERING", "Engineering Team A"),
        ("ENG-B", "ENGINEERING", "Engineering Team B"),
        ("SIG-A", "SIGNALLING", "Signal Team A"),
        ("SIG-B", "SIGNALLING", "Signal Team B"),
        ("TRC-A", "TRACTION", "Traction Team A"),
        ("TRC-B", "TRACTION", "Traction Team B"),
    ]
    cur = conn.cursor()
    for rid, dept, name in resources:
        cur.execute(
            "INSERT OR IGNORE INTO resources (resource_id, department, name) VALUES (?,?,?)",
            (rid, dept, name),
        )
    conn.commit()
