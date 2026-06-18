# Source Code (The Engine)

### Responsibility
This directory owns the "Source of Truth" for the project's logic. It handles data processing, cognitive modeling, and AI orchestration.

### Sub-Modules
- `ai/`: Logic for the AI Mirror. Handles prompt engineering and grounding.
- `cds/`: The mathematical implementation of the Cognitive Diagnostic System.
- `kb/`: Logic for parsing, structuring, and connecting student knowledge notes.

### Standards
- **Language:** Python 3.10+
- **Separation:** No UI code (HTML/CSS) should live here. This code should be testable in isolation.
- **Output:** Prefers JSON outputs to be consumed by the `web/` layer.
