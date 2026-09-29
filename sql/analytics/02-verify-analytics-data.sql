-- Run as WEBUI_MCP after 01 succeeds. READ ONLY, no LLM calls.
SET SERVEROUTPUT ON
DECLARE
  l_value NUMBER;
  PROCEDURE expect(p_label VARCHAR2, p_value NUMBER, p_expected NUMBER) AS
  BEGIN
    IF p_value IS NULL OR p_value <> p_expected THEN
      RAISE_APPLICATION_ERROR(-20110, p_label||': unexpected result; expected '||p_expected);
    END IF;
    DBMS_OUTPUT.PUT_LINE('OK: '||p_label||' = '||p_value);
  END;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'WEBUI_MCP'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'WEBUI_MCP' THEN
    RAISE_APPLICATION_ERROR(-20111,'Run as WEBUI_MCP with current schema WEBUI_MCP.');
  END IF;
  SELECT COUNT(*) INTO l_value FROM demo_a_departments;
  expect('departments',l_value,4);
  SELECT COUNT(*) INTO l_value FROM demo_a_employees;
  expect('employees',l_value,24);
  SELECT COUNT(*) INTO l_value FROM demo_a_projects;
  expect('projects',l_value,36);
  SELECT COUNT(*) INTO l_value FROM demo_a_costs;
  expect('cost entries',l_value,192);
  SELECT COUNT(*) INTO l_value FROM demo_a_leave_days;
  expect('absence-day records',l_value,354);
  SELECT COUNT(*) INTO l_value FROM demo_a_projects
  WHERE start_date >= DATE '2025-01-01' AND start_date < DATE '2026-01-01';
  expect('projects started 2025',l_value,18);
  SELECT COUNT(*) INTO l_value FROM demo_a_projects
  WHERE start_date >= DATE '2026-01-01' AND start_date < DATE '2027-01-01';
  expect('projects started 2026',l_value,18);
  SELECT COUNT(*) INTO l_value FROM demo_a_projects
  WHERE start_date < DATE '2027-01-01'
    AND (actual_end_date IS NULL OR actual_end_date >= DATE '2026-01-01');
  expect('projects active at some point in 2026',l_value,22);
  SELECT SUM(amount_eur) INTO l_value FROM demo_a_costs;
  expect('total actual spending EUR',l_value,473699);
  SELECT SUM(amount_eur) INTO l_value FROM demo_a_costs
  WHERE cost_date >= DATE '2025-01-01' AND cost_date < DATE '2026-01-01';
  expect('actual spending in 2025 EUR',l_value,185523);
  SELECT SUM(amount_eur) INTO l_value FROM demo_a_costs
  WHERE cost_date >= DATE '2026-01-01' AND cost_date < DATE '2027-01-01';
  expect('actual spending in 2026 through snapshot EUR',l_value,288176);
  SELECT SUM(budget_eur) INTO l_value FROM demo_a_projects;
  expect('approved total budget EUR',l_value,1095500);
  SELECT COUNT(DISTINCT employee_id) INTO l_value FROM demo_a_leave_days
  WHERE leave_type='GODISNJI' AND leave_status='ISKORISTEN'
    AND leave_date >= DATE '2025-01-01' AND leave_date < DATE '2026-01-01';
  expect('employees who took annual leave in 2025',l_value,20);
  SELECT SUM(day_fraction) INTO l_value FROM demo_a_leave_days
  WHERE leave_type='GODISNJI' AND leave_status='ISKORISTEN'
    AND leave_date >= DATE '2025-01-01' AND leave_date < DATE '2026-01-01';
  expect('annual leave days actually taken in 2025',l_value,100);
  SELECT COUNT(DISTINCT employee_id) INTO l_value FROM demo_a_leave_days
  WHERE leave_type='GODISNJI' AND leave_status='ISKORISTEN'
    AND leave_date >= DATE '2026-01-01' AND leave_date < DATE '2027-01-01';
  expect('employees who took annual leave in 2026',l_value,22);
  SELECT COUNT(*) INTO l_value FROM demo_a_costs WHERE cost_date > DATE '2026-09-24';
  expect('future actual costs',l_value,0);
  SELECT COUNT(*) INTO l_value FROM demo_a_leave_days
  WHERE leave_status='ISKORISTEN' AND leave_date > DATE '2026-09-24';
  expect('future taken leave',l_value,0);
  DBMS_OUTPUT.PUT_LINE('SUCCESS: all analytics demo dataset checks passed.');
END;
/

-- Reference query: costs by calendar year (not project start year).
SELECT EXTRACT(YEAR FROM cost_date) AS calendar_year, SUM(amount_eur) AS cost_eur
FROM demo_a_costs GROUP BY EXTRACT(YEAR FROM cost_date) ORDER BY calendar_year;

-- Reference query: preaggregate cost rows before joining to project budgets.
SELECT p.project_code, p.budget_eur, c.spent_eur,
       c.spent_eur-p.budget_eur AS overspend_eur
FROM demo_a_projects p
JOIN (SELECT project_id,SUM(amount_eur) AS spent_eur
      FROM demo_a_costs GROUP BY project_id) c ON c.project_id=p.project_id
WHERE c.spent_eur>p.budget_eur ORDER BY p.project_code;

-- Reference query: includes employees with zero taken annual-leave days in 2025.
SELECT d.department_name, COUNT(DISTINCT e.employee_id) AS all_employees,
       COUNT(DISTINCT l.employee_id) AS employees_with_annual_leave,
       NVL(SUM(l.day_fraction),0) AS days_taken
FROM demo_a_employees e
JOIN demo_a_departments d ON d.department_id=e.department_id
LEFT JOIN demo_a_leave_days l ON l.employee_id=e.employee_id
  AND l.leave_type='GODISNJI' AND l.leave_status='ISKORISTEN'
  AND l.leave_date>=DATE '2025-01-01' AND l.leave_date<DATE '2026-01-01'
GROUP BY d.department_name ORDER BY d.department_name;
