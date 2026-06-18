# KnowMe — Knowledge Base + Cognitive Diagnostics System

> *A tool that makes a student’s own knowledge visible, then helps them think — not just memorize.*

---

## 1. What is this project?

Most EdTech tools push content *into* the student.  
We do the opposite: **pull the student’s own knowledge out**, structure it, and let them work with it.

Two core systems:

- **Knowledge Base (KB)** – a personal, typed knowledge graph built from the student’s own words.
- **Cognitive Diagnostics System (CDS)** – a model that recommends *how* to study based on sleep, fatigue, and cognitive state.

We are building this for the **ICT for Africa Tech Innovation Challenge 2026** (July/August).

---

## 2. The problem we solve

> Students study blind. They cannot see the difference between what they truly understand and what they have only memorized.

- 72% of enrolled students in Cameroon cannot read an age‑appropriate text.
- Classrooms often have 50–100 students per teacher → personalized guidance is impossible.
- No existing tool helps a student understand *how their own mind learns*.

---

## 3. What makes us different

| Other EdTech | We do this |
|--------------|-------------|
| Push content in | Pull knowledge out |
| Teach *what* to study | Develop *how* to think |
| AI knows everything | AI knows only what the student wrote |
| Needs constant internet | Works offline (core KB) |

---

## 4. Repository Architecture (New)

This repository is organized by domain and responsibility to support the 8-week sprint:

```text
/
├── assets/                 # Branding, media, and demo insurance
├── docs/                   # The "War Room" - Strategic & Architectural core
│   ├── architecture/       # Technical deep-dives (CDS 8-axis, KB Graph)
│   ├── strategy/           # Competition positioning, SWOT, business model
│   └── team/               # Collaboration agreements, roles, IP docs
├── experiments/            # Vision-level prototypes (non-demo features)
├── pitch/                  # The "Performance" layer (scripts, Q&A, slides)
├── src/                    # The "Engine" (Logic & Backend)
│   ├── ai/                 # AI Mirror & RAG logic (student-only context)
│   ├── cds/                # Cognitive Diagnostics (state calculation)
│   └── kb/                 # Knowledge Base (parsing, mastery, graph logic)
├── survey/                 # Research & Market Validation (data & analysis)
├── tests/                  # Verification & Validation
├── web/                    # The "Interface" (Visual layer & Graph Viz)
├── scripts/                # Automation (setup, data processing)
└── README.md               # Project Entry Point
```

---

## 5. What we build for the competition (the demo)

One complete, working flow – **four steps**:

1. **CDS entry** → two questions (sleep + fatigue) → session mode recommendation.
2. **KB note creation** → student types understanding → system creates structured knowledge note.
3. **AI mirror** → AI responds using *only the student’s own words*.
4. **Graph** → two connected knowledge nodes appear visually.

> The full 8‑axis CDS and complete knowledge graph are explained as **vision**, not fully built in the demo.

---

## 6. Team & roles

| Role | Lead | Responsibility |
|------|------|----------------|
| Architecture & Research | Tuendom Yves | Project vision, KB/CDS design, survey, pitch script, Q&A prep |
| Prototype Development | SONGUE Seth | Build demo (CDS entry, KB note, AI mirror, graph) |
| Pitch & Presentation | Nguendjob Gadyel | Delivery, rehearsals, live demo operation |

**All three contribute to every domain** – no passive members.

---

## 7. 8‑week execution calendar (simplified)

| Week | Focus | Deliverable |
|------|-------|--------------|
| 1 | Survey + architecture | Survey live (96 students), schema locked |
| 2 | CDS prototype | Sleep + fatigue → session mode |
| 3 | KB note creation | Typed input → structured knowledge note |
| 4 | AI mirror | Full KB interaction end‑to‑end |
| 5 | Graph + pitch script | Nodes visible; script complete |
| 6 | Full demo flow | 4‑step demo stable + backup recording |
| 7 | Rehearsals + research | Pitch memorized; 3 key survey stats ready |
| 8 | Buffer | Fix breakages; no new features |

---

## 8. What we walk in with

- Working demo (tested on presentation device)
- Backup recording of the demo
- Survey results from 96 students → 3 key statistics
- Rehearsed pitch (no notes)
- Answers to the three guaranteed judge questions:
  1. How does this work without internet?
  2. Who pays for it?
  3. How do we measure learning improvement?

---

## 9. Beyond the competition

This is not a one‑off. The same project is aligned for:

- **Cameroon ICT Innovation Week** (national competition, >70M FCFA prize pool)
- **UNESCO King Hamad Prize for ICT in Education** ($25,000, 2026 theme on AI + critical thinking)
- **World Bank / African Union EdTech pilot funding**

---

## 10. Collaboration rules (short version)

- Domain lead is **accountable** for their deliverable.
- Blockers communicated **same day**.
- No feature creep without Yves’ approval.
- Pitch is split across all three members – we present as a real team.

Full team agreement (IP, prize split, origin of project) is signed separately.

---

**Three Minds One Goal!**

SYNK
