import json
import urllib.request
import re

# ---------------------------------------------------------------------------
# Mode template strings — used as fallback when Ollama is unavailable
# ---------------------------------------------------------------------------
MODE_TEMPLATES = {
    "STABILIZATION": {
        "title": "Stabilization Mode",
        "description": (
            "Neurophysiological alert. Your biological readiness to learn "
            "(sleep, fatigue, or nutrition) is currently compromised. "
            "Basic conditions for learning are not met."
        ),
        "recommendation": (
            "Stop studying new or difficult material immediately. Focus on "
            "physical recovery. Your workspace has been filtered to surface "
            "only highly familiar and mastered notes to minimise cognitive load."
        ),
        "directive": "Revisit highly familiar concepts (Mastery >= 4) or close the workspace and rest.",
    },
    "RECOVERY": {
        "title": "Recovery Mode",
        "description": (
            "Motivational alert. Your drive, regulation, or interest is running "
            "low. Mental resistance is high, making deep cognitive processing difficult."
        ),
        "recommendation": (
            "Do not push into new territory. Work on familiar, comfortable material. "
            "Your workspace has been filtered to show connected notes where you "
            "already have some understanding."
        ),
        "directive": "Review existing connections (Mastery >= 3) or add simple facts to existing notes.",
    },
    "CONSOLIDATION": {
        "title": "Consolidation Mode",
        "description": (
            "Balanced learning state. You are performing well relative to your own "
            "history. Your mind is ready to organise and integrate."
        ),
        "recommendation": (
            "Focus on depth rather than breadth. Look at concepts you have defined "
            "but not yet connected. Create links between ideas to build a cohesive schema."
        ),
        "directive": "Deepen definitions, add Layer C descriptions, and create connections for mid-range notes (Mastery 2-4).",
    },
    "PROGRESSION": {
        "title": "Progression Mode",
        "description": (
            "High cognitive availability. Your physiological state is strong, "
            "you are motivated, and your mind is clear."
        ),
        "recommendation": (
            "This is the optimal state to push into new territory. Tackle difficult "
            "concepts, create new notes, and explore the frontier of your knowledge graph."
        ),
        "directive": "Explore ghost notes (placeholders) and create new concepts (Mastery 0-1) to expand your graph.",
    },
    "PEAK": {
        "title": "Peak Flow Mode",
        "description": (
            "Exceptional cognitive state. Your proximity to both your personal best "
            "and the ideal learner profile is at its maximum."
        ),
        "recommendation": (
            "Engage in maximum challenge. Synthesise across different domains. "
            "Try to teach or connect widely separated namespaces in your graph."
        ),
        "directive": "Perform cross-domain synthesis. Map out complex systems and principles.",
    },
}

SUBP_NAMES = {
    "N1": "Sleep Quality",   "N2": "Fatigue",            "N3": "Hydration",       "N4": "Nutrition",
    "C1": "Working Memory",  "C2": "Processing Speed",   "C3": "Cognitive Flexibility", "C4": "Schema Activation",
    "M1": "Intrinsic Motivation", "M2": "Self-Regulation", "M3": "Goal Clarity",  "M4": "Effort Tolerance",
    "E1": "Noise Level",     "E2": "Physical Comfort",   "E3": "Tool Access",     "E4": "Social Pressure",
    "S1": "Granularity",     "S2": "Sequencing",         "S3": "Estimation",      "S4": "Reflection",
}

# ---------------------------------------------------------------------------
# Ollama API caller (zero external dependencies — uses urllib)
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL    = "qwen2.5:1.5b"


