import subprocess
import time
import sys
import os

def run_validation():
    print("====================================================")
    print("      KNOWME SYSTEM DEMO FLOW VALIDATOR             ")
    print("====================================================")
    
    # 1. Start FastAPI server using uvicorn in background
    print("\n[Step 1] Booting up FastAPI/Uvicorn server...")
    server_process = subprocess.Popen(
        ["uv", "run", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8085"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=os.environ
    )
    
    # Wait for server to boot
    time.sleep(3)
    
    # Check if server is running
    if server_process.poll() is not None:
        print("❌ Error: Server failed to start. Logs:")
        stdout, stderr = server_process.communicate()
        print(stderr.decode())
        sys.exit(1)
    else:
        print("✅ Server booted successfully on http://127.0.0.1:8085")
        
    try:
        import httpx
    except ImportError:
        print("Installing httpx for validation script...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
        import httpx
        
    client = httpx.Client(base_url="http://127.0.0.1:8085")
    
    try:
        # 2. Register user
        print("\n[Step 2] Registering user 'Songue'...")
        res = client.post("/auth/register", json={"display_name": "Songue"})
        res.raise_for_status()
        user = res.json()
        user_id = user["user_id"]
        print(f"✅ Registered! User ID: {user_id}")
        
        headers = {"X-User-ID": user_id}
        
        # 3. Start diagnostic session
        print("\n[Step 3] Starting CDS session...")
        res = client.post("/sessions/start", headers=headers)
        res.raise_for_status()
        session = res.json()
        session_id = session["session_id"]
        questions = session["questions"]
        print(f"✅ Session started! Session ID: {session_id}")
        print(f"   Received {len(questions)} onboarding calibration questions.")
        
        # 4. Submit responses (simulating positive values for rest, tired for fatigue)
        print("\n[Step 4] Submitting responses to anchor questions...")
        # Let's say sleep is average (0.4), fatigue is low (1.0 - fresh), hydration is full (1.0), etc.
        responses = {q["id"]: 0.8 for q in questions}
        # Simulate slight fatigue N2 = 0.4
        for q in questions:
            if q["sub_pillar"] == "N2":
                responses[q["id"]] = 0.4
                
        res = client.post(f"/sessions/{session_id}/responses", headers=headers, json={"responses": responses})
        res.raise_for_status()
        cds_result = res.json()
        print(f"✅ CDS Calibration Successful!")
        print(f"   Recommended Strategic Mode: {cds_result['strategic_mode']}")
        print(f"   Current Bottlenecks detected: {cds_result['bottleneck_list']}")
        print(f"   P_local (Proximity to best): {cds_result['p_local']}")
        print(f"   P_global (Proximity to ideal): {cds_result['p_global']}")
        print(f"   Diagnostic feedback title: '{cds_result['feedback']['title']}'")
        print(f"   Diagnostic Narrative: \"{cds_result['feedback']['diagnostic_narrative']}\"")
        
        # 5. Create note
        print("\n[Step 5] Creating Knowledge Note: 'Newtonian Physics [Physics]'...")
        res = client.post(
            "/kb/notes", 
            headers=headers, 
            json={
                "name": "Newtonian Physics", 
                "type": "PRINCIPLE",
                "prerequisites": ["Mass", "Acceleration"],
                "namespace": ["Physics", "Mechanics"]
            }
        )
        res.raise_for_status()
        note = res.json()
        note_id = note["note_id"]
        print(f"✅ Note created! ID: {note_id}")
        print(f"   Note Status: {note['status']} (Default Level 0)")
        
        # Verify ghost notes were created automatically for Mass and Acceleration
        print("   Checking automatically created ghost note placeholders...")
        res = client.get("/kb/notes", headers=headers)
        all_notes = res.json()
        ghosts = [n for n in all_notes if n["ghost"]]
        print(f"✅ Found {len(ghosts)} ghost note placeholders: {', '.join([g['name'] for g in ghosts])}")
        
        # 6. Update user definition (Layer C) to unlock status 2
        print("\n[Step 6] Adding User definition (Layer C) to Newton Note...")
        res = client.patch(
            f"/kb/notes/{note_id}", 
            headers=headers, 
            json={
                "definition_c": "Newtonian physics describes the motion of macro objects based on force, mass, and acceleration.",
                "status": 2
            }
        )
        res.raise_for_status()
        note_updated = res.json()
        print(f"✅ Note updated! New Status: {note_updated['status']} (Unlocked Defined Status)")
        
        # 7. Update Mass and Force to satisfy connection gates
        print("   Updating prerequisites 'Mass' and 'Acceleration' to satisfy status gates...")
        mass_note = next(n for n in all_notes if n["name"] == "Mass")
        acc_note = next(n for n in all_notes if n["name"] == "Acceleration")
        
        # Define Mass
        client.patch(f"/kb/notes/{mass_note['note_id']}", headers=headers, json={"definition_c": "Measurement of resistance to acceleration."})
        # Define Acceleration
        client.patch(f"/kb/notes/{acc_note['note_id']}", headers=headers, json={"definition_c": "Rate of change of velocity."})
        
        # 8. Create connections to unlock status 3 (requires 2 connections)
        print("\n[Step 8] Connecting Newtonian Physics to Mass and Acceleration...")
        
        # Connect Newton -> Mass
        res = client.post(
            "/kb/connections",
            headers=headers,
            json={
                "source_id": note_id,
                "target_id": mass_note["note_id"],
                "type": "IS-USED-IN",
                "reason": "Mass is the primary parameter in Newton's second law."
            }
        )
        res.raise_for_status()
        
        # Connect Newton -> Acceleration
        res = client.post(
            "/kb/connections",
            headers=headers,
            json={
                "source_id": note_id,
                "target_id": acc_note["note_id"],
                "type": "IS-USED-IN",
                "reason": "Acceleration represents the rate of change parameter in Newtonian mechanics."
            }
        )
        res.raise_for_status()
        print("✅ Connections created successfully!")
        
        # Trigger note status upgrade to Level 3 (Connected)
        res = client.patch(f"/kb/notes/{note_id}", headers=headers, json={"status": 3})
        res.raise_for_status()
        print(f"✅ Newtonian Physics status updated to: {res.json()['status']} (Unlocked Connected Status)")
        
        # 9. Trigger AI mirror reflection
        print("\n[Step 9] Triggering AI Mirror reflection for Newtonian Physics...")
        res = client.post(f"/kb/notes/{note_id}/mirror", headers=headers)
        res.raise_for_status()
        mirror = res.json()
        print("----------------------------------------------------")
        print(mirror["reflection"])
        print("----------------------------------------------------")
        
        # 10. Query graph
        print("\n[Step 10] Retrieving full knowledge graph...")
        res = client.get("/kb/graph", headers=headers)
        res.raise_for_status()
        graph = res.json()
        print(f"✅ Graph retrieved! Nodes: {len(graph['nodes'])}, Edges: {len(graph['edges'])}")
        
        # 11. Close session
        print("\n[Step 11] Closing session...")
        res = client.post(
            f"/sessions/{session_id}/close", 
            headers=headers,
            json={
                "notes_created": [note_id],
                "notes_modified": [note_id],
                "connections_added": []
            }
        )
        res.raise_for_status()
        print("✅ Session closed successfully!")
        print(f"   Deltas calculated - p_local_delta: {res.json()['p_local_delta']}, p_global_delta: {res.json()['p_global_delta']}")
        
    except Exception as e:
        print(f"❌ Error during validation: {str(e)}")
        raise e
    finally:
        # Stop background uvicorn server
        print("\nStopping uvicorn server process...")
        server_process.terminate()
        server_process.wait()
        print("👋 Validation process finished.")

if __name__ == "__main__":
    run_validation()
