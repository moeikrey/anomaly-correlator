---
name: synthetic-security-data
description: How to generate realistic, correlated synthetic badge-access, network-authentication, and HR roster data for GhostBadge, including injecting labeled attack scenarios. Use this skill whenever the task involves creating, extending, or debugging fake security data — badge swipes, logins, VPN sessions, employee rosters, attack injection, ground-truth labels, or data generator seeds — even if the user just says "make the data more realistic" or "add a new scenario."
---

# Synthetic Security Data Generation

The correlator is only as convincing as its data. Bad synthetic data has two failure modes: (1) it's so random that benign behavior looks anomalous everywhere, drowning detections in noise; (2) it's so clean that detections are trivial. Aim for *boring realism with labeled needles*.

## Golden rules

1. **Causality first.** In benign data, physical events cause cyber events: an employee badges IN, *then* logs into a workstation in that zone, *then* maybe badges into other zones, *then* badges OUT after their last activity. Generate each employee's day as a coherent narrative, not as independent event streams.
2. **Everything is seeded.** One master seed drives all randomness (`random.Random(seed)`, never the global RNG). Same seed + same params = byte-identical files. Tests depend on this.
3. **Ground truth or it didn't happen.** Every injected malicious event writes a row to `labels.jsonl`: `{scenario, rule_id_expected, employee_id, event_ids, day}`. Precision/recall in Phase 3 is measured against this file. Never inject without labeling.
4. **Injection = surgical edits to benign data.** Generate the fully benign world first, then apply scenario injectors that add/remove/modify specific events. This keeps scenarios composable and the benign baseline reusable.

## Benign behavior model

Per employee, sample stable "personality" traits once (seeded by employee id):
- Typical arrival time: normal(μ=dept-dependent 8:00–9:30, σ=20min)
- Departure: arrival + normal(8.5h, σ=45min)
- Lunch exit probability ~0.4 (badge OUT/IN pair around noon)
- Home zone from HR roster; occasional visits to 1–2 other permitted zones
- Login count per day: 1–3 interactive logins on hosts in occupied zones; VPN logins only on remote days (~10–20% of days, and on those days: **no badge events**)
- Weekends: ~5% chance of a legitimate short visit (this creates honest after-hours noise so GB-004 isn't trivial)

Imperfections to include deliberately (real logs are messy):
- ~1% badge reads with `result: denied` (wrong door, expired retry)
- Occasional missing badge-OUT (people tailgate out; exits are less enforced)
- Clock skew: auth event timestamps jitter ±90s relative to badge system

## Scenario injectors

Each injector is a function `inject_<scenario>(world, rng) -> list[Label]`. Implement one per detection:

| Scenario | Edit made to benign world |
|---|---|
| `ghost_login` | Pick an employee with a remote/absent day; add an interactive login on an on-site host under their account. Remove nothing. |
| `impossible_presence` | Employee badges in at HQ at time T; add VPN login from geo >2000km at T ± <45min. |
| `zone_mismatch` | Add login on a host in a zone the employee never badged into that day (badge events untouched). |
| `after_hours` | Add badge-in at 02:00 + login to a host tagged `sensitive: true` 10 min later. |
| `terminated_actor` | Mark an employee terminated N days into the window; keep generating their badge/auth events after the term date. |
| `tailgate` | One badge swipe at a zone door, followed within 30s by logins from **two different accounts** on hosts in that zone (second account has no swipe). |
| `credential_sharing` | Same account: interactive logins in zone A and zone B 5 min apart, badge trail only covers zone A. |

Injection rate: default ~1 scenario instance per 10 employee-days, configurable. `--inject all` applies every scenario at least twice so `ghostbadge score` has enough positives.

## Schemas (keep in sync with `src/ghostbadge/models.py`)

`badge_events.jsonl`:
```json
{"event_id": "b-000123", "ts": "2026-03-02T15:04:11Z", "employee_id": "E017",
 "door_id": "D-3F-EAST", "zone": "3F-ENG", "direction": "in", "result": "granted"}
```
`auth_events.jsonl`:
```json
{"event_id": "a-000456", "ts": "2026-03-02T15:11:42Z", "account": "E017",
 "host": "WS-3F-022", "host_zone": "3F-ENG", "login_type": "interactive",
 "src_ip": "10.3.22.14", "geo": null, "sensitive": false, "result": "success"}
```
VPN events: `login_type: "vpn"`, `host: "vpn-gw-1"`, `host_zone: null`, `geo: {"lat":..., "lon":..., "city":...}`.

`hr_roster.csv`: `employee_id,name,department,home_zone,permitted_zones,status,term_date`

Names come from a hardcoded fake-name list; IPs only from RFC1918 ranges; geo cities from a small fixed table with lat/lon (needed for impossible-presence distance math). Never use real people, real company hostnames, or public IPs.

## Sanity tests every generator change must keep green
- Referential integrity: every `employee_id`/`account` exists in roster
- Temporal ordering within each employee-day narrative
- Benign world contains **zero** label rows; each `--inject` scenario contributes ≥1
- Fixed seed reproduces identical SHA-256 for all output files
- Benign-only data run through the rule engine produces near-zero alerts (false-positive smoke test — a handful is OK given deliberate noise, dozens is a bug)
