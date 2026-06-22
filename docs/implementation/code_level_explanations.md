# Code-Level Explanations

## `src/main.py`
**Purpose**: This is the core FastAPI application entry point.
- **Why it exists**: To serve HTTP endpoints for the frontend, enabling operations like authentication, session management, and KB updates.
- **Interactions**: Interfaces directly with the SQLite database and imports logic from `cds_engine`, `kb_engine`, and `ai_engine`.

## `src/cds/engine.py`
**Purpose**: Handles the logic for the Cognitive Diagnostics System.
- **Major Functions**: 
  - `compute_proximity_scores`: Calculates how a student is performing relative to their personal best (`p_local`) and the ideal state (`p_global`).
  - `bayesian_update`: Adjusts the prior distributions of the student's cognitive model based on new responses.
- **Why the implementation was chosen**: Uses Bayesian logic to create a dynamic, evolving model of the student's state over time, allowing personalized recommendations.

## `src/kb/engine.py`
**Purpose**: Handles Knowledge Base operations.
- **Major Functions**: Graph traversal, updating mastery scores, finding dependencies.
- **Why it exists**: Provides the logic to pull "knowledge out" of the student and represent it visually and logically as a connected graph.

## `src/database.py`
**Purpose**: Manages the SQLite database connection and initialization.
- **Why it exists**: Stores all user, session, and knowledge graph data locally (offline-first capability as outlined in the README).
