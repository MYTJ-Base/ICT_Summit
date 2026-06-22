# Testing Documentation

## Test Coverage

The system is tested using a comprehensive suite of unit, integration, and end-to-end tests built with `pytest`.
- **Unit Tests (`test_cds.py`, `test_kb.py`)**: Tests individual functions and logic for the Cognitive Diagnostics System and Knowledge Base components. These test isolated logic and mathematical formulas (e.g., Bayesian updates).
- **Integration Tests (`test_api.py`)**: Tests the API endpoints and ensure that the backend correctly interfaces with the SQLite database, including authentication, session management, and note operations.
- **End-to-End Tests (`test_extended.py`)**: Tests complete user workflows, such as user registration, starting a session, submitting responses, and creating notes.

## Test Execution

### Requirements
- Python 3.10+
- `pytest`
- `httpx`

### Running the tests
To execute the tests, activate your virtual environment (if applicable) and run:
```bash
PYTHONPATH=. pytest
```
This command runs all test files located in the `/tests/` directory.

### Expected Outcomes
A successful run will display `passed` for all tests. Any failure indicates a bug in the code logic or the database operations.

## Component Validation Guide

### Cognitive Diagnostics System (CDS)
- **Validation**: Independent formulas like `compute_axis_scores` or `compute_proximity_scores` are tested directly.
- **Common Failures**: Mathematical errors due to missing dictionary keys (e.g. `AttributeError` on database rows).
- **Diagnose**: Run `pytest tests/test_cds.py` directly.

### Knowledge Base (KB)
- **Validation**: Graph creation and recalculation logic are tested.
- **Diagnose**: Check for circular dependencies or incorrect database schema constraints if `test_kb.py` fails.

### API & End-to-End
- **Validation**: Ensures the FastApi routes return the expected HTTP statuses.
- **Common Failures**: 404 or 500 status codes. Usually means the database state isn't correctly set up in the test, or a missing field in the request.
- **Diagnose**: Run `pytest tests/test_api.py -v` to see verbose errors, and check the server logs.
