# Exact router integration text for Task A

The owner of `rai-orm` should replace its Step 5 paragraph with this text:

> Run `report.py` from this skill's `tools/` with `--model model.orm.yaml`, adding `--verification model.verification.json`, `--connectivity connectivity.json` and `--digest workload.digest.yaml` when available. Show `orm-report.md` as the route summary. When its first line is `BUDGET_EXHAUSTED`, lead with that line verbatim: give the residual count and the exact step to continue, and keep the route incomplete. Otherwise state the report's statistics and issues, including connectivity and unverified items. Load `references/connectivity.md` to review islands or required joins, and `references/statistics-and-issues.md` to interpret the report.

Add these rows to a Reference files table:

| File | When to load |
|---|---|
| [Connectivity](connectivity.md) | Before hand-off or when the report finds islands or required join gaps |
| [Statistics and issues](statistics-and-issues.md) | At route close, especially on budget exhaustion |

The rows above are shown relative to this integration note. In the router, use `references/connectivity.md` and `references/statistics-and-issues.md` as link targets. No changes to the router's `SKILL.md` are part of Task A.
