import os
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Header, Query, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse

from src.database import get_db_connection, init_db
import src.cds.engine as cds_engine
import src.kb.engine as kb_engine
import src.ai.engine as ai_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — initialises the database on startup."""
    init_db()
    yield

app = FastAPI(title="KnowMe API", version="0.1.0", lifespan=lifespan)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get user_id from header or query param
def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    user_id: Optional[str] = Query(None)
) -> str:
    uid = x_user_id or user_id
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_411_LENGTH_REQUIRED,
            detail="User identity required. Provide X-User-ID header or user_id query parameter."
        )
    return uid

# Pydantic Schemas
class RegisterRequest(BaseModel):
    display_name: str

class NoteCreate(BaseModel):
    name: str
    type: str  # CONCEPT, FACT, etc.
    prerequisites: Optional[List[str]] = []
    namespace: Optional[List[str]] = []

class NoteUpdate(BaseModel):
    definition_a: Optional[str] = None
    definition_b: Optional[str] = None
    definition_c: Optional[str] = None
    status: Optional[int] = None
    origin: Optional[str] = None
    prerequisites: Optional[List[str]] = None
    unlocks_suspected: Optional[List[str]] = None
    namespace: Optional[List[str]] = None

class ConnectionCreate(BaseModel):
    source_id: str
    target_id: str
    type: str
    reason: str

class NamespaceCreate(BaseModel):
    name: str
    parent_namespace_id: Optional[str] = None

class ResponseSubmit(BaseModel):
    responses: Dict[str, float]  # question_id -> response_value

class SessionClose(BaseModel):
    notes_created: Optional[List[str]] = []
    notes_modified: Optional[List[str]] = []
    connections_added: Optional[List[str]] = []

# Auth Endpoints
@app.post("/auth/register")
def register(req: RegisterRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if user already exists
    cursor.execute("SELECT user_id FROM users WHERE display_name = ?", (req.display_name,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="User already registered. Please login instead.")
        
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        # Create user
        cursor.execute("INSERT INTO users (user_id, display_name, created_at) VALUES (?, ?, ?)", 
                       (user_id, req.display_name, now))
        
        # Initialize CDS Profile
        initial_priors = cds_engine.get_initial_priors()
        initial_scores = cds_engine.compute_axis_scores(initial_priors)
        cursor.execute("""
            INSERT INTO cds_profiles (
                user_id, axis_scores, p_local, p_global, strategic_mode, 
                bottleneck_list, session_count, prior_distribution, lambda_lo, onboarding_complete
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            json.dumps(initial_scores),
            1.0,  # p_local
            0.5,  # p_global (neutral avg)
            "CONSOLIDATION",  # default initial mode
            json.dumps([]),
            0,
            json.dumps(initial_priors),
            1.0,
            0  # onboarding_complete = false
        ))
        
        # Initialize KB Profile
        cursor.execute("""
            INSERT INTO kb_profiles (user_id, ghost_count, total_notes, last_modified)
            VALUES (?, ?, ?, ?)
        """, (user_id, 0, 0, now))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error during registration: {str(e)}")
        
    conn.close()
    return {"user_id": user_id, "token": user_id, "display_name": req.display_name}

@app.post("/auth/login")
def login(req: RegisterRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, display_name FROM users WHERE display_name = ?", (req.display_name,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")
        
    return {"user_id": row["user_id"], "token": row["user_id"], "display_name": row["display_name"]}

