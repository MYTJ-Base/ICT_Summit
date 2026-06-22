# Architectural Design Decisions — KnowMe

This document records the major design decisions made during the prototyping phase of the KnowMe project, outlining alternatives and rationales.

## 1. Single-User Database Design (SQLite)
*   **Decision**: Use SQLite as the database for the prototype, utilizing tables with UUID primary keys and structured JSON string representation for collections (like prerequisites, namespaces, priors).
*   **Rationale**: SQLite provides zero-configuration local persistence which is perfect for student developers and offline operations. Designing the tables with standard UUID primary keys and strict column types ensures that migrating to a production PostgreSQL database requires no change in schema logic, only swapping the driver.
*   **Alternatives Considered**:
    *   *JSON File Database*: Extremely simple but fails on concurrency and relational foreign-key constraint enforcement (such as deleting a user deleting their sessions/notes automatically).
    *   *Real PostgreSQL instance*: Introduces heavy installation, configuration, and environment setup overhead which is not desirable for an 8-week rapid challenge prototype.

## 2. Bayesian Update model (Gaussian Conjugate Priors)
*   **Decision**: Represent student availability on each sub-pillar as a normal distribution $N(\mu, \sigma^2)$, updating it using conjugate Gaussian priors with a response noise standard deviation $\sigma_{obs} = 0.22$.
*   **Rationale**: The Gaussian conjugate prior model provides a mathematically rigorous way to handle learning self-reports. Since we start with a high standard deviation (high uncertainty, $\sigma_{prior} = 0.5$, variance $= 0.25$), each question response narrows down the variance and shifts the mean towards the user's selected choice. This model avoids arbitrary thresholds and behaves predictably.
*   **Alternatives Considered**:
    *   *Simple Exponential Moving Average (EMA)*: Easier to implement, but lacks structural representation of confidence/uncertainty, making it impossible to select questions by "highest-variance" information value.

## 3. Mastery Level Gates Enforcement
*   **Decision**: Enforce gates automatically inside the note PATCH endpoint rather than relying on frontend logic. Downgrade target status if criteria are not met.
*   **Rationale**: Students should not be able to manually declare a concept "Mastered" without writing a definition (Layer C) or connecting it. By enforcing this in the backend, the integrity of the data structure is preserved across all API endpoints (curl, tests, frontend).
*   **Alternatives Considered**:
    *   *Frontend Validation only*: Lightweight, but vulnerable if the client uses direct API requests or bypasses the UI, violating database logic constraints.

## 4. Zero-Dependency AI Mirror Fallback
*   **Decision**: Implement a custom keyword/noun parser to create a rule-based AI reflection, querying the Gemini API via raw `urllib.request` only if a `GEMINI_API_KEY` is present.
*   **Rationale**: Serving Cameroonian classrooms requires offline capability (core KB). By writing a smart rule-based parser that mirrors the user's words, extracts overlapping notes, and suggests ghost note placeholders based on unrecognized capitalized words, the prototype runs 100% offline without any API key. If the user provides a key, it seamlessly upgrades to a full generative reflection.
*   **Alternatives Considered**:
    *   *Mandatory LLM API calls*: Fails completely if offline or if the API key is not configured, breaking the core demo.
