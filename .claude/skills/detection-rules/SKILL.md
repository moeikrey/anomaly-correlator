---
name: detection-rules
description: How to design, implement, and test correlation/detection rules in GhostBadge — rule class structure, severity and MITRE ATT&CK mapping, evidence chains, tuning thresholds, and the mandatory test trio. Use this skill whenever adding a new detection, modifying rule logic or thresholds, fixing false positives/negatives, or wiring rules into the registry — even if the user phrases it as "the correlator is missing X" or "too many alerts."
---

# Writing Detection Rules

A rule is a falsifiable claim about attacker behavior expressed as code. Every rule must answer three questions in its docstring: **What attacker behavior does this catch? What benign behavior could look identical (false-positive story)? What could an attacker do to evade it?** If you can't answer all three, the rule isn't ready.

## Rule anatomy

```python
@register_rule
class GhostLogin(Rule):
    """GB-001: Interactive login on-site with no badge-in that day.

    Attacker story: stolen/shared credentials used at a workstation while
    the real owner is absent. Maps to T1078 (Valid Accounts).
    FP story: badge reader outage; employee entered via a door with a
    broken reader. Mitigation: suppress if >5% of workforce has no swipes
    that day (systemic outage heuristic).
    Evasion: attacker also steals the badge (then GB-003/GB-007 may fire).
    """
    id = "GB-001"
    name = "Ghost Login"
    severity = Severity.HIGH
    mitre_technique = "T1078"
    default_params = {"outage_threshold": 0.05}

    def evaluate(self, window: DayWindow) -> list[Alert]:
        ...
```

Requirements:
- **Pure function discipline:** `evaluate()` takes a `DayWindow` (all events + roster for one calendar day, pre-indexed by employee), returns alerts. No DB access, no I/O, no mutation of the window, no reading the clock.
- **Parameterized thresholds** live in `default_params`, overridable from config — never hardcode magic numbers in logic. Tuning FPs must not require code edits.
- **Evidence chain:** every alert lists the `event_id`s that justify it, plus a one-line human explanation template, e.g. `"E017 logged into WS-3F-022 at 15:11 UTC but has no badge entry on 2026-03-02"`. The dashboard renders this verbatim; an analyst must be able to verify the alert from evidence alone.
- **Confidence** (0–1) is separate from severity. Severity = impact if true; confidence = how sure the rule is. GB-006 tailgate inference is inherently low-confidence; say so.

## Correlation guidance

- Join key between worlds is `employee_id == account`. The roster is the bridge — always resolve through it (handles terminated status, permitted zones).
- Time windows: compare with explicit tolerances (`abs(dt) <= timedelta(...)`), remembering the generator injects ±90s clock skew. Any rule comparing badge vs auth timestamps must tolerate ≥2 min skew or it will both miss injections and page on noise.
- Impossible presence math: haversine distance / elapsed time > 900 km/h ⇒ impossible. Put haversine in `ghostbadge/geo.py`, shared, unit-tested separately.
- Absence of evidence is a signal here (no badge-in *is* the anomaly), so rules must distinguish "no events for employee" from "employee not in roster" — the latter is a data-quality warning, not an alert.

## The mandatory test trio

Every rule ships with at least three tests in `tests/rules/test_<rule_id>.py`, built from small hand-crafted fixtures (not full generator runs):

1. **Fires when it should** — minimal event set that triggers exactly one alert; assert the evidence chain contains the right event_ids.
2. **Stays silent when it shouldn't** — the nearest benign look-alike (for GB-001: employee badged in via a different door earlier that day; for GB-002: VPN geo 30 km away).
3. **Edge case** — midnight boundary, clock-skew boundary, terminated-but-rehired, duplicate events, etc. Pick the one most likely to bite.

Plus, after any rule change, run the integration check: `ghostbadge generate --seed 42 --inject all && ghostbadge run && ghostbadge score`. A rule change that drops any rule's precision or recall below 0.9 on the standard seed doesn't merge — either fix the rule or (if the ground truth is wrong) fix the injector and say so explicitly.

## Tuning workflow (false positives / false negatives)

1. Reproduce with a fixed seed; identify the offending alert(s) and their evidence.
2. Classify: is it a **threshold** problem (adjust params), a **missing suppression** (add documented heuristic like the outage check), or a **generator realism** problem (fix in synthetic-security-data skill territory)?
3. Never fix an FP by deleting the assertion or widening a threshold blindly — every tuning change gets a comment citing the scenario that motivated it.
4. Update the rule's FP story docstring if the mitigation changed.

## Adding a brand-new detection (beyond GB-001..007)

1. Write the attacker story / FP story / evasion trio first, in the PR description.
2. Reserve the next GB-ID in PLAN.md's detection table with severity + MITRE mapping.
3. Add a matching injector + labels in the data generator (a rule without injectable ground truth can't be scored and doesn't merge).
4. Implement rule + test trio, then run the integration check.
