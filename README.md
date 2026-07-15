# GhostBadge — Physical-to-Cyber Anomaly Correlator

Correlates physical badge-access logs with network authentication logs to
detect anomalies neither log source can reveal alone — e.g., a login on an
on-site workstation belonging to someone whose badge never entered the
building.

> **All data in this project is synthetic.** The generator produces fake
> employees, fake badge swipes, and fake authentication events. No real
> personal data, real credentials, or real network information is used or
> ingested anywhere. This is defensive detection tooling only.

🚧 Under construction — see [PLAN.md](PLAN.md) for the roadmap. The full
README (quickstart, detection table, architecture, results) lands in Phase 7.

## Development

```bash
pip install -e ".[dev]"
pre-commit install
pytest
ruff check . && ruff format .
```
