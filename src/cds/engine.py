import json
import math

# Define the sub-pillars and their mapping to axes
SUB_PILLARS = {
    "N1": "N", "N2": "N", "N3": "N", "N4": "N",
    "C1": "C", "C2": "C", "C3": "C", "C4": "C",
    "M1": "M", "M2": "M", "M3": "M", "M4": "M",
    "E1": "E", "E2": "E", "E3": "E", "E4": "E",
    "S1": "S", "S2": "S", "S3": "S", "S4": "S"
}

AXIS_NAMES = {
    "N": "Neurophysiological",
    "C": "Cognitive",
    "M": "Motivational",
    "E": "Environmental",
    "S": "Strategic"
}

# The 20 anchor questions
QUESTIONS = [
    {
        "id": "q_N1",
        "sub_pillar": "N1",
        "text": "How did you sleep last night?",
        "options": [
            {"label": "Woke up multiple times, feel exhausted", "value": 0.1},
            {"label": "Tossed and turned, average rest", "value": 0.4},
            {"label": "Slept well, minor disruptions", "value": 0.7},
            {"label": "Deep, uninterrupted sleep, fully refreshed", "value": 1.0}
        ]
    },
    {
        "id": "q_N2",
        "sub_pillar": "N2",
        "text": "How is your mental energy right now?",
        "options": [
            {"label": "Severely burned out, cannot think", "value": 0.1},
            {"label": "Heavy mental fatigue, slow thinking", "value": 0.4},
            {"label": "Mild tiredness, but manageable", "value": 0.7},
            {"label": "Energetic, clear-headed, ready to build", "value": 1.0}
        ]
    },
    {
        "id": "q_N3",
        "sub_pillar": "N3",
        "text": "Have you had enough water today?",
        "options": [
            {"label": "Hardly any water, feeling thirsty/headache", "value": 0.1},
            {"label": "Only a cup or two, slightly dry", "value": 0.5},
            {"label": "Well hydrated, drank regularly", "value": 1.0}
        ]
    },
    {
        "id": "q_N4",
        "sub_pillar": "N4",
        "text": "How is your physical nourishment today?",
        "options": [
            {"label": "Missed meals, feeling empty/weak", "value": 0.1},
            {"label": "Ate junk food/heavy sugar, feeling sluggish", "value": 0.5},
            {"label": "Balanced, nutritious meals, stable energy", "value": 1.0}
        ]
    },
    {
        "id": "q_C1",
        "sub_pillar": "C1",
        "text": "How easily can you hold complex ideas in your head right now?",
        "options": [
            {"label": "Constantly losing track, highly distracted", "value": 0.1},
            {"label": "Need to write everything down to follow", "value": 0.5},
            {"label": "Can hold and manipulate ideas easily", "value": 1.0}
        ]
    },
    {
        "id": "q_C2",
        "sub_pillar": "C2",
        "text": "How fast are you absorbing information right now?",
        "options": [
            {"label": "Slower than usual, reading things 3 times", "value": 0.1},
            {"label": "Steady pace, normal comprehension speed", "value": 0.6},
            {"label": "Very fast, grasping concepts instantly", "value": 1.0}
        ]
    },
    {
        "id": "q_C3",
        "sub_pillar": "C3",
        "text": "How easily can you switch between different tasks or logic?",
        "options": [
            {"label": "Feeling rigid, stuck on one detail", "value": 0.1},
            {"label": "Slight friction when shifting focus", "value": 0.6},
            {"label": "Fluid transitions, adaptive mindset", "value": 1.0}
        ]
    },
    {
        "id": "q_C4",
        "sub_pillar": "C4",
        "text": "How well do you remember related concepts in this domain?",
        "options": [
            {"label": "Mind feels blank, struggling to recall basics", "value": 0.1},
            {"label": "Can recall with effort, patchy memory", "value": 0.6},
            {"label": "Related concepts immediately present in mind", "value": 1.0}
        ]
    },
    {
        "id": "q_M1",
        "sub_pillar": "M1",
        "text": "How interested are you in today's study topic?",
        "options": [
            {"label": "Doing it purely out of obligation, bored", "value": 0.1},
            {"label": "Moderately curious, some interest", "value": 0.6},
            {"label": "Deeply fascinated, eager to explore", "value": 1.0}
        ]
    },
    {
        "id": "q_M2",
        "sub_pillar": "M2",
        "text": "How easily can you resist distractions (phone, social media)?",
        "options": [
            {"label": "Constantly checking phone, no discipline", "value": 0.1},
            {"label": "Occasionally distracted, but can re-focus", "value": 0.6},
            {"label": "Completely locked in, zero distraction", "value": 1.0}
        ]
    },
    {
        "id": "q_M3",
        "sub_pillar": "M3",
        "text": "How clear is what you want to achieve in this session?",
        "options": [
            {"label": "No specific plan, just browsing", "value": 0.2},
            {"label": "Have a general topic, but vague goals", "value": 0.6},
            {"label": "Exact, measurable checklist ready", "value": 1.0}
        ]
    },
    {
        "id": "q_M4",
        "sub_pillar": "M4",
        "text": "Are you ready to push through confusion or hard problems?",
        "options": [
            {"label": "Will give up quickly if it gets frustrating", "value": 0.2},
            {"label": "Will try, but might seek help early", "value": 0.6},
            {"label": "Ready to wrestle with difficult bugs/math", "value": 1.0}
        ]
    },
    {
        "id": "q_E1",
        "sub_pillar": "E1",
        "text": "How is the sound environment around you?",
        "options": [
            {"label": "Extremely loud, chaotic (construction, traffic)", "value": 0.1},
            {"label": "Moderate chatter or background noise", "value": 0.6},
            {"label": "Perfect silence or focus-friendly ambient sound", "value": 1.0}
        ]
    },
    {
        "id": "q_E2",
        "sub_pillar": "E2",
        "text": "How comfortable is your study workspace?",
        "options": [
            {"label": "Poor posture, bad chair, too hot/cold", "value": 0.1},
            {"label": "Okay setup, minor physical discomfort", "value": 0.6},
            {"label": "Ergonomic chair, perfect temperature", "value": 1.0}
        ]
    },
    {
        "id": "q_E3",
        "sub_pillar": "E3",
        "text": "Do you have all the books, scripts, or systems you need?",
        "options": [
            {"label": "Missing key resources, constantly searching", "value": 0.2},
            {"label": "Have most tools, minor friction", "value": 0.7},
            {"label": "All resources open and running seamlessly", "value": 1.0}
        ]
    },
    {
        "id": "q_E4",
        "sub_pillar": "E4",
        "text": "Are there social interruptions or expectations on you?",
        "options": [
            {"label": "Constantly interrupted by family/peers", "value": 0.1},
            {"label": "Mild social presence, some distraction risk", "value": 0.6},
            {"label": "Completely uninterrupted personal space", "value": 1.0}
        ]
    },
    {
        "id": "q_S1",
        "sub_pillar": "S1",
        "text": "How well have you broken down the topic into small parts?",
        "options": [
            {"label": "Looking at a massive, overwhelming wall of info", "value": 0.2},
            {"label": "Broken down into generic sections", "value": 0.6},
            {"label": "Finely sliced into atomic, bite-sized tasks", "value": 1.0}
        ]
    },
    {
        "id": "q_S2",
        "sub_pillar": "S2",
        "text": "Do you know what order to study these concepts in?",
        "options": [
            {"label": "No idea, jumping around randomly", "value": 0.2},
            {"label": "Following a textbook/syllabus order", "value": 0.6},
            {"label": "Custom logical order tailored to dependencies", "value": 1.0}
        ]
    },
    {
        "id": "q_S3",
        "sub_pillar": "S3",
        "text": "How accurate are your estimates of how long this takes?",
        "options": [
            {"label": "Clueless, often run out of time", "value": 0.2},
            {"label": "Roughly correct, with some buffer", "value": 0.7},
            {"label": "Precise tracking of learning speed", "value": 1.0}
        ]
    },
    {
        "id": "q_S4",
        "sub_pillar": "S4",
        "text": "How often do you review what you did and adjust your study habits?",
        "options": [
            {"label": "Never, just move on to the next chapter", "value": 0.1},
            {"label": "Occasionally look back before tests", "value": 0.6},
            {"label": "Actively reflect and document habits daily", "value": 1.0}
        ]
    }
]

