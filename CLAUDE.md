# CLAUDE.md — GhostBadge (Physical-to-Cyber Anomaly Correlator)

## What this project is
A defensive security analytics tool that correlates **synthetic** physical badge-access logs with **synthetic** network authentication logs to detect anomalies (ghost logins, impossible presence, tailgating indicators). It is a portfolio project targeting security engineer / AI engineer roles. Everything here is defensive detection tooling operating on fake data — there is no offensive capability and none should be added.

## Source of truth
- `PLAN.md` — phased roadmap with acceptance criteria. **Always check which phase we're in before writing code.** Never skip ahead; never mark a phase done until its acceptance criteria pass.
- `.claude/skills/` — follow these when their domain comes up:
  - `synthetic-security-data` — any time we generate, modify, or extend fake badge/auth/HR data
  - `detection-rules` — any time we add or change a correlation rule
  - `security-docs` — README, THREAT_MODEL.md, or any security write-up

## Stack & layout
- Python 3.11+, src layout: `src/ghostbadge/`
- pydantic v2 for models, SQLAlchemy + SQLite for storage, Typer for CLI, Streamlit for dashboard, scikit-learn for the ML layer
- Tests in `tests/`, mirroring `src/ghostbadge/` structure
- Data outputs to `data/` (gitignored except small committed fixtures in `tests/fixtures/`)

## Commands
```bash
pip install -e ".[dev]"        # setup
pytest                          # run tests (must pass before any commit)
pytest tests/rules/ -k GB_001   # run tests for one rule
ruff check . && ruff format .   # lint + format (must be clean before commit)
ghostbadge generate --employees 50 --days 30 --seed 42 --inject all
ghostbadge ingest ./data/
ghostbadge run
ghostbadge score                # precision/recall vs ground-truth labels
ghostbadge report --format md
streamlit run src/ghostbadge/dashboard/app.py
```

## Conventions
- **Type hints everywhere.** Pydantic models for anything crossing a module boundary.
- **All timestamps UTC**, timezone-aware `datetime`. Convert at ingestion, never later.
- **Determinism:** anything random takes a `seed` parameter. Same seed → identical output. Tests rely on this.
- **Evidence chains are sacred:** every `Alert` must reference the exact source events that triggered it. An alert without evidence is a bug.
- **Rules are pure:** `evaluate()` reads events and returns alerts. No I/O, no global state inside rules.
- Docstrings explain the *security rationale* ("why an attacker would look like this"), not just mechanics.
- Small commits, one logical change each, message format: `phase-N: <what>` (e.g., `phase-3: add GB-002 impossible presence rule`).

## Workflow with the human
1. At the start of a session, state the current phase and what remains for its acceptance criteria.
2. Propose the next concrete step before writing code; keep steps small (reviewable in one sitting).
3. Write the test alongside (or before) the implementation — especially for rules, which have a mandated test trio (fires / stays silent / edge case) per the detection-rules skill.
4. After completing a step: run `pytest` and `ruff check`, show results, then stop for review. Don't chain multiple features without a checkpoint.
5. If an acceptance criterion seems wrong or unachievable, say so and propose an amendment to PLAN.md — don't silently deviate.

## Hard boundaries
- Never generate or ingest real personal data, real employee names tied to real companies, or real IP/geo data of identifiable people. Synthetic only, and the README must say so.
- No offensive tooling: no exploit code, no credential harvesting, no scanning of real networks. This project detects; it does not attack.
- Don't add dependencies without stating why; prefer stdlib where reasonable.
- Don't rewrite working modules wholesale when a targeted edit will do.

## North star
Every decision should serve the portfolio goal: a recruiter or hiring manager should be able to clone this, run three commands, see alerts with readable evidence, and think "this person understands both physical and network security." Clarity and demo-ability beat cleverness.
