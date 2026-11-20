# judge

Grades predicted funding rounds against ground truth.

- `config.yaml` — Exact matching rules (stage equivalences, ±5% on amount, ±7 days on date) and leaderboard scoring.
- `grader.py` — Decides pass or fail for each field and computes 95% confidence intervals.
- `stage_aliases.json` — Lookup table mapping funding stage names (for example, `Seed Bridge` and `Pre-Series A` to `seed_group`).
