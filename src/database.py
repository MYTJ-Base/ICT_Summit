import sqlite3
import os
import json

# Use an in-memory database during test runs if the env var is set.
_test_db = os.environ.get("KNOWME_TEST_DB")
if _test_db:
    DB_PATH = _test_db
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowme.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    
    # CDS Profiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cds_profiles (
        user_id TEXT PRIMARY KEY,
        axis_scores TEXT NOT NULL,
        p_local REAL NOT NULL,
        p_global REAL NOT NULL,
        strategic_mode TEXT NOT NULL,
        bottleneck_list TEXT NOT NULL,
        session_count INTEGER NOT NULL,
        prior_distribution TEXT NOT NULL,
        lambda_lo REAL NOT NULL,
        onboarding_complete INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)
    
    # KB Profiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS kb_profiles (
        user_id TEXT PRIMARY KEY,
        ghost_count INTEGER NOT NULL,
        total_notes INTEGER NOT NULL,
        last_modified TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)
    
    # Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        closed_at TEXT,
        strategic_mode TEXT NOT NULL,
        bottleneck_list TEXT NOT NULL,
        axis_scores_snapshot TEXT NOT NULL,
        kb_activity TEXT NOT NULL,
        p_local_delta REAL,
        p_global_delta REAL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)
    
    # Notes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        note_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        created_at TEXT NOT NULL,
        ghost INTEGER NOT NULL,
        definition_a TEXT,
        definition_b TEXT,
        definition_c TEXT,
        status INTEGER NOT NULL,
        origin TEXT,
        prerequisites TEXT, -- JSON string list of note names or IDs
        unlocks_suspected TEXT, -- JSON string list
        namespace TEXT, -- JSON string list
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    );
    """)
    
    # Connections table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS connections (
        connection_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        type TEXT NOT NULL,
        reason TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (source_id) REFERENCES notes (note_id) ON DELETE CASCADE,
        FOREIGN KEY (target_id) REFERENCES notes (note_id) ON DELETE CASCADE
    );
    """)
    
    # Namespaces table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS namespaces (
        namespace_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        parent_namespace_id TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (parent_namespace_id) REFERENCES namespaces (namespace_id) ON DELETE SET NULL
    );
    """)
    
    # Definition C History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS definition_c_history (
        history_id TEXT PRIMARY KEY,
        note_id TEXT NOT NULL,
        definition_c TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (note_id) REFERENCES notes (note_id) ON DELETE CASCADE
    );
    """)
    
    # Status History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS status_history (
        history_id TEXT PRIMARY KEY,
        note_id TEXT NOT NULL,
        status INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (note_id) REFERENCES notes (note_id) ON DELETE CASCADE
    );
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