def call_ollama(prompt: str, system: str | None = None, timeout: int = 30) -> str:
    """
    Send a prompt to the local Ollama instance and return the response text.

    Args:
        prompt:  The user-facing prompt text.
        system:  Optional system instruction prepended to the conversation.
        timeout: HTTP read timeout in seconds (default 30s — small model is fast).

    Returns:
        Response text from the model, or an error string beginning with "Error:".
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload: dict = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# Diagnostic feedback generator
# ---------------------------------------------------------------------------

def generate_diagnostic_feedback(strategic_mode: str, bottleneck_list: list) -> dict:
    """
    Build the structured feedback object shown on the CDS output screen.

    The function first assembles a human-readable description of the current
    session state from templates, then asks Ollama/Qwen to rephrase it into
    a warm, 2-sentence personalised narrative (concise enough for the UI).
    If Ollama is unavailable the raw template text is used verbatim.

    Returns:
        {
            "title":               str,
            "diagnostic_narrative": str,
            "recommendation":      str,
            "kb_directive":        str,
        }
    """
    template = MODE_TEMPLATES.get(strategic_mode, MODE_TEMPLATES["CONSOLIDATION"])

    # Build readable bottleneck clause
    readable_bottlenecks = [SUBP_NAMES.get(b, b) for b in bottleneck_list]
    if len(readable_bottlenecks) == 1:
        bottleneck_clause = f"Detected bottleneck: {readable_bottlenecks[0]}."
    elif readable_bottlenecks:
        bottleneck_clause = (
            f"Detected bottlenecks: {', '.join(readable_bottlenecks[:-1])} "
            f"and {readable_bottlenecks[-1]}."
        )
    else:
        bottleneck_clause = ""

    raw_description = template["description"]
    if bottleneck_clause:
        raw_description = f"{raw_description} {bottleneck_clause}"

    # Try Ollama for a personalised rewrite
    system_instruction = (
        "You are a concise study coach. Rewrite the following diagnostic observation "
        "in warm, motivating language in exactly 2 sentences. Do not add advice — "
        "just rephrase the observation clearly. Return only the 2 sentences."
    )
    ai_narrative = call_ollama(raw_description, system=system_instruction, timeout=20)

    # Fallback to template text if Ollama fails
    if ai_narrative.startswith("Error:") or len(ai_narrative.strip()) < 10:
        ai_narrative = raw_description

    return {
        "title":                template["title"],
        "diagnostic_narrative": ai_narrative,
        "recommendation":       template["recommendation"],
        "kb_directive":         template["directive"],
    }


# ---------------------------------------------------------------------------
# AI Mirror — note reflection
# ---------------------------------------------------------------------------

def generate_note_reflection(
    note_name: str,
    note_type: str,
    definition_c: str,
    existing_notes: list,
    api_key: str | None = None,  # kept for backwards-compat; unused when Ollama is available
) -> str:
    """
    Generate an AI Mirror reflection for a knowledge note.

    The Mirror reflects the student's own words back to them, highlights
    overlapping concepts already in their workspace, and flags unknown terms
    as potential ghost notes (knowledge debts).

    Rules (enforced by the system prompt):
      1. Never add external knowledge.
      2. Only use the student's Layer C definition as source material.
      3. Identify connections to existing notes in the database.
      4. Flag unrecognised capitalised terms as potential ghost notes.

    Args:
        note_name:      Name of the note being reflected.
        note_type:      Epistemic type of the note (CONCEPT, FACT, etc.).
        definition_c:   The student's own Layer C definition text.
        existing_notes: List of {"name": str, "type": str} dicts for other notes.
        api_key:        Ignored — Ollama is used instead of cloud APIs.

    Returns:
        Markdown-formatted reflection string.
    """
    if not definition_c or not definition_c.strip():
        return (
            "I cannot mirror your thoughts until you write your own definition in "
            "Layer C. Try defining the concept in your own words first."
        )

    existing_notes_str = ", ".join(
        f"'{n['name']}' ({n['type']})" for n in existing_notes
    ) or "none yet"

    system_instruction = (
        "You are the KnowMe AI Mirror. Your purpose is to reflect the student's "
        "own words back to them to make their understanding visible.\n\n"
        "ABSOLUTE RULES:\n"
        "1. Do NOT act as a general chatbot. Do NOT answer open questions.\n"
        "2. Do NOT add external textbook definitions or new explanations.\n"
        "3. Rely ONLY on the student's Layer C definition to structure your response.\n"
        "4. Identify overlapping concepts between the student's definition and the "
        "   existing note names provided.\n"
        "5. Flag terms in the definition that look like concepts but are NOT in the "
        "   existing notes list — mark them as potential ghost notes (knowledge debt).\n"
        "Keep the response short, structured, and focused on reflecting the student's words.\n"
        "Use markdown formatting (bold, bullet points). Respond in 6 lines or fewer."
    )

    prompt = (
        f"Current concept: '{note_name}' ({note_type})\n"
        f"Student's own definition: \"{definition_c}\"\n"
        f"Other concepts already in the student's workspace: [{existing_notes_str}]\n\n"
        "Write a brief AI Mirror reflection. "
        "Highlight which existing concepts relate to this definition and "
        "identify any terms that should become ghost notes."
    )

    response = call_ollama(prompt, system=system_instruction, timeout=30)

    if response.startswith("Error:") or len(response.strip()) < 10:
        # Graceful rule-based fallback
        return _rule_based_reflection(note_name, note_type, definition_c, existing_notes)

    return response


# ---------------------------------------------------------------------------
# Rule-based fallback (no network required)
# ---------------------------------------------------------------------------

def _rule_based_reflection(
    note_name: str,
    note_type: str,
    definition_c: str,
    existing_notes: list,
) -> str:
    """
    Lightweight regex-based mirror reflection used when Ollama is unavailable.

    Logic:
      - Extract words from definition_c.
      - Match against existing note names (case-insensitive).
      - Flag capitalised words not in existing notes as potential ghost notes.
    """
    words = re.findall(r"\b[A-Za-z]+\b", definition_c)

    existing_names_lower = {n["name"].lower(): n["name"] for n in existing_notes}

    # Direct word match against existing notes
    connected_concepts = list({
        existing_names_lower[w.lower()]
        for w in words
        if w.lower() in existing_names_lower and w.lower() != note_name.lower()
    })

    # Capitalised words not in existing notes → ghost candidates
    STOP_WORDS = {"I", "The", "Le", "La", "Les", "We", "This", "It", "A", "An"}
    potential_ghosts = list({
        w for w in words
        if w[0].isupper()
        and len(w) > 1
        and w not in STOP_WORDS
        and w.lower() not in existing_names_lower
        and w.lower() != note_name.lower()
    })

    # Key content words (longer than 5 chars, ignore common words)
    COMMON = {"concept", "definition", "understanding", "system", "which", "where", "about"}
    key_words = [
        w.lower() for w in words
        if len(w) > 5 and w.lower() not in COMMON
    ][:3]

    lines = [
        f"**AI Mirror Reflection — {note_name}**",
        f"You defined this **{note_type.lower()}** as: *\"{definition_c}\"*",
    ]
    if key_words:
        lines.append(f"Core themes detected: *{', '.join(key_words)}*.")
    if connected_concepts:
        links = ", ".join(f"**{c}**" for c in connected_concepts)
        lines.append(f"💡 **Connected to existing notes:** {links}.")
    if potential_ghosts:
        ghosts_str = ", ".join(f"*{g}*" for g in potential_ghosts[:4])
        lines.append(
            f"👻 **Potential knowledge debt:** {ghosts_str} — "
            "these concepts do not exist in your workspace yet."
        )
    if not connected_concepts and not potential_ghosts:
        lines.append(
            "✨ Your definition is self-contained. "
            "Consider connecting this note to others using the connection builder."
        )

    return "\n".join(lines)
