---
name: security-docs
description: How to write GhostBadge's portfolio-facing documentation — the README, THREAT_MODEL.md, architecture diagram, demo assets, and detection write-ups. Use this skill whenever the task touches documentation, the README, diagrams, the threat model, release notes, or "making the repo look good for recruiters," even if the user just says "polish it up" or "write up what we built."
---

# Security Documentation & Portfolio Polish

The audience is a recruiter or hiring manager giving the repo 90 seconds, and an engineer giving it 10 minutes. Write for the 90-second reader first; layer depth beneath.

## README structure (in this order)

1. **One-sentence pitch + demo GIF** at the very top. The GIF shows: run pipeline → alert feed → click alert → evidence chain. Record with `vhs` or a screen recorder; keep under 15 seconds.
2. **"Why I built this"** — 3–4 sentences, first person, grounded in the author's real background: worked physical security at Pinterest HQ, studied networking (CCNA) — noticed badge systems and SIEMs never talk to each other. This paragraph is the differentiator; keep it specific and human, no buzzwords.
3. **Quickstart** — 3 commands max (`pip install -e .` → `ghostbadge demo` → open dashboard). If it takes more, add a `demo` command that wraps generate+ingest+run.
4. **Detection table** — copy from PLAN.md (ID, name, what it catches, severity, MITRE technique).
5. **Results** — precision/recall table from `ghostbadge score` on the standard seed. Honest numbers beat perfect numbers; if GB-006 has 0.7 precision, show it and explain why tailgate inference is hard.
6. **Architecture diagram** — one Mermaid diagram in the README (renders on GitHub natively; no image files to maintain).
7. **What I'd build next** — 3 bullets (real SIEM integration via Wazuh/Splunk connectors, streaming instead of batch, UEBA baselining). Shows judgment about scope.
8. **Synthetic-data disclaimer** — explicit statement that all data is generated, no real people/companies/IPs.

Tone: confident, concrete, zero filler. Ban the phrases "cutting-edge," "state-of-the-art," "robust and scalable." Prefer "detects X by joining Y with Z."

## THREAT_MODEL.md

Use a lightweight STRIDE-flavored structure, ~1–2 pages:

1. **System & assets** — what the tool protects conceptually (facility + corp network), and what the tool itself must protect (log integrity, alert pipeline).
2. **Trust boundaries** — badge system → ingestion, auth logs → ingestion, DB → dashboard. One Mermaid diagram with boundaries drawn.
3. **Threats considered** — table: threat, affected detection(s), residual risk. Include threats *against the correlator itself* (log tampering/deletion = T1070, feeding it spoofed events) — acknowledging your tool's own attack surface reads as senior.
4. **Evasion analysis** — pull the "evasion" lines from each rule's docstring into one honest section: what a sophisticated attacker does to walk past GhostBadge, and which evasions are out of scope.
5. **Assumptions** — clock sync within N minutes, badge coverage of all entrances, 1:1 employee↔account mapping.

## Diagrams

- Mermaid only, committed as code in the markdown. Flow direction left→right for pipelines, top→down for trust boundaries.
- Label edges with data formats (`jsonl`, `SQLite`), not vague arrows.
- One diagram per concern; never one mega-diagram.

## Per-detection write-ups (docs/detections/GB-00X.md, optional but high-value)

For each rule, a short page: attacker story → how the correlation works (with a tiny event-sequence example) → FP story and suppression → evasion. Source these directly from rule docstrings so docs and code can't drift; if they disagree, the docstring wins and the doc gets fixed.

## Release hygiene

- Tag releases (v1.0.0 at end of Phase 7); CHANGELOG.md with human-readable entries per phase.
- Repo description + topics set: `security`, `detection-engineering`, `siem`, `insider-threat`, `python`.
- LICENSE (MIT) and a `.github/workflows/ci.yml` badge at the top of the README — a green badge is recruiter-visible proof of working CI.
