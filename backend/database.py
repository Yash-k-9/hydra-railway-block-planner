"""
HYDRA - SQLite Database Layer
Uses Python's built-in sqlite3. No ORM.
"""

import json
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

    CREATE TABLE IF NOT EXISTS app_state (
        key             TEXT PRIMARY KEY,
        value           TEXT                  -- JSON string
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
                   "resources", "maintenance_tasks", "app_state"]:
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


def save_state(conn, state):
    """Store the API's working state (dict of JSON-serializable values)."""
    conn.executemany(
        "INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)",
        [(key, json.dumps(value)) for key, value in state.items()],
    )
    conn.commit()


def load_state(conn):
    """Return the stored working state as a dict ({} if nothing is stored)."""
    try:
        rows = conn.execute("SELECT key, value FROM app_state").fetchall()
    except sqlite3.OperationalError:
        return {}
    return {key: json.loads(value) for key, value in rows}


def save_plan(conn, plan_type, result):
    """Replace the stored blocks of one plan ('optimized' or 'baseline') and log its stats."""
    old_ids = [r[0] for r in conn.execute(
        "SELECT block_id FROM blocks WHERE plan_type=?", (plan_type,)
    ).fetchall()]
    conn.executemany("DELETE FROM block_tasks WHERE block_id=?", [(b,) for b in old_ids])
    conn.execute("DELETE FROM blocks WHERE plan_type=?", (plan_type,))

    known_tasks = {r[0] for r in conn.execute("SELECT task_id FROM maintenance_tasks").fetchall()}
    for b in result.get("blocks", []):
        conn.execute(
            """INSERT OR REPLACE INTO blocks
               (block_id, plan_type, corridor_id, date, start_time, end_time,
                duration_minutes, departments, requires_isolation, utilization, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (b["block_id"], plan_type, b["corridor_id"], b["date"], b["start_time"],
             b["end_time"], b["duration_minutes"], ",".join(b.get("departments", [])),
             int(bool(b.get("requires_isolation"))), b.get("utilization", 0),
             b.get("status", "generated")),
        )
        conn.executemany(
            "INSERT INTO block_tasks (block_id, task_id) VALUES (?, ?)",
            [(b["block_id"], bt["task_id"]) for bt in b["tasks"] if bt["task_id"] in known_tasks],
        )

    stats = result.get("stats", {})
    conn.execute(
        """INSERT INTO optimization_results
           (plan_type, total_blocks, total_block_hours, tasks_completed,
            critical_completed, bundled_tasks, optimization_time, objective_value, created_at)
           VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
        (plan_type, stats.get("total_blocks"), stats.get("total_block_hours"),
         stats.get("tasks_completed"), stats.get("critical_completed"),
         stats.get("bundled_tasks"), result.get("optimization_time"),
         result.get("objective_value")),
    )
    conn.commit()


def set_block_status(conn, block_id, status):
    conn.execute("UPDATE blocks SET status=? WHERE block_id=?", (status, block_id))
    conn.commit()


def get_crew_counts(conn):
    """Return {department: number of crews} from the resources table."""
    rows = conn.execute(
        "SELECT department, COUNT(*) FROM resources GROUP BY department"
    ).fetchall()
    return {dept: count for dept, count in rows}


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
