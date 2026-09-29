-- Run as WEBUI_MCP. Read-only verification.
SELECT SYS_CONTEXT('USERENV', 'SESSION_USER') AS connected_user FROM dual;

-- Expected: 12 rows, 870000 EUR budget, 483000 EUR spent.
SELECT COUNT(*) AS project_count,
       SUM(budget_eur) AS total_budget_eur,
       SUM(spent_eur) AS total_spent_eur
FROM demo_projects;

-- Expected: PLANIRAN 2, U_TIJEKU 5, PAUZIRAN 2, ZAVRSEN 3.
SELECT status, COUNT(*) AS project_count
FROM demo_projects GROUP BY status ORDER BY status;

SELECT project_code, project_name, status, budget_eur, spent_eur, progress_pct
FROM demo_projects ORDER BY project_code;

-- Single-project lookup for a future parameterized MCP tool.
SELECT * FROM demo_projects WHERE project_code = 'ORION-742';

-- Expected: COMET-905 (2000 EUR), PULSAR-630 (6000 EUR).
SELECT project_code, spent_eur - budget_eur AS overspend_eur
FROM demo_projects WHERE spent_eur > budget_eur ORDER BY project_code;

-- Fixed demo reference date, not today's date: expected VEGA-208 and PULSAR-630.
SELECT project_code, status, target_end_date
FROM demo_projects
WHERE status <> 'ZAVRSEN' AND target_end_date < DATE '2026-09-24'
ORDER BY target_end_date;