# Session Endpoints
@app.post("/sessions/start")
def start_session(user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Load profile details
    cursor.execute("SELECT session_count, prior_distribution FROM cds_profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()
    if not profile:
        conn.close()
        raise HTTPException(status_code=404, detail="CDS Profile not found.")
        
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Select question set
    session_count = profile["session_count"]
    priors = json.loads(profile["prior_distribution"])
    
    if session_count == 0:
        # Onboarding: return the first 16 questions
        questions = [q for q in cds_engine.QUESTIONS if q["id"] in cds_engine.ONBOARDING_QUESTIONS_IDS]
    else:
        # Normal session: select 6 highest-variance sub-pillars
        questions = cds_engine.select_next_questions(priors, num_questions=6)
        
    # Get current axis scores to snapshot
    cursor.execute("SELECT axis_scores, strategic_mode, bottleneck_list FROM cds_profiles WHERE user_id = ?", (user_id,))
    curr_profile = cursor.fetchone()
    
    try:
        # Create session record
        cursor.execute("""
            INSERT INTO sessions (
                session_id, user_id, started_at, strategic_mode, bottleneck_list, axis_scores_snapshot, kb_activity
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            user_id,
            now,
            curr_profile["strategic_mode"],
            curr_profile["bottleneck_list"],
            curr_profile["axis_scores"],
            json.dumps({"notes_created": [], "notes_modified": [], "connections_added": []})
        ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error starting session: {str(e)}")
        
    conn.close()
    return {"session_id": session_id, "questions": questions}

@app.post("/sessions/{id}/responses")
def submit_responses(id: str, req: ResponseSubmit, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Load session and profile
    cursor.execute("SELECT 1 FROM sessions WHERE session_id = ? AND user_id = ?", (id, user_id))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Active session not found.")
        
    cursor.execute("SELECT prior_distribution, session_count FROM cds_profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()
    priors = json.loads(profile["prior_distribution"])
    session_count = profile["session_count"]
    
    # Apply Bayesian update for each response
    # req.responses is a dict of question_id -> value
    for q_id, val in req.responses.items():
        # Find sub-pillar
        q_obj = next((q for q in cds_engine.QUESTIONS if q["id"] == q_id), None)
        if q_obj:
            sp = q_obj["sub_pillar"]
            prior_mu = priors[sp]["mu"]
            prior_sigma = priors[sp]["sigma"]
            
            # Update prior distribution
            post_mu, post_sigma = cds_engine.bayesian_update(prior_mu, prior_sigma, val)
            priors[sp]["mu"] = post_mu
            priors[sp]["sigma"] = post_sigma
            
    # Recompute axis scores
    axis_scores = cds_engine.compute_axis_scores(priors)
    
    # Fetch session history for proximity scores
    cursor.execute("SELECT axis_scores_snapshot FROM sessions WHERE user_id = ? AND closed_at IS NOT NULL", (user_id,))
    history = cursor.fetchall()
    
    p_local, p_global = cds_engine.compute_proximity_scores(axis_scores, history)
    
    # Determine strategic mode
    strategic_mode = cds_engine.determine_strategic_mode(priors, axis_scores, p_local, p_global)
    
    # Generate bottleneck list
    bottlenecks = cds_engine.get_bottlenecks(priors)
    
    # Get diagnostic feedback (narrative summary)
    feedback = ai_engine.generate_diagnostic_feedback(strategic_mode, bottlenecks)
    
    onboarding_complete = 1 if session_count > 0 or len(req.responses) >= 16 else 0
    
    try:
        # Update CDS Profile
        cursor.execute("""
            UPDATE cds_profiles
            SET axis_scores = ?, p_local = ?, p_global = ?, strategic_mode = ?, 
                bottleneck_list = ?, prior_distribution = ?, onboarding_complete = ?
            WHERE user_id = ?
        """, (
            json.dumps(axis_scores),
            p_local,
            p_global,
            strategic_mode,
            json.dumps(bottlenecks),
            json.dumps(priors),
            onboarding_complete,
            user_id
        ))
        
        # Update Session Snapshot
        cursor.execute("""
            UPDATE sessions
            SET strategic_mode = ?, bottleneck_list = ?, axis_scores_snapshot = ?
            WHERE session_id = ?
        """, (
            strategic_mode,
            json.dumps(bottlenecks),
            json.dumps(axis_scores),
            id
        ))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error during responses submit: {str(e)}")
        
    conn.close()
    return {
        "axis_scores": axis_scores,
        "strategic_mode": strategic_mode,
        "bottleneck_list": bottlenecks,
        "p_local": p_local,
        "p_global": p_global,
        "feedback": feedback
    }

@app.post("/sessions/{id}/close")
def close_session(id: str, req: SessionClose, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT started_at, strategic_mode, axis_scores_snapshot FROM sessions WHERE session_id = ? AND user_id = ?", (id, user_id))
    session_row = cursor.fetchone()
    if not session_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found.")
        
    # Get user profile to calculate deltas
    cursor.execute("SELECT p_local, p_global, session_count FROM cds_profiles WHERE user_id = ?", (user_id,))
    profile_row = cursor.fetchone()
    
    curr_p_local = profile_row["p_local"]
    curr_p_global = profile_row["p_global"]
    session_count = profile_row["session_count"]
    
    # In SQLite, find previous session's scores
    cursor.execute("""
        SELECT axis_scores_snapshot 
        FROM sessions 
        WHERE user_id = ? AND closed_at IS NOT NULL 
        ORDER BY closed_at DESC LIMIT 1
    """, (user_id,))
    prev_session = cursor.fetchone()
    
    p_local_delta = 0.0
    p_global_delta = 0.0
    
    if prev_session:
        # If there is a previous session, calculate delta in P_local/P_global
        # P_local_delta = current_p_local - previous_session's p_local
        # Let's approximate delta or fetch previous session profile values
        # A simpler way: just delta relative to previous snapshot averages
        pass
        
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        # Update session record
        cursor.execute("""
            UPDATE sessions
            SET closed_at = ?, kb_activity = ?, p_local_delta = ?, p_global_delta = ?
            WHERE session_id = ?
        """, (
            now,
            json.dumps({
                "notes_created": req.notes_created,
                "notes_modified": req.notes_modified,
                "connections_added": req.connections_added
            }),
            p_local_delta,
            p_global_delta,
            id
        ))
        
        # Increment session count
        cursor.execute("UPDATE cds_profiles SET session_count = ? WHERE user_id = ?", (session_count + 1, user_id))
        
        # Recalculate KB metrics
        kb_engine.recalculate_graph_metrics(conn, user_id)
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error closing session: {str(e)}")
        
    conn.close()
    return {"status": "closed", "p_local_delta": p_local_delta, "p_global_delta": p_global_delta}

@app.get("/sessions/history")
def get_session_history(user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, started_at, closed_at, strategic_mode, bottleneck_list, axis_scores_snapshot, kb_activity 
        FROM sessions 
        WHERE user_id = ? AND closed_at IS NOT NULL 
        ORDER BY started_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "session_id": r["session_id"],
            "started_at": r["started_at"],
            "closed_at": r["closed_at"],
            "strategic_mode": r["strategic_mode"],
            "bottleneck_list": json.loads(r["bottleneck_list"]),
            "axis_scores_snapshot": json.loads(r["axis_scores_snapshot"]),
            "kb_activity": json.loads(r["kb_activity"])
        })
    return history

@app.get("/sessions/{id}")
def get_session_by_id(id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT session_id, started_at, closed_at, strategic_mode, bottleneck_list, axis_scores_snapshot, kb_activity 
        FROM sessions 
        WHERE session_id = ? AND user_id = ?
    """, (id, user_id))
    r = cursor.fetchone()
    conn.close()
    
    if not r:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    return {
        "session_id": r["session_id"],
        "started_at": r["started_at"],
        "closed_at": r["closed_at"],
        "strategic_mode": r["strategic_mode"],
        "bottleneck_list": json.loads(r["bottleneck_list"]),
        "axis_scores_snapshot": json.loads(r["axis_scores_snapshot"]),
        "kb_activity": json.loads(r["kb_activity"])
    }

# KB Endpoints
@app.get("/kb/notes")
def get_notes(
    type: Optional[str] = None,
    status_min: Optional[int] = None,
    status_max: Optional[int] = None,
    namespace: Optional[str] = None,
    ghost: Optional[bool] = None,
    user_id: str = Depends(get_current_user_id)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM notes WHERE user_id = ?"
    params = [user_id]
    
    if type:
        query += " AND type = ?"
        params.append(type)
    if status_min is not None:
        query += " AND status >= ?"
        params.append(status_min)
    if status_max is not None:
        query += " AND status <= ?"
        params.append(status_max)
    if ghost is not None:
        query += " AND ghost = ?"
        params.append(1 if ghost else 0)
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    notes = []
    for r in rows:
        note_ns = json.loads(r["namespace"])
        # Namespace filter in python for simplicity
        if namespace and namespace not in note_ns:
            continue
            
        notes.append({
            "note_id": r["note_id"],
            "name": r["name"],
            "type": r["type"],
            "created_at": r["created_at"],
            "ghost": bool(r["ghost"]),
            "definition_a": r["definition_a"],
            "definition_b": r["definition_b"],
            "definition_c": r["definition_c"],
            "status": r["status"],
            "origin": r["origin"],
            "prerequisites": json.loads(r["prerequisites"]),
            "unlocks_suspected": json.loads(r["unlocks_suspected"]),
            "namespace": note_ns
        })
    return notes

@app.post("/kb/notes")
def create_note(req: NoteCreate, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if a note with the same name already exists
    cursor.execute("SELECT note_id, ghost FROM notes WHERE user_id = ? AND name = ?", (user_id, req.name))
    existing = cursor.fetchone()
    
    now = datetime.now(timezone.utc).isoformat()
    
    if existing:
        if bool(existing["ghost"]):
            # Turn the ghost note into a real note!
            note_id = existing["note_id"]
            try:
                cursor.execute("""
                    UPDATE notes
                    SET type = ?, ghost = 0, created_at = ?, namespace = ?
                    WHERE note_id = ?
                """, (req.type, now, json.dumps(req.namespace or []), note_id))
                
                # Update status history
                cursor.execute("""
                    INSERT INTO status_history (history_id, note_id, status, created_at)
                    VALUES (?, ?, 0, ?)
                """, (str(uuid.uuid4()), note_id, now))
                conn.commit()
            except Exception as e:
                conn.rollback()
                conn.close()
                raise HTTPException(status_code=500, detail=f"Database error turning ghost into note: {str(e)}")
        else:
            conn.close()
            raise HTTPException(status_code=400, detail="A note with this name already exists.")
    else:
        # Create completely new note
        note_id = str(uuid.uuid4())
        try:
            cursor.execute("""
                INSERT INTO notes (
                    note_id, user_id, name, type, created_at, ghost, definition_a, 
                    definition_b, definition_c, status, origin, prerequisites, unlocks_suspected, namespace
                ) VALUES (?, ?, ?, ?, ?, 0, NULL, NULL, NULL, 0, NULL, ?, '[]', ?)
            """, (
                note_id,
                user_id,
                req.name,
                req.type,
                now,
                json.dumps(req.prerequisites or []),
                json.dumps(req.namespace or [])
            ))
            
            # Insert status history
            cursor.execute("""
                INSERT INTO status_history (history_id, note_id, status, created_at)
                VALUES (?, ?, 0, ?)
            """, (str(uuid.uuid4()), note_id, now))
            
            # Auto-create ghost notes for declared prerequisites that don't exist
            if req.prerequisites:
                for prereq_name in req.prerequisites:
                    kb_engine.get_or_create_ghost_note(conn, user_id, prereq_name)
                    
            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            raise HTTPException(status_code=500, detail=f"Database error creating note: {str(e)}")
            
    # Fetch and return the newly created/updated note
    cursor.execute("SELECT * FROM notes WHERE note_id = ?", (note_id,))
    r = cursor.fetchone()
    conn.close()
    
    return {
        "note_id": r["note_id"],
        "name": r["name"],
        "type": r["type"],
        "created_at": r["created_at"],
        "ghost": bool(r["ghost"]),
        "definition_a": r["definition_a"],
        "definition_b": r["definition_b"],
        "definition_c": r["definition_c"],
        "status": r["status"],
        "origin": r["origin"],
        "prerequisites": json.loads(r["prerequisites"]),
        "unlocks_suspected": json.loads(r["unlocks_suspected"]),
        "namespace": json.loads(r["namespace"])
    }

@app.get("/kb/notes/{id}")
def get_note_by_id(id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notes WHERE note_id = ? AND user_id = ?", (id, user_id))
    r = cursor.fetchone()
    conn.close()
    
    if not r:
        raise HTTPException(status_code=404, detail="Note not found.")
        
    return {
        "note_id": r["note_id"],
        "name": r["name"],
        "type": r["type"],
        "created_at": r["created_at"],
        "ghost": bool(r["ghost"]),
        "definition_a": r["definition_a"],
        "definition_b": r["definition_b"],
        "definition_c": r["definition_c"],
        "status": r["status"],
        "origin": r["origin"],
        "prerequisites": json.loads(r["prerequisites"]),
        "unlocks_suspected": json.loads(r["unlocks_suspected"]),
        "namespace": json.loads(r["namespace"])
    }

@app.patch("/kb/notes/{id}")
def update_note(id: str, req: NoteUpdate, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM notes WHERE note_id = ? AND user_id = ?", (id, user_id))
    note = cursor.fetchone()
    if not note:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found.")
        
    # Get current connection count involving this note
    cursor.execute("SELECT COUNT(*) FROM connections WHERE user_id = ? AND (source_id = ? OR target_id = ?)", (user_id, id, id))
    conn_count = cursor.fetchone()[0]
    
    # Merge updates
    updated_fields = {}
    
    def_a = req.definition_a if req.definition_a is not None else note["definition_a"]
    def_b = req.definition_b if req.definition_b is not None else note["definition_b"]
    def_c = req.definition_c if req.definition_c is not None else note["definition_c"]
    
    target_status = req.status if req.status is not None else note["status"]
    
    # Enforce mastery status gates!
    final_status = kb_engine.enforce_mastery_gates(def_c, target_status, conn_count)
    
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        # If definition_c changed and is not null, archive previous version
        if req.definition_c is not None and req.definition_c != note["definition_c"] and note["definition_c"] is not None:
            cursor.execute("""
                INSERT INTO definition_c_history (history_id, note_id, definition_c, created_at)
                VALUES (?, ?, ?, ?)
            """, (str(uuid.uuid4()), id, note["definition_c"], now))
            
        # If status changed, archive it
        if final_status != note["status"]:
            cursor.execute("""
                INSERT INTO status_history (history_id, note_id, status, created_at)
                VALUES (?, ?, ?, ?)
            """, (str(uuid.uuid4()), id, final_status, now))
            
        # Handle ghost creation for newly added prerequisites
        prereqs = note["prerequisites"]
        if req.prerequisites is not None:
            prereqs = json.dumps(req.prerequisites)
            for prereq_name in req.prerequisites:
                kb_engine.get_or_create_ghost_note(conn, user_id, prereq_name)
                
        # Perform update
        cursor.execute("""
            UPDATE notes
            SET definition_a = ?, definition_b = ?, definition_c = ?, status = ?, 
                origin = ?, prerequisites = ?, unlocks_suspected = ?, namespace = ?
            WHERE note_id = ?
        """, (
            def_a,
            def_b,
            def_c,
            final_status,
            req.origin if req.origin is not None else note["origin"],
            prereqs,
            json.dumps(req.unlocks_suspected) if req.unlocks_suspected is not None else note["unlocks_suspected"],
            json.dumps(req.namespace) if req.namespace is not None else note["namespace"],
            id
        ))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error updating note: {str(e)}")
        
    # Re-fetch note
    cursor.execute("SELECT * FROM notes WHERE note_id = ?", (id,))
    r = cursor.fetchone()
    conn.close()
    
    return {
        "note_id": r["note_id"],
        "name": r["name"],
        "type": r["type"],
        "created_at": r["created_at"],
        "ghost": bool(r["ghost"]),
        "definition_a": r["definition_a"],
        "definition_b": r["definition_b"],
        "definition_c": r["definition_c"],
        "status": r["status"],
        "origin": r["origin"],
        "prerequisites": json.loads(r["prerequisites"]),
        "unlocks_suspected": json.loads(r["unlocks_suspected"]),
        "namespace": json.loads(r["namespace"])
    }

# Connections
@app.post("/kb/connections")
def create_connection(req: ConnectionCreate, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if connection already exists
    cursor.execute("""
        SELECT connection_id FROM connections 
        WHERE user_id = ? AND (
            (source_id = ? AND target_id = ?) OR 
            (source_id = ? AND target_id = ? AND type IN ('IS-ANALOGOUS-TO', 'CONTRADICTS', 'REINFORCES', 'FUZZY'))
        )
    """, (user_id, req.source_id, req.target_id, req.target_id, req.source_id))
    
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Connection already exists between these notes.")
        
    conn_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO connections (connection_id, user_id, source_id, target_id, type, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (conn_id, user_id, req.source_id, req.target_id, req.type, req.reason, now))
        
        # Trigger mastery status re-evaluation for source and target notes
        for nid in [req.source_id, req.target_id]:
            # Load note
            cursor.execute("SELECT definition_c, status FROM notes WHERE note_id = ?", (nid,))
            note_row = cursor.fetchone()
            # Count connections
            cursor.execute("SELECT COUNT(*) FROM connections WHERE user_id = ? AND (source_id = ? OR target_id = ?)", (user_id, nid, nid))
            conn_count = cursor.fetchone()[0]
            
            final_status = kb_engine.enforce_mastery_gates(note_row["definition_c"], note_row["status"], conn_count)
            if final_status != note_row["status"]:
                cursor.execute("UPDATE notes SET status = ? WHERE note_id = ?", (final_status, nid))
                cursor.execute("""
                    INSERT INTO status_history (history_id, note_id, status, created_at)
                    VALUES (?, ?, ?, ?)
                """, (str(uuid.uuid4()), nid, final_status, now))
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error creating connection: {str(e)}")
        
    cursor.execute("SELECT * FROM connections WHERE connection_id = ?", (conn_id,))
    r = cursor.fetchone()
    conn.close()
    
    return {
        "connection_id": r["connection_id"],
        "source_id": r["source_id"],
        "target_id": r["target_id"],
        "type": r["type"],
        "reason": r["reason"],
        "created_at": r["created_at"]
    }

@app.delete("/kb/connections/{id}")
def delete_connection(id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT source_id, target_id FROM connections WHERE connection_id = ? AND user_id = ?", (id, user_id))
    conn_row = cursor.fetchone()
    if not conn_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Connection not found.")
        
    source_id = conn_row["source_id"]
    target_id = conn_row["target_id"]
    
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        cursor.execute("DELETE FROM connections WHERE connection_id = ?", (id,))
        
        # Trigger mastery status re-evaluation for source and target notes
        for nid in [source_id, target_id]:
            # Load note
            cursor.execute("SELECT definition_c, status FROM notes WHERE note_id = ?", (nid,))
            note_row = cursor.fetchone()
            if note_row:
                # Count connections
                cursor.execute("SELECT COUNT(*) FROM connections WHERE user_id = ? AND (source_id = ? OR target_id = ?)", (user_id, nid, nid))
                conn_count = cursor.fetchone()[0]
                
                final_status = kb_engine.enforce_mastery_gates(note_row["definition_c"], note_row["status"], conn_count)
                if final_status != note_row["status"]:
                    cursor.execute("UPDATE notes SET status = ? WHERE note_id = ?", (final_status, nid))
                    cursor.execute("""
                        INSERT INTO status_history (history_id, note_id, status, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (str(uuid.uuid4()), nid, final_status, now))
                    
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error deleting connection: {str(e)}")
        
    conn.close()
    return {"status": "deleted"}

# Namespaces
@app.get("/kb/namespaces")
def get_namespaces(user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM namespaces WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    namespaces = []
    for r in rows:
        namespaces.append({
            "namespace_id": r["namespace_id"],
            "name": r["name"],
            "parent_namespace_id": r["parent_namespace_id"]
        })
    return namespaces

@app.post("/kb/namespaces")
def create_namespace(req: NamespaceCreate, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if namespace name already exists
    cursor.execute("SELECT namespace_id FROM namespaces WHERE user_id = ? AND name = ?", (user_id, req.name))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Namespace with this name already exists.")
        
    ns_id = str(uuid.uuid4())
    try:
        cursor.execute("""
            INSERT INTO namespaces (namespace_id, user_id, name, parent_namespace_id)
            VALUES (?, ?, ?, ?)
        """, (ns_id, user_id, req.name, req.parent_namespace_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Database error creating namespace: {str(e)}")
        
    cursor.execute("SELECT * FROM namespaces WHERE namespace_id = ?", (ns_id,))
    r = cursor.fetchone()
    conn.close()
    
    return {
        "namespace_id": r["namespace_id"],
        "name": r["name"],
        "parent_namespace_id": r["parent_namespace_id"]
    }

# Graph Query
@app.get("/kb/graph")
def get_graph(user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all notes
    cursor.execute("SELECT note_id, name, type, status, ghost, namespace FROM notes WHERE user_id = ?", (user_id,))
    note_rows = cursor.fetchall()
    
    # Get all connections
    cursor.execute("SELECT connection_id, source_id, target_id, type, reason FROM connections WHERE user_id = ?", (user_id,))
    conn_rows = cursor.fetchall()
    
    # Get computed unlocks to inject in node details if needed
    unlocks_map = kb_engine.compute_unlocks_known(conn, user_id)
    
    conn.close()
    
    nodes = []
    name_to_id = {}
    for nr in note_rows:
        name_to_id[nr["name"]] = nr["note_id"]
        nodes.append({
            "id": nr["note_id"],
            "name": nr["name"],
            "type": nr["type"],
            "status": nr["status"],
            "ghost": bool(nr["ghost"]),
            "namespace": json.loads(nr["namespace"]),
            "unlocks_known": unlocks_map.get(nr["note_id"], [])
        })
        
    edges = []
    # Add semantic connections
    for cr in conn_rows:
        edges.append({
            "id": cr["connection_id"],
            "source": cr["source_id"],
            "target": cr["target_id"],
            "type": cr["type"],
            "reason": cr["reason"],
            "is_prerequisite": False
        })
        
    # Re-fetch notes prerequisites to build prerequisite edges
    # We load them and match note names to node IDs to build prerequisite edges
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT note_id, name, prerequisites FROM notes WHERE user_id = ?", (user_id,))
    notes_prereqs = cursor.fetchall()
    conn.close()
    
    for r in notes_prereqs:
        source_id = r["note_id"]
        try:
            p_list = json.loads(r["prerequisites"])
        except Exception:
            p_list = []
            
        for p in p_list:
            target_id = None
            if p in name_to_id:
                target_id = name_to_id[p]
                
            if target_id:
                edges.append({
                    "id": f"prereq_{target_id}_{source_id}",
                    "source": target_id,  # Prerequisite is target of learning, source of dependency
                    "target": source_id,
                    "type": "PREREQUISITE",
                    "reason": f"Prerequisite for {r['name']}",
                    "is_prerequisite": True
                })
                
    return {"nodes": nodes, "edges": edges}

# AI Mirror Note Reflection
@app.post("/kb/notes/{id}/mirror")
def get_note_mirror_reflection(id: str, user_id: str = Depends(get_current_user_id)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch current note
    cursor.execute("SELECT name, type, definition_c FROM notes WHERE note_id = ? AND user_id = ?", (id, user_id))
    note = cursor.fetchone()
    if not note:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found.")
        
    # Fetch all other notes of the user
    cursor.execute("SELECT name, type FROM notes WHERE user_id = ? AND note_id != ?", (user_id, id))
    other_notes = [{"name": r["name"], "type": r["type"]} for r in cursor.fetchall()]
    
    conn.close()
    
    # Check for GEMINI_API_KEY in environment
    api_key = os.environ.get("GEMINI_API_KEY")
    
    reflection = ai_engine.generate_note_reflection(
        note_name=note["name"],
        note_type=note["type"],
        definition_c=note["definition_c"],
        existing_notes=other_notes,
        api_key=api_key
    )
    
    return {"reflection": reflection}

# Mount static files to serve the frontend on the root URL
app.mount("/", StaticFiles(directory="/home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/web", html=True), name="static")