# We need onboarding (16 questions). Let's take the first 16 questions (N1-N4, C1-C4, M1-M4, E1-E4)
# S1-S4 can be updated after or we can just ask 16 questions that cover 16 sub-pillars.
ONBOARDING_QUESTIONS_IDS = [q["id"] for q in QUESTIONS[:16]]

def get_initial_priors():
    # Mean = 0.5, Variance = 0.25 (highly uncertain) for all 20 sub-pillars
    priors = {}
    for sp in SUB_PILLARS:
        priors[sp] = {"mu": 0.5, "sigma": 0.5}  # standard deviation = 0.5, variance = 0.25
    return priors

def compute_axis_scores(priors):
    scores = {"N": 0.0, "C": 0.0, "M": 0.0, "E": 0.0, "S": 0.0}
    counts = {"N": 0, "C": 0, "M": 0, "E": 0, "S": 0}
    for sp, data in priors.items():
        axis = SUB_PILLARS[sp]
        scores[axis] += data["mu"]
        counts[axis] += 1
    
    for axis in scores:
        if counts[axis] > 0:
            scores[axis] = round(scores[axis] / counts[axis], 3)
    return scores

def bayesian_update(prior_mu, prior_sigma, observation_y, obs_sigma=0.22):
    # Obs_sigma represents standard deviation of observation noise (variance = 0.05 approx)
    # Variance updates: 1 / var_post = 1 / var_prior + 1 / var_obs
    var_prior = prior_sigma ** 2
    var_obs = obs_sigma ** 2
    
    var_post = 1.0 / ((1.0 / var_prior) + (1.0 / var_obs))
    sigma_post = math.sqrt(var_post)
    
    # Mean update: mu_post = var_post * (mu_prior/var_prior + y/var_obs)
    mu_post = var_post * ((prior_mu / var_prior) + (observation_y / var_obs))
    
    # Bounding mu between 0.0 and 1.0
    mu_post = max(0.0, min(1.0, mu_post))
    
    return round(mu_post, 4), round(sigma_post, 4)

