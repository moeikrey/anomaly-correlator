# GhostBadge — Physical-to-Cyber Anomaly Correlator

**Elevator pitch:** A security analytics engine that correlates physical access logs (badge swipes) with network authentication logs (workstation logins, VPN sessions) to detect anomalies neither log source can reveal alone — e.g., a login from an on-site workstation belonging to someone whose badge never entered the building.

**Why this project exists (personal hook for README):** Built by someone who worked physical security at Pinterest HQ (Allied Universal) and studied networking/security (CCNA, RedHat training). The physical and cyber sides of security rarely talk to each other — this project makes them.

---

## Core Detections (the product's soul)

| ID | Name | Signal | Severity |
|----|------|--------|----------|
| GB-001 | Ghost Login | Interactive login on an on-site workstation, but the account owner has **no badge-in** that day | High |
| GB-002 | Impossible Presence | Badge-in at HQ and a VPN login from a distant geo within a window too short to travel | High |
| GB-003 | Zone Mismatch | Workstation login in a physical zone the user never badged into | Medium |
| GB-004 | After-Hours Pairing | Badge-in outside business hours followed by access to a sensitive system | Medium |
| GB-005 | Terminated Actor | Badge or account activity from a user marked terminated in HR data | Critical |
| GB-006 | Tailgate Indicator | Two logins in the same zone within N seconds of a single badge swipe at that zone's door | Low/Medium |
| GB-007 | Credential Sharing | Same account logging in from two zones with no badge movement between them | Medium |

Each detection maps to a MITRE ATT&CK technique in its rule metadata (e.g., GB-001 → T1078 Valid Accounts).

---

## Architecture

```
[Synthetic Data Generator] ──> badge_events.jsonl, auth_events.jsonl, hr_roster.csv
        │
        v
[Ingestion & Normalization]  (pydantic models → SQLite via SQLAlchemy)
        │
        v
[Correlation Engine]  (rule registry; each rule = pure function over event windows)
        │
        v
[Alert Store + Scoring]  (severity, confidence, evidence chain)
        │
        ├──> [CLI]        `ghostbadge run`, `ghostbadge report`
        └──> [Dashboard]  Streamlit: per-employee timeline, alert feed, zone map
        
[ML Layer (stretch)]  IsolationForest over behavioral features; flags outliers rules miss
```

**Stack:** Python 3.11+, pydantic v2, SQLAlchemy + SQLite, Typer (CLI), Streamlit (dashboard), scikit-learn (ML stretch), pytest, ruff, GitHub Actions CI, Docker.

---

## Phases

Work strictly in order. Do not start a phase until the previous phase's acceptance criteria pass.

### Phase 0 — Repo & Tooling (½ day)
- `pyproject.toml` with pinned deps; `src/ghostbadge/` package layout
- ruff + pytest configured; GitHub Actions workflow running both on push
- Pre-commit hook for ruff
- **Done when:** CI is green on an empty-but-importable package with one trivial test.

### Phase 1 — Synthetic Data Generator (1–2 days)
- `ghostbadge generate --employees 50 --days 30 --seed 42` produces:
  - `hr_roster.csv` (employee id, name, dept, zone assignments, status, term date)
  - `badge_events.jsonl` (swipe events: employee, door, zone, direction, ts, result)
  - `auth_events.jsonl` (logins: account, host, zone-of-host, src ip, geo, type: local/vpn, result)
- Realistic *benign* behavior: arrival-time distributions, lunch exits, badge-in must precede local logins
- Injectable *attack scenarios* via `--inject ghost_login,impossible_presence,...` with a ground-truth labels file for later precision/recall measurement
- Follow the **synthetic-security-data** skill.
- **Done when:** generated data passes sanity tests (referential integrity, temporal ordering, ≥1 label per injected scenario) and a fixed seed reproduces byte-identical output.

### Phase 2 — Ingestion & Storage (1 day)
- Pydantic models: `BadgeEvent`, `AuthEvent`, `Employee`
- Loader: validates, normalizes timestamps to UTC, writes to SQLite
- Reject-and-log malformed rows (don't crash)
- **Done when:** `ghostbadge ingest ./data/` loads a generated dataset; row counts match; malformed-row fixture is skipped with a warning.

### Phase 3 — Correlation Engine (2–3 days, the heart)
- Rule registry: each rule is a class with `id`, `name`, `severity`, `mitre_technique`, and `evaluate(window) -> list[Alert]`
- Implement GB-001 through GB-005 first; GB-006/007 after
- Every alert carries an **evidence chain** (the exact events that triggered it)
- Follow the **detection-rules** skill for structure, naming, and test requirements.
- **Done when:** running against injected data, every rule achieves ≥0.9 recall and ≥0.9 precision against ground-truth labels (measured by `ghostbadge score`), and each rule has unit tests for: fires-when-it-should, silent-when-it-shouldn't, and one edge case.

### Phase 4 — Alerting, Scoring & CLI (1 day)
- Composite risk score per employee per day (weighted by severity + rule confidence)
- `ghostbadge run` (full pipeline), `ghostbadge report --format md|json` (top alerts w/ evidence)
- **Done when:** end-to-end run on fresh generated data produces a readable markdown report an analyst could act on.

### Phase 5 — Dashboard (1–2 days)
- Streamlit app: alert feed (filter by severity/rule), per-employee timeline showing badge + auth events interleaved with alerts flagged inline, simple zone occupancy view
- **Done when:** a stranger can open the dashboard, click one alert, and understand *why* it fired from the evidence view alone.

### Phase 6 — ML Anomaly Layer (stretch, 2 days)
- Feature extraction per employee-day (arrival deviation, login count, zone entropy, off-hours ratio)
- IsolationForest flags outliers; surfaced as "ML anomalies" distinct from rule alerts
- Honest evaluation section in README: what ML caught that rules missed, and vice versa
- **Done when:** at least one injected scenario variant is caught by ML but not rules, and this is documented.

### Phase 7 — Polish & Presentation (1 day, non-negotiable)
- README with: architecture diagram, demo GIF, "why I built this" paragraph, quickstart (`docker compose up` or 3 commands max), detection table, precision/recall results
- `THREAT_MODEL.md` per the **security-docs** skill
- Tag v1.0.0.
- **Done when:** a recruiter with 90 seconds can understand the project from the README alone.

---

## Definition of Done (global)
- All tests pass, ruff clean, CI green
- No secrets, no real personal data anywhere — all data is synthetic and clearly labeled as such
- Every rule and module has a docstring explaining the *security rationale*, not just the code
