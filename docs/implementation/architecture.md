# System Architecture — KnowMe

This document describes the architectural design and structural organization of the KnowMe platform.

## System Topology

KnowMe is designed as a strict decoupled client-server architecture consisting of a Python-based FastAPI backend and a Vanilla HTML/CSS/JavaScript frontend. Communication occurs exclusively over a JSON REST API.

```mermaid
graph TD
    subgraph Frontend [Web Interface - Client]
        UI[HTML/CSS Workspace] <--> Controller[App Controller - app.js]
        Controller <--> D3[Graph Renderer - graph.js]
    end
    
    subgraph Backend [Engine - REST API Server]
        API[FastAPI Router - main.py]
        DB[SQLite Database - database.py]
        CDS[CDS Engine - cds/engine.py]
        KB[KB Engine - kb/engine.py]
        AI[AI Mirror - ai/engine.py]
        
        API <--> CDS
        API <--> KB
        API <--> AI
        API <--> DB
    end
    
    Controller <-->|JSON REST API| API
```

## System Modules

The backend consists of four primary directories in `/src/`:

1.  **FastAPI Router ([main.py](file:///home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/src/main.py))**: Core server containing HTTP endpoint declarations, route controllers, validation, and JSON marshalling/unmarshalling.
2.  **Database Hub ([database.py](file:///home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/src/database.py))**: Handles connection pooling, SQLite pragmas (including enforcing foreign key constraints), and table initialization.
3.  **CDS Engine ([cds/engine.py](file:///home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/src/cds/engine.py))**: Contains mathematical modeling, Bayesian priors, Gaussian conjugate updates, proximity score calculations, and strategic mode criteria.
4.  **KB Graph Engine ([kb/engine.py](file:///home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/src/kb/engine.py))**: Handles structural graph operations: auto-creating ghost notes, checking prerequisites, recalculating metrics, and merging duplicate notes.
5.  **AI Mirror Engine ([ai/engine.py](file:///home/mightyj/Desktop/Development/projects/Group/ICT_SUMMIT/src/ai/engine.py))**: Integrates with the Gemini API to construct grounded reflections, falling back to a custom rule-based keyword extraction mirror when offline.

## Data Flow Diagram

The lifecycle of a single study session follows a strict data pipeline:

```mermaid
sequenceDiagram
    autonumber
    actor Student as Student (Client)
    participant API as FastAPI Server
    participant CDS as CDS Engine
    participant DB as SQLite DB
    participant KB as KB Engine
    participant AI as AI Mirror

    Student->>API: POST /sessions/start
    API->>DB: Load Session Count & Priors
    API-->>Student: Return 16 Onboarding or 6 selected questions
    Student->>API: POST /sessions/{id}/responses (user chips)
    API->>CDS: Perform Gaussian updates on priors
    CDS->>CDS: Compute Axis Scores, P_local, P_global
    CDS->>CDS: Select Strategic Mode & bottlenecks
    CDS->>AI: Fetch template diagnostic messages
    API->>DB: Update priors, scores, and save session snapshot
    API-->>Student: Return Scores, Mode, bottlenecks, and feedback
    Student->>API: GET /kb/notes & GET /kb/graph (Apply Mode Filter)
    API->>DB: Retrieve filtered notes & edges
    API-->>Student: Render dimmed/highlighted force layout
    Student->>API: PATCH /kb/notes/{id} (Type Layer C definition)
    API->>KB: Check status change & enforce gates
    API->>DB: Archive history & save note updates
    API-->>Student: Return updated note & final status
    Student->>API: POST /kb/notes/{id}/mirror
    API->>AI: Generate grounded reflection from Layer C
    AI-->>Student: Render reflective glass bubble
    Student->>API: POST /sessions/{id}/close
    API->>DB: Close session, increment session count, recalculate metrics
    API-->>Student: Success deltas
```