def select_next_questions(priors, num_questions=6):
    # Sort sub-pillars by variance (sigma desc) to reduce uncertainty,
    # or by lowest mean to query bottlenecks.
    # The specification says: "selected by information value — the sub-pillars with the highest current variance in the prior distribution are queried first."
    sorted_sp = sorted(priors.items(), key=lambda x: x[1]["sigma"], reverse=True)
    selected_sp = [sp for sp, _ in sorted_sp[:num_questions]]
    
    selected_questions = []
    for q in QUESTIONS:
        if q["sub_pillar"] in selected_sp:
            selected_questions.append(q)
    return selected_questions

def determine_strategic_mode(priors, axis_scores, p_local, p_global):
    # Mode selection logic:
    # 1. STABILIZATION: Any N sub-pillar critically low (< 0.4)
    # 2. RECOVERY: M1 or M2 critically low (< 0.4)
    # 3. PEAK: P_local >= 0.9 and P_global >= 0.85
    # 4. PROGRESSION: P_local and P_global both high (>= 0.7)
    # 5. CONSOLIDATION: Default
    
    # Check STABILIZATION
    n_subpillars = [sp for sp in priors if SUB_PILLARS[sp] == "N"]
    for sp in n_subpillars:
        if priors[sp]["mu"] < 0.4:
            return "STABILIZATION"
            
    # Check RECOVERY
    if priors.get("M1", {}).get("mu", 0.5) < 0.4 or priors.get("M2", {}).get("mu", 0.5) < 0.4:
        return "RECOVERY"
        
    # Check PEAK
    if p_local >= 0.9 and p_global >= 0.85:
        return "PEAK"
        
    # Check PROGRESSION
    if p_local >= 0.7 and p_global >= 0.7:
        return "PROGRESSION"
        
    # Default is CONSOLIDATION
    return "CONSOLIDATION"

def compute_proximity_scores(axis_scores, session_history):
    # If no sessions have been closed before, P_local is 1.0
    # P_local: how are you performing compared to your own personal best?
    # Personal best is the max score recorded for each axis in all completed sessions in history.
    if not session_history:
        p_local = 1.0
        # P_global: average of current axis scores (since this is our starting best)
        p_global = round(sum(axis_scores.values()) / len(axis_scores), 3)
        return p_local, p_global
        
    # Extract personal best for each axis
    personal_bests = {"N": 0.0, "C": 0.0, "M": 0.0, "E": 0.0, "S": 0.0}
    for session in session_history:
        snapshot = session.get("axis_scores_snapshot", {})
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except Exception:
                snapshot = {}
        for axis in personal_bests:
            personal_bests[axis] = max(personal_bests[axis], snapshot.get(axis, 0.0))
            
    # Distance to personal best
    distances = []
    for axis, curr_score in axis_scores.items():
        best = personal_bests[axis]
        # Diff is max(0, best - curr_score)
        diff = max(0.0, best - curr_score)
        distances.append(diff)
        
    avg_distance = sum(distances) / len(distances)
    p_local = round(1.0 - avg_distance, 3)
    
    # Update personal best with current scores for P_global
    for axis, curr_score in axis_scores.items():
        personal_bests[axis] = max(personal_bests[axis], curr_score)
        
    # P_global: proximity to ideal profile (where ideal is 1.0 on all axes)
    p_global = round(sum(personal_bests.values()) / len(personal_bests), 3)
    
    return p_local, p_global

def get_bottlenecks(priors):
    # Sort sub-pillars by their mean mu ascending, filter those under 0.6, limit to top 3
    sorted_sp = sorted(priors.items(), key=lambda x: x[1]["mu"])
    bottlenecks = [sp for sp, val in sorted_sp if val["mu"] < 0.65]
    if not bottlenecks:
        # If all are high, just return the lowest 2
        bottlenecks = [sp for sp, _ in sorted_sp[:2]]
    return bottlenecks[:3]
