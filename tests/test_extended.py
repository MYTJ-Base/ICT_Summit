"""
Extended test suite for the KnowMe system.

Covers:
- Unit tests:        CDS engine, KB engine mastery gates
- Integration tests: Full API lifecycle via FastAPI TestClient
- Edge-case tests:   Ghost note creation, connection gates, mirror endpoint,
                     namespace management, graph query, session history,
                     duplicate user/note, invalid states
- Regression tests:  Mastery gates cannot be bypassed
"""

import json
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Shared test setup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Module-scoped TestClient.  Uses an in-memory test database so every
    test run starts clean without touching the real knowme.db.
    """
    import os
    os.environ["KNOWME_TEST_DB"] = ":memory:"

    from src.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def registered_user(client):
    """Register a fresh user and return the JSON payload."""
    resp = client.post("/auth/register", json={"display_name": "TestStudent_Extended"})
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture(scope="module")
def auth_headers(registered_user):
    return {"X-User-ID": registered_user["user_id"]}


@pytest.fixture(scope="module")
def onboarded_session(client, auth_headers):
    """Start a session and submit 16 onboarding responses, returning CDS result."""
    start = client.post("/sessions/start", headers=auth_headers)
    assert start.status_code == 200
    session_data = start.json()
    session_id = session_data["session_id"]
    questions = session_data["questions"]

    # Answer every question with a moderately good score
    responses = {q["id"]: 0.7 for q in questions}
    submit = client.post(
        f"/sessions/{session_id}/responses",
        headers=auth_headers,
        json={"responses": responses},
    )
    assert submit.status_code == 200
    return {"session_id": session_id, "cds": submit.json()}


# ===========================================================================
# Auth Tests
# ===========================================================================

class TestAuth:
    def test_register_new_user(self, client):
        resp = client.post("/auth/register", json={"display_name": "UniqueUser_XYZ"})
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert data["display_name"] == "UniqueUser_XYZ"

    def test_register_duplicate_name_fails(self, client, registered_user):
        resp = client.post(
            "/auth/register",
            json={"display_name": registered_user["display_name"]},
        )
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_login_existing_user(self, client, registered_user):
        resp = client.post(
            "/auth/login",
            json={"display_name": registered_user["display_name"]},
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == registered_user["user_id"]

    def test_login_unknown_user_returns_404(self, client):
        resp = client.post("/auth/login", json={"display_name": "NoSuchUser_ABC"})
        assert resp.status_code == 404

    def test_endpoints_require_user_id(self, client):
        """All protected endpoints must reject requests with no user identity."""
        for url, method in [
            ("/sessions/start", "post"),
            ("/kb/notes", "get"),
            ("/kb/graph", "get"),
        ]:
            resp = getattr(client, method)(url)
            # 411 is the code set in get_current_user_id for missing identity
            assert resp.status_code in (411, 422), f"{url} should require user_id"


# ===========================================================================
# Session / CDS Tests
# ===========================================================================

class TestSessions:
    def test_start_session_returns_questions(self, client, auth_headers):
        resp = client.post("/sessions/start", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert isinstance(data["questions"], list)
        assert len(data["questions"]) > 0

    def test_onboarding_returns_16_questions_first_time(self, client):
        """First session for a brand-new user must deliver exactly 16 onboarding questions."""
        reg = client.post("/auth/register", json={"display_name": "OnboardingCheck_001"})
        uid = reg.json()["user_id"]
        headers = {"X-User-ID": uid}

        start = client.post("/sessions/start", headers=headers)
        assert start.status_code == 200
        assert len(start.json()["questions"]) == 16

    def test_subsequent_session_returns_fewer_questions(self, client, auth_headers, onboarded_session):
        """After onboarding completes, the next session must select 6 highest-variance sub-pillars."""
        # Close the onboarding session first
        client.post(
            f"/sessions/{onboarded_session['session_id']}/close",
            headers=auth_headers,
            json={"notes_created": [], "notes_modified": [], "connections_added": []},
        )
        start2 = client.post("/sessions/start", headers=auth_headers)
        assert start2.status_code == 200
        q_count = len(start2.json()["questions"])
        assert q_count == 6, f"Expected 6 follow-up questions, got {q_count}"

    def test_submit_responses_returns_axis_scores(self, client, auth_headers):
        start = client.post("/sessions/start", headers=auth_headers)
        sid = start.json()["session_id"]
        questions = start.json()["questions"]
        responses = {q["id"]: 0.9 for q in questions}
        resp = client.post(
            f"/sessions/{sid}/responses",
            headers=auth_headers,
            json={"responses": responses},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "axis_scores" in data
        assert set(data["axis_scores"].keys()) == {"N", "C", "M", "E", "S"}
        assert "strategic_mode" in data
        assert data["strategic_mode"] in (
            "STABILIZATION", "RECOVERY", "CONSOLIDATION", "PROGRESSION", "PEAK"
        )

    def test_session_history_endpoint(self, client, auth_headers):
        resp = client.get("/sessions/history", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_session_by_id(self, client, auth_headers, onboarded_session):
        sid = onboarded_session["session_id"]
        resp = client.get(f"/sessions/{sid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["session_id"] == sid

    def test_get_session_wrong_user_returns_404(self, client, onboarded_session):
        # Different user should not see this session
        other = client.post("/auth/register", json={"display_name": "Stranger_User_001"})
        other_headers = {"X-User-ID": other.json()["user_id"]}
        sid = onboarded_session["session_id"]
        resp = client.get(f"/sessions/{sid}", headers=other_headers)
        assert resp.status_code == 404

    def test_close_session(self, client, auth_headers):
        start = client.post("/sessions/start", headers=auth_headers)
        sid = start.json()["session_id"]
        questions = start.json()["questions"]
        client.post(
            f"/sessions/{sid}/responses",
            headers=auth_headers,
            json={"responses": {q["id"]: 0.6 for q in questions}},
        )
        close = client.post(
            f"/sessions/{sid}/close",
            headers=auth_headers,
            json={"notes_created": [], "notes_modified": [], "connections_added": []},
        )
        assert close.status_code == 200
        assert close.json()["status"] == "closed"

    def test_low_n_sub_pillar_triggers_stabilization(self, client):
        """Sending a critically low N1 value (0.1) should produce STABILIZATION mode."""
        reg = client.post("/auth/register", json={"display_name": "Stab_Test_001"})
        uid = reg.json()["user_id"]
        headers = {"X-User-ID": uid}
        start = client.post("/sessions/start", headers=headers)
        sid = start.json()["session_id"]
        questions = start.json()["questions"]

        # Build responses — all high except any N sub-pillar
        responses = {}
        for q in questions:
            if q["sub_pillar"].startswith("N"):
                responses[q["id"]] = 0.1   # critically low
            else:
                responses[q["id"]] = 0.9
        submit = client.post(
            f"/sessions/{sid}/responses",
            headers=headers,
            json={"responses": responses},
        )
        assert submit.status_code == 200
        assert submit.json()["strategic_mode"] == "STABILIZATION"


# ===========================================================================
# KB Notes Tests
# ===========================================================================

class TestKBNotes:
    @pytest.fixture(autouse=True)
    def _ensure_session(self, client, auth_headers, onboarded_session):
        """Reuse onboarded session so tests can hit KB endpoints."""
        self.session_id = onboarded_session["session_id"]

    def test_create_note(self, client, auth_headers):
        resp = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "Entropy", "type": "CONCEPT", "namespace": ["Thermodynamics"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Entropy"
        assert data["ghost"] is False
        assert data["status"] == 0

    def test_create_duplicate_note_returns_400(self, client, auth_headers):
        client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "DuplicateNote_Test", "type": "FACT"},
        )
        resp = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "DuplicateNote_Test", "type": "FACT"},
        )
        assert resp.status_code == 400

    def test_prerequisites_auto_create_ghost_notes(self, client, auth_headers):
        resp = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={
                "name": "QuantumEntanglement",
                "type": "CONCEPT",
                "prerequisites": ["WaveFunction", "SpinState"],
            },
        )
        assert resp.status_code == 200

        notes = client.get("/kb/notes", headers=auth_headers).json()
        ghost_names = {n["name"] for n in notes if n["ghost"]}
        assert "WaveFunction" in ghost_names
        assert "SpinState" in ghost_names

    def test_creating_note_with_ghost_prereq_name_promotes_ghost(self, client, auth_headers):
        """If a ghost note already exists, POSTing a real note with the same name promotes it."""
        # Create a note with a prerequisite called 'GhostTarget'
        client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "RealNoteA", "type": "CONCEPT", "prerequisites": ["GhostTarget"]},
        )
        # Now create GhostTarget as a real note
        resp = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "GhostTarget", "type": "PRINCIPLE"},
        )
        assert resp.status_code == 200
        assert resp.json()["ghost"] is False

    def test_get_note_by_id(self, client, auth_headers):
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "Photon_GetTest", "type": "CONCEPT"},
        )
        note_id = create.json()["note_id"]
        resp = client.get(f"/kb/notes/{note_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["note_id"] == note_id

    def test_get_note_wrong_user_returns_404(self, client):
        reg = client.post("/auth/register", json={"display_name": "NoteThief_001"})
        thief_headers = {"X-User-ID": reg.json()["user_id"]}
        # Create a note as the thief (so the user exists)
        create = client.post(
            "/kb/notes",
            headers=thief_headers,
            json={"name": "ThiefNote", "type": "FACT"},
        )
        note_id = create.json()["note_id"]

        # Try to access with a totally different user
        reg2 = client.post("/auth/register", json={"display_name": "Innocent_User_001"})
        innocent_headers = {"X-User-ID": reg2.json()["user_id"]}
        resp = client.get(f"/kb/notes/{note_id}", headers=innocent_headers)
        assert resp.status_code == 404

    def test_update_note_definition_c(self, client, auth_headers):
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "Velocity_UpdateTest", "type": "CONCEPT"},
        )
        nid = create.json()["note_id"]
        resp = client.patch(
            f"/kb/notes/{nid}",
            headers=auth_headers,
            json={"definition_c": "Rate of displacement over time."},
        )
        assert resp.status_code == 200
        assert resp.json()["definition_c"] == "Rate of displacement over time."

    def test_get_notes_with_type_filter(self, client, auth_headers):
        client.post("/kb/notes", headers=auth_headers, json={"name": "TypeFilter_Fact", "type": "FACT"})
        resp = client.get("/kb/notes", headers=auth_headers, params={"type": "FACT"})
        assert resp.status_code == 200
        for note in resp.json():
            assert note["type"] == "FACT"

    def test_get_notes_with_ghost_filter(self, client, auth_headers):
        client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "GhostFilterParent", "type": "CONCEPT", "prerequisites": ["GhostFilterChild"]},
        )
        resp = client.get("/kb/notes", headers=auth_headers, params={"ghost": True})
        assert resp.status_code == 200
        for note in resp.json():
            assert note["ghost"] is True


# ===========================================================================
# Mastery Gate Tests (Regression)
# ===========================================================================

class TestMasteryGates:
    def test_status_cannot_exceed_1_without_definition_c(self, client, auth_headers):
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "GateTest_NoDefC", "type": "CONCEPT"},
        )
        nid = create.json()["note_id"]
        resp = client.patch(
            f"/kb/notes/{nid}",
            headers=auth_headers,
            json={"status": 3},  # Requesting status 3 without Layer C
        )
        assert resp.status_code == 200
        # System must silently cap at 1
        assert resp.json()["status"] == 1

    def test_status_can_reach_2_after_definition_c(self, client, auth_headers):
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "GateTest_WithDefC", "type": "CONCEPT"},
        )
        nid = create.json()["note_id"]
        resp = client.patch(
            f"/kb/notes/{nid}",
            headers=auth_headers,
            json={"definition_c": "A test definition.", "status": 2},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == 2

    def test_status_cannot_exceed_2_without_connections(self, client, auth_headers):
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "GateTest_NoConn", "type": "CONCEPT"},
        )
        nid = create.json()["note_id"]
        client.patch(
            f"/kb/notes/{nid}",
            headers=auth_headers,
            json={"definition_c": "Some definition."},
        )
        resp = client.patch(
            f"/kb/notes/{nid}",
            headers=auth_headers,
            json={"status": 4},  # Requesting 4 with no connections
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == 2  # Capped at 2

    def test_status_3_unlocked_after_two_connections(self, client, auth_headers):
        # Create main note
        n1 = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "GateTest_Main", "type": "CONCEPT"},
        ).json()
        # Add definition_c
        client.patch(
            f"/kb/notes/{n1['note_id']}",
            headers=auth_headers,
            json={"definition_c": "Main concept definition."},
        )

        # Create two target notes
        n2 = client.post("/kb/notes", headers=auth_headers, json={"name": "GateTest_Target1", "type": "FACT"}).json()
        n3 = client.post("/kb/notes", headers=auth_headers, json={"name": "GateTest_Target2", "type": "FACT"}).json()

        # Create two connections
        client.post(
            "/kb/connections",
            headers=auth_headers,
            json={"source_id": n1["note_id"], "target_id": n2["note_id"], "type": "REINFORCES", "reason": "Reason A"},
        )
        client.post(
            "/kb/connections",
            headers=auth_headers,
            json={"source_id": n1["note_id"], "target_id": n3["note_id"], "type": "IS-USED-IN", "reason": "Reason B"},
        )

        # Now set status 3
        resp = client.patch(
            f"/kb/notes/{n1['note_id']}",
            headers=auth_headers,
            json={"status": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == 3


# ===========================================================================
# Connection Tests
# ===========================================================================

class TestConnections:
    def _create_two_notes(self, client, auth_headers, suffix):
        a = client.post("/kb/notes", headers=auth_headers, json={"name": f"ConnA_{suffix}", "type": "CONCEPT"}).json()
        b = client.post("/kb/notes", headers=auth_headers, json={"name": f"ConnB_{suffix}", "type": "FACT"}).json()
        return a["note_id"], b["note_id"]

    def test_create_connection(self, client, auth_headers):
        aid, bid = self._create_two_notes(client, auth_headers, "Create")
        resp = client.post(
            "/kb/connections",
            headers=auth_headers,
            json={"source_id": aid, "target_id": bid, "type": "GENERALIZES", "reason": "A generalises B"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == aid
        assert data["target_id"] == bid

    def test_duplicate_connection_returns_400(self, client, auth_headers):
        aid, bid = self._create_two_notes(client, auth_headers, "Dup")
        payload = {"source_id": aid, "target_id": bid, "type": "REINFORCES", "reason": "Same link"}
        client.post("/kb/connections", headers=auth_headers, json=payload)
        resp = client.post("/kb/connections", headers=auth_headers, json=payload)
        assert resp.status_code == 400

    def test_delete_connection(self, client, auth_headers):
        aid, bid = self._create_two_notes(client, auth_headers, "Del")
        create = client.post(
            "/kb/connections",
            headers=auth_headers,
            json={"source_id": aid, "target_id": bid, "type": "FUZZY", "reason": "Fuzzy link"},
        )
        conn_id = create.json()["connection_id"]
        resp = client.delete(f"/kb/connections/{conn_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_unknown_connection_returns_404(self, client, auth_headers):
        resp = client.delete("/kb/connections/nonexistent-conn-id", headers=auth_headers)
        assert resp.status_code == 404


# ===========================================================================
# Graph Query Tests
# ===========================================================================

class TestGraph:
    def test_get_graph_structure(self, client, auth_headers):
        resp = client.get("/kb/graph", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_graph_nodes_have_required_fields(self, client, auth_headers):
        client.post("/kb/notes", headers=auth_headers, json={"name": "GraphTest_Node", "type": "MODEL"})
        resp = client.get("/kb/graph", headers=auth_headers)
        nodes = resp.json()["nodes"]
        required_fields = {"id", "name", "type", "status", "ghost", "namespace", "unlocks_known"}
        for node in nodes:
            assert required_fields.issubset(node.keys()), f"Node missing fields: {node}"

    def test_prerequisite_edges_in_graph(self, client, auth_headers):
        """Notes with declared prerequisites should generate PREREQUISITE edges in the graph."""
        parent = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "Graph_Parent", "type": "CONCEPT", "prerequisites": ["Graph_Prereq"]},
        ).json()
        resp = client.get("/kb/graph", headers=auth_headers)
        prereq_edges = [e for e in resp.json()["edges"] if e.get("is_prerequisite")]
        assert len(prereq_edges) > 0


# ===========================================================================
# Namespace Tests
# ===========================================================================

class TestNamespaces:
    def test_create_namespace(self, client, auth_headers):
        resp = client.post("/kb/namespaces", headers=auth_headers, json={"name": "Physics_NS"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Physics_NS"

    def test_create_duplicate_namespace_returns_400(self, client, auth_headers):
        client.post("/kb/namespaces", headers=auth_headers, json={"name": "DupNS_Test"})
        resp = client.post("/kb/namespaces", headers=auth_headers, json={"name": "DupNS_Test"})
        assert resp.status_code == 400

    def test_list_namespaces(self, client, auth_headers):
        client.post("/kb/namespaces", headers=auth_headers, json={"name": "ListNS_Test"})
        resp = client.get("/kb/namespaces", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_child_namespace(self, client, auth_headers):
        parent = client.post("/kb/namespaces", headers=auth_headers, json={"name": "ParentNS"}).json()
        child = client.post(
            "/kb/namespaces",
            headers=auth_headers,
            json={"name": "ChildNS", "parent_namespace_id": parent["namespace_id"]},
        )
        assert child.status_code == 200
        assert child.json()["parent_namespace_id"] == parent["namespace_id"]


# ===========================================================================
# AI Mirror Endpoint Test
# ===========================================================================

class TestAIMirror:
    def test_mirror_without_definition_c_returns_prompt(self, client, auth_headers):
        """Mirror must ask student to write Layer C before reflecting."""
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "MirrorNoDefC", "type": "CONCEPT"},
        )
        nid = create.json()["note_id"]
        resp = client.post(f"/kb/notes/{nid}/mirror", headers=auth_headers)
        assert resp.status_code == 200
        assert "Layer C" in resp.json()["reflection"]

    def test_mirror_with_definition_c_returns_reflection(self, client, auth_headers):
        """Mirror should return a non-empty reflection string when Layer C exists."""
        create = client.post(
            "/kb/notes",
            headers=auth_headers,
            json={"name": "MirrorWithDefC", "type": "CONCEPT"},
        )
        nid = create.json()["note_id"]
        client.patch(
            f"/kb/notes/{nid}",
            headers=auth_headers,
            json={"definition_c": "Energy cannot be created or destroyed, only converted."},
        )
        resp = client.post(f"/kb/notes/{nid}/mirror", headers=auth_headers)
        assert resp.status_code == 200
        reflection = resp.json()["reflection"]
        assert isinstance(reflection, str)
        assert len(reflection) > 20

    def test_mirror_unknown_note_returns_404(self, client, auth_headers):
        resp = client.post("/kb/notes/nonexistent-note-id/mirror", headers=auth_headers)
        assert resp.status_code == 404


# ===========================================================================
# CDS Engine Unit Tests  (direct module tests, no HTTP)
# ===========================================================================

class TestCDSEngineUnit:
    def test_get_initial_priors_keys(self):
        from src.cds.engine import get_initial_priors, SUB_PILLARS
        priors = get_initial_priors()
        assert set(priors.keys()) == set(SUB_PILLARS.keys())
        for sp, val in priors.items():
            assert val["mu"] == 0.5
            assert val["sigma"] == 0.5

    def test_bayesian_update_shifts_mean_toward_observation(self):
        from src.cds.engine import bayesian_update
        mu_post, sigma_post = bayesian_update(0.5, 0.5, 1.0)
        assert mu_post > 0.5, "Observation of 1.0 should raise the mean"
        assert sigma_post < 0.5, "Posterior variance must be less than prior variance"

    def test_bayesian_update_bounds_mu(self):
        from src.cds.engine import bayesian_update
        mu_post, _ = bayesian_update(0.0, 0.5, 0.0)
        assert mu_post >= 0.0
        mu_post2, _ = bayesian_update(1.0, 0.5, 1.0)
        assert mu_post2 <= 1.0

    def test_compute_axis_scores_returns_five_axes(self):
        from src.cds.engine import compute_axis_scores, get_initial_priors
        scores = compute_axis_scores(get_initial_priors())
        assert set(scores.keys()) == {"N", "C", "M", "E", "S"}
        for v in scores.values():
            assert 0.0 <= v <= 1.0

    def test_select_next_questions_returns_correct_count(self):
        from src.cds.engine import select_next_questions, get_initial_priors
        priors = get_initial_priors()
        qs = select_next_questions(priors, num_questions=6)
        assert len(qs) == 6

    def test_stabilization_triggered_by_low_n(self):
        from src.cds.engine import determine_strategic_mode, get_initial_priors, compute_axis_scores
        priors = get_initial_priors()
        priors["N1"]["mu"] = 0.1   # critically low
        scores = compute_axis_scores(priors)
        mode = determine_strategic_mode(priors, scores, 0.5, 0.5)
        assert mode == "STABILIZATION"

    def test_peak_triggered_by_very_high_proximity(self):
        from src.cds.engine import determine_strategic_mode, get_initial_priors, compute_axis_scores
        priors = get_initial_priors()
        for sp in priors:
            priors[sp]["mu"] = 0.95
        scores = compute_axis_scores(priors)
        mode = determine_strategic_mode(priors, scores, 0.92, 0.88)
        assert mode == "PEAK"

    def test_get_bottlenecks_returns_low_pillars(self):
        from src.cds.engine import get_bottlenecks, get_initial_priors
        priors = get_initial_priors()
        priors["N1"]["mu"] = 0.1
        priors["M2"]["mu"] = 0.2
        bottlenecks = get_bottlenecks(priors)
        assert "N1" in bottlenecks
        assert "M2" in bottlenecks
        assert len(bottlenecks) <= 3


# ===========================================================================
# KB Engine Unit Tests  (direct module tests)
# ===========================================================================

class TestKBEngineUnit:
    def test_mastery_gate_no_definition_c(self):
        from src.kb.engine import enforce_mastery_gates
        assert enforce_mastery_gates(None, 3, 10) == 1
        assert enforce_mastery_gates("", 4, 10) == 1

    def test_mastery_gate_no_connections(self):
        from src.kb.engine import enforce_mastery_gates
        assert enforce_mastery_gates("Good definition", 4, 1) == 2
        assert enforce_mastery_gates("Good definition", 3, 0) == 2

    def test_mastery_gate_passes_when_conditions_met(self):
        from src.kb.engine import enforce_mastery_gates
        assert enforce_mastery_gates("Good definition", 3, 5) == 3
        assert enforce_mastery_gates("Good definition", 5, 5) == 5

    def test_mastery_gate_clamps_to_5(self):
        from src.kb.engine import enforce_mastery_gates
        assert enforce_mastery_gates("Good definition", 99, 10) == 5

    def test_mastery_gate_min_is_0(self):
        from src.kb.engine import enforce_mastery_gates
        assert enforce_mastery_gates(None, -5, 10) == 0


# ===========================================================================
# AI Engine Unit Tests  (direct module tests — uses rule-based path)
# ===========================================================================

class TestAIEngineUnit:
    def test_generate_diagnostic_feedback_structure(self):
        from src.ai.engine import generate_diagnostic_feedback
        for mode in ("STABILIZATION", "RECOVERY", "CONSOLIDATION", "PROGRESSION", "PEAK"):
            result = generate_diagnostic_feedback(mode, [])
            assert "title" in result
            assert "diagnostic_narrative" in result
            assert "recommendation" in result
            assert "kb_directive" in result

    def test_reflection_without_definition_c(self):
        from src.ai.engine import generate_note_reflection
        result = generate_note_reflection("Test", "CONCEPT", "", [])
        assert "Layer C" in result

    def test_rule_based_reflection_fallback(self):
        """Directly test the rule-based fallback (no Ollama required)."""
        from src.ai.engine import _rule_based_reflection
        existing = [{"name": "Energy", "type": "CONCEPT"}, {"name": "Motion", "type": "CONCEPT"}]
        result = _rule_based_reflection(
            "Kinetic Energy",
            "CONCEPT",
            "Kinetic Energy is the energy of Motion of an object due to its velocity.",
            existing,
        )
        assert "Energy" in result or "Motion" in result
        assert isinstance(result, str)
        assert len(result) > 0
