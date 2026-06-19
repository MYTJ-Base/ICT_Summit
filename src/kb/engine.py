import json
import uuid
from datetime import datetime, timezone

# Knowledge Note Types
NOTE_TYPES = ["CONCEPT", "FACT", "PROCEDURE", "PRINCIPLE", "MODEL", "QUESTION", "EXPERIENCE"]

# Connection Types
CONNECTION_TYPES = [
    "IS-A-VERSION-OF",
    "IS-ANALOGOUS-TO",
    "IS-USED-IN",
    "CONTRADICTS",
    "GENERALIZES",
    "REINFORCES",
    "FUZZY"
]

def enforce_mastery_gates(definition_c, target_status, connection_count):
    """
    Enforces the mastery status gates:
    - Layer C (user's own definition) must exist before status can exceed 1.
    - At least 2 typed connections must exist before status can exceed 2.
    """
    # Force status to be an integer between 0 and 5
    status = max(0, min(5, int(target_status)))
    
    # Gate 1: Status cannot exceed 1 if Layer C doesn't exist
    if status > 1:
        if not definition_c or not definition_c.strip():
            return 1
            
    # Gate 2: Status cannot exceed 2 if connections < 2
    if status > 2:
        if connection_count < 2:
            return 2
            
    return status

def recalculate_graph_metrics(conn, user_id):
    """
    Recalculates the graph metrics for a user and updates their kb_profile.
    Metrics include:
    - total_notes
    - ghost_count
    - average_status (of non-ghost notes)
    """
    cursor = conn.cursor()
    
    # Get total notes
    cursor.execute("SELECT COUNT(*) FROM notes WHERE user_id = ?", (user_id,))
    total_notes = cursor.fetchone()[0]
    
    # Get ghost count
    cursor.execute("SELECT COUNT(*) FROM notes WHERE user_id = ? AND ghost = 1", (user_id,))
    ghost_count = cursor.fetchone()[0]
    
    # Get average status for non-ghost notes
    cursor.execute("SELECT AVG(status) FROM notes WHERE user_id = ? AND ghost = 0", (user_id,))
    avg_status = cursor.fetchone()[0]
    avg_status = round(avg_status, 2) if avg_status is not None else 0.0
    
    # Update kb_profiles table
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if profile exists
    cursor.execute("SELECT 1 FROM kb_profiles WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE kb_profiles
            SET total_notes = ?, ghost_count = ?, last_modified = ?
            WHERE user_id = ?
        """, (total_notes, ghost_count, now, user_id))
    else:
        cursor.execute("""
            INSERT INTO kb_profiles (user_id, total_notes, ghost_count, last_modified)
            VALUES (?, ?, ?, ?)
        """, (user_id, total_notes, ghost_count, now))
        
    return {
        "total_notes": total_notes,
        "ghost_count": ghost_count,
        "average_status": avg_status
    }

def get_or_create_ghost_note(conn, user_id, note_name):
    """
    Gets a note by name, or creates it as a ghost note if it doesn't exist.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT note_id, ghost FROM notes WHERE user_id = ? AND name = ?", (user_id, note_name))
    row = cursor.fetchone()
    
    if row:
        return row["note_id"], bool(row["ghost"])
        
    # Create ghost note
    note_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO notes (note_id, user_id, name, type, created_at, ghost, status, prerequisites, unlocks_suspected, namespace)
        VALUES (?, ?, ?, ?, ?, 1, 0, '[]', '[]', '[]')
    """, (note_id, user_id, note_name, "CONCEPT", now))
    
    # Insert history
    cursor.execute("""
        INSERT INTO status_history (history_id, note_id, status, created_at)
        VALUES (?, ?, 0, ?)
    """, (str(uuid.uuid4()), note_id, now))
    
    return note_id, True

def compute_unlocks_known(conn, user_id):
    """
    Helper function to calculate unlocks_known for all notes of a user.
    If A lists B as a prerequisite, then B has A in its unlocks_known.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT note_id, name, prerequisites FROM notes WHERE user_id = ?", (user_id,))
    notes = cursor.fetchall()
    
    # Create a mapping of note_name to note_id for fast lookup
    name_to_id = {n["name"]: n["note_id"] for n in notes}
    id_to_name = {n["note_id"]: n["name"] for n in notes}
    
    # Build prerequisites adj list
    prereqs = {}
    for n in notes:
        try:
            p_list = json.loads(n["prerequisites"])
        except Exception:
            p_list = []
        prereqs[n["note_id"]] = p_list
        
    # Compute unlocks
    unlocks = {n["note_id"]: [] for n in notes}
    for note_id, p_list in prereqs.items():
        for p in p_list:
            # p could be a name or ID
            target_id = None
            if p in name_to_id:
                target_id = name_to_id[p]
            elif p in id_to_name:
                target_id = p
                
            if target_id and target_id in unlocks:
                source_name = id_to_name[note_id]
                unlocks[target_id].append(source_name)
                
    return unlocks

def merge_notes(conn, user_id, source_id, target_id, reason="Merged duplicates"):
    """
    Fuses source_id note into target_id note.
    All connections, prerequisites, and histories are updated.
    """
    cursor = conn.cursor()
    
    # Verify both exist
    cursor.execute("SELECT name, ghost FROM notes WHERE user_id = ? AND note_id = ?", (user_id, source_id))
    source_row = cursor.fetchone()
    cursor.execute("SELECT name, ghost FROM notes WHERE user_id = ? AND note_id = ?", (user_id, target_id))
    target_row = cursor.fetchone()
    
    if not source_row or not target_row:
        raise ValueError("Source or Target note not found.")
        
    source_name = source_row["name"]
    target_name = target_row["name"]
    
    # Redirect connections where source_id was source or target
    cursor.execute("""
        UPDATE connections 
        SET source_id = ? 
        WHERE user_id = ? AND source_id = ?
    """, (target_id, user_id, source_id))
    
    cursor.execute("""
        UPDATE connections 
        SET target_id = ? 
        WHERE user_id = ? AND target_id = ?
    """, (target_id, user_id, source_id))
    
    # Merge prerequisites lists in the DB
    # We will need to load, edit, and save them.
    # But a simpler way: just delete the source note after redirects,
    # and update references in prerequisites json fields of other notes.
    cursor.execute("SELECT note_id, prerequisites, unlocks_suspected FROM notes WHERE user_id = ?", (user_id,))
    all_notes = cursor.fetchall()
    
    for note in all_notes:
        nid = note["note_id"]
        try:
            prereqs = json.loads(note["prerequisites"])
        except Exception:
            prereqs = []
            
        # Replace source_name with target_name in prerequisites
        updated_prereqs = []
        changed = False
        for p in prereqs:
            if p == source_name or p == source_id:
                updated_prereqs.append(target_name)
                changed = True
            else:
                updated_prereqs.append(p)
                
        if changed:
            cursor.execute("UPDATE notes SET prerequisites = ? WHERE note_id = ?", (json.dumps(list(set(updated_prereqs))), nid))
            
    # Delete the source note
    cursor.execute("DELETE FROM notes WHERE note_id = ?", (source_id,))
    
    # Commit changes
    conn.commit()
    
    return target_id
