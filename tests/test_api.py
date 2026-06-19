import os
import json
import pytest
from fastapi.testclient import TestClient

# Set test database path before importing the app
import src.database
src.database.DB_PATH = "knowme_test.db"

from src.main import app
from src.database import init_db, get_db_connection

client = TestClient(app)

@pytest.fixture(autouse=True)
def run_around_tests():
    # Setup: Initialize test database
    if os.path.exists("knowme_test.db"):
        os.remove("knowme_test.db")
    init_db()
    
    yield
    
    # Teardown: Clean up database file
    if os.path.exists("knowme_test.db"):
        os.remove("knowme_test.db")

def test_auth_register_and_login():
    # Register
    res = client.post("/auth/register", json={"display_name": "Yves"})
    assert res.status_code == 200
    data = res.json()
    assert "user_id" in data
    assert data["display_name"] == "Yves"
    user_id = data["user_id"]
    
    # Registering same name fails
    res_dup = client.post("/auth/register", json={"display_name": "Yves"})
    assert res_dup.status_code == 400
    
    # Login
    res_login = client.post("/auth/login", json={"display_name": "Yves"})
    assert res_login.status_code == 200
    assert res_login.json()["user_id"] == user_id

def test_session_lifecycle():
    # Register user
    reg = client.post("/auth/register", json={"display_name": "Seth"})
    user_id = reg.json()["user_id"]
    
    # Start session
    res_start = client.post(f"/sessions/start?user_id={user_id}")
    assert res_start.status_code == 200
    s_data = res_start.json()
    assert "session_id" in s_data
    session_id = s_data["session_id"]
    assert len(s_data["questions"]) == 16  # Onboarding questions
    
    # Submit responses
    responses = {q["id"]: 0.8 for q in s_data["questions"]}
    res_submit = client.post(
        f"/sessions/{session_id}/responses?user_id={user_id}",
        json={"responses": responses}
    )
    assert res_submit.status_code == 200
    r_data = res_submit.json()
    assert "axis_scores" in r_data
    assert "strategic_mode" in r_data
    assert "p_local" in r_data
    
    # Close session
    res_close = client.post(
        f"/sessions/{session_id}/close?user_id={user_id}",
        json={
            "notes_created": [],
            "notes_modified": [],
            "connections_added": []
        }
    )
    assert res_close.status_code == 200
    assert res_close.json()["status"] == "closed"
    
    # Verify session count incremented
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT session_count FROM cds_profiles WHERE user_id = ?", (user_id,))
    assert cursor.fetchone()[0] == 1
    conn.close()

def test_kb_operations():
    # Register user
    reg = client.post("/auth/register", json={"display_name": "Gadyel"})
    user_id = reg.json()["user_id"]
    
    # Create note
    res_note = client.post(
        f"/kb/notes?user_id={user_id}",
        json={"name": "Newton's Second Law", "type": "PRINCIPLE", "prerequisites": ["Mass", "Force"]}
    )
    assert res_note.status_code == 200
    note_data = res_note.json()
    assert note_data["name"] == "Newton's Second Law"
    assert note_data["ghost"] is False
    note_id = note_data["note_id"]
    
    # Prerequisites "Mass" and "Force" should be created automatically as ghost notes
    res_notes = client.get(f"/kb/notes?user_id={user_id}")
    assert len(res_notes.json()) == 3  # The principal note + 2 ghosts
    
    # Find ghost notes
    ghosts = [n for n in res_notes.json() if n["ghost"]]
    assert len(ghosts) == 2
    ghost_names = {g["name"] for g in ghosts}
    assert "Mass" in ghost_names
    assert "Force" in ghost_names
    
    # Update note Layer C (User Definition)
    res_update = client.patch(
        f"/kb/notes/{note_id}?user_id={user_id}",
        json={"definition_c": "F = ma, force equals mass times acceleration", "status": 2}
    )
    assert res_update.status_code == 200
    assert res_update.json()["status"] == 2  # Unlocked status 2 since def_c exists
    
    # Attempt status 3 (fails/downgrades to 2 because we don't have 2 connections yet)
    res_update_invalid = client.patch(
        f"/kb/notes/{note_id}?user_id={user_id}",
        json={"status": 3}
    )
    assert res_update_invalid.json()["status"] == 2
    
    # Create connections to trigger status 3
    # First turn "Force" and "Mass" ghosts into real notes
    res_force = client.post(f"/kb/notes?user_id={user_id}", json={"name": "Force", "type": "CONCEPT"})
    res_mass = client.post(f"/kb/notes?user_id={user_id}", json={"name": "Mass", "type": "CONCEPT"})
    force_id = res_force.json()["note_id"]
    mass_id = res_mass.json()["note_id"]
    
    # Add definition_c to Force and Mass
    client.patch(f"/kb/notes/{force_id}?user_id={user_id}", json={"definition_c": "A push or pull"})
    client.patch(f"/kb/notes/{mass_id}?user_id={user_id}", json={"definition_c": "Resistance to acceleration"})
    
    # Connect Newton's Law to Force and Mass
    conn1 = client.post(
        f"/kb/connections?user_id={user_id}",
        json={
            "source_id": note_id,
            "target_id": force_id,
            "type": "IS-USED-IN",
            "reason": "Force is a term in Newton's equation"
        }
    )
    assert conn1.status_code == 200
    
    conn2 = client.post(
        f"/kb/connections?user_id={user_id}",
        json={
            "source_id": note_id,
            "target_id": mass_id,
            "type": "IS-USED-IN",
            "reason": "Mass is a term in Newton's equation"
        }
    )
    assert conn2.status_code == 200
    
    # Try updating Newton's Law status to 3 again
    res_update_valid = client.patch(
        f"/kb/notes/{note_id}?user_id={user_id}",
        json={"status": 3}
    )
    assert res_update_valid.json()["status"] == 3  # Success! Now we have 2 connections!
    
    # Test Graph endpoint
    res_graph = client.get(f"/kb/graph?user_id={user_id}")
    assert res_graph.status_code == 200
    g_data = res_graph.json()
    assert len(g_data["nodes"]) == 3
    # We should have 2 semantic connections + 2 prerequisite edges (since Newton lists Mass and Force as prereqs)
    # Total edges = 4
    assert len(g_data["edges"]) == 4
    
    # Test Mirror Endpoint
    res_mirror = client.post(f"/kb/notes/{note_id}/mirror?user_id={user_id}")
    assert res_mirror.status_code == 200
    m_data = res_mirror.json()
    assert "reflection" in m_data
    assert "Newton" in m_data["reflection"]
    assert "Force" in m_data["reflection"] or "force" in m_data["reflection"]
