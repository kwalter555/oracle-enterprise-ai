-- Run ENTIRE file as WEBUI_MCP in a fresh SQL Developer worksheet: F5.
-- Independent analytics demo. Does not modify DEMO_PROJECTS or existing tools.
-- Creates five NEW DEMO_A_* tables. All people/customers/amounts are fictional.
-- Fixed reporting date: 2026-09-24. No LLM calls, no credentials in this file.
SET SERVEROUTPUT ON
DECLARE
  l_count PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'WEBUI_MCP'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'WEBUI_MCP' THEN
    RAISE_APPLICATION_ERROR(-20101,'Run as WEBUI_MCP with current schema WEBUI_MCP.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM user_objects WHERE object_name IN
    ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS',
     'DEMO_A_COSTS','DEMO_A_LEAVE_DAYS');
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20102,'Some DEMO_A_* objects already exist. Nothing overwritten. Stop and inspect.');
  END IF;

  EXECUTE IMMEDIATE q'~CREATE TABLE demo_a_departments (
    department_id NUMBER(4) CONSTRAINT da_dept_pk PRIMARY KEY,
    department_name VARCHAR2(80 CHAR) NOT NULL CONSTRAINT da_dept_name_uq UNIQUE
  )~';
  EXECUTE IMMEDIATE q'~CREATE TABLE demo_a_employees (
    employee_id NUMBER(6) CONSTRAINT da_emp_pk PRIMARY KEY,
    employee_name VARCHAR2(80 CHAR) NOT NULL,
    department_id NUMBER(4) NOT NULL CONSTRAINT da_emp_dept_fk REFERENCES demo_a_departments(department_id),
    hired_on DATE NOT NULL
  )~';
  EXECUTE IMMEDIATE q'~CREATE TABLE demo_a_projects (
    project_id NUMBER(6) CONSTRAINT da_proj_pk PRIMARY KEY,
    project_code VARCHAR2(32 CHAR) NOT NULL CONSTRAINT da_proj_code_uq UNIQUE,
    project_name VARCHAR2(120 CHAR) NOT NULL,
    customer_name VARCHAR2(80 CHAR) NOT NULL,
    department_id NUMBER(4) NOT NULL CONSTRAINT da_proj_dept_fk REFERENCES demo_a_departments(department_id),
    manager_id NUMBER(6) NOT NULL CONSTRAINT da_proj_mgr_fk REFERENCES demo_a_employees(employee_id),
    start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    actual_end_date DATE,
    project_status VARCHAR2(20 CHAR) NOT NULL,
    budget_eur NUMBER(12,2) NOT NULL,
    CONSTRAINT da_proj_status_ck CHECK (project_status IN ('U_TIJEKU','PAUZIRAN','ZAVRSEN')),
    CONSTRAINT da_proj_dates_ck CHECK (planned_end_date >= start_date AND (actual_end_date IS NULL OR actual_end_date >= start_date)),
    CONSTRAINT da_proj_end_ck CHECK ((project_status = 'ZAVRSEN' AND actual_end_date IS NOT NULL) OR (project_status <> 'ZAVRSEN' AND actual_end_date IS NULL)),
    CONSTRAINT da_proj_budget_ck CHECK (budget_eur >= 0)
  )~';
  EXECUTE IMMEDIATE q'~CREATE TABLE demo_a_costs (
    cost_id NUMBER(8) CONSTRAINT da_cost_pk PRIMARY KEY,
    project_id NUMBER(6) NOT NULL CONSTRAINT da_cost_proj_fk REFERENCES demo_a_projects(project_id),
    cost_date DATE NOT NULL,
    cost_category VARCHAR2(30 CHAR) NOT NULL,
    amount_eur NUMBER(12,2) NOT NULL,
    CONSTRAINT da_cost_amount_ck CHECK (amount_eur > 0),
    CONSTRAINT da_cost_category_ck CHECK (cost_category IN ('RAD','CLOUD','LICENCE','VANJSKE_USLUGE'))
  )~';
  EXECUTE IMMEDIATE q'~CREATE TABLE demo_a_leave_days (
    leave_day_id NUMBER(8) CONSTRAINT da_leave_pk PRIMARY KEY,
    employee_id NUMBER(6) NOT NULL CONSTRAINT da_leave_emp_fk REFERENCES demo_a_employees(employee_id),
    leave_date DATE NOT NULL,
    leave_type VARCHAR2(20 CHAR) NOT NULL,
    leave_status VARCHAR2(20 CHAR) NOT NULL,
    day_fraction NUMBER(3,2) NOT NULL,
    CONSTRAINT da_leave_uq UNIQUE (employee_id,leave_date),
    CONSTRAINT da_leave_type_ck CHECK (leave_type IN ('GODISNJI','EDUKACIJA')),
    CONSTRAINT da_leave_status_ck CHECK (leave_status IN ('ISKORISTEN','ODOBREN','OTKAZAN')),
    CONSTRAINT da_leave_fraction_ck CHECK (day_fraction > 0 AND day_fraction <= 1)
  )~';

  -- Compiled after the tables exist. Fixed source only; no user-generated SQL.
  EXECUTE IMMEDIATE q'~
DECLARE
  c_as_of CONSTANT DATE := DATE '2026-09-24';
  l_start DATE;
  l_end DATE;
  l_actual DATE;
  l_status VARCHAR2(20);
  l_category VARCHAR2(30);
  l_budget NUMBER;
  l_year NUMBER;
  l_local NUMBER;
  l_manager NUMBER;
  l_cost_id NUMBER := 0;
  l_leave_id NUMBER := 0;
  l_base DATE;
  l_cancel DATE;
  l_education DATE;
  l_used_employees NUMBER;
BEGIN
  INSERT INTO demo_a_departments VALUES (1,'Razvoj');
  INSERT INTO demo_a_departments VALUES (2,'Operacije');
  INSERT INTO demo_a_departments VALUES (3,'Analitika');
  INSERT INTO demo_a_departments VALUES (4,'Korisnicka podrska');
  FOR e IN 1..24 LOOP
    INSERT INTO demo_a_employees VALUES
      (e,'Demo zaposlenik ' || TO_CHAR(e,'FM00'),MOD(e-1,4)+1,
       ADD_MONTHS(DATE '2024-01-01',MOD(e-1,12))+7);
  END LOOP;

  FOR p IN 1..36 LOOP
    IF p <= 18 THEN l_year := 2025; l_local := p;
    ELSE l_year := 2026; l_local := p-18; END IF;
    IF l_year = 2025 THEN l_start := DATE '2025-01-01';
    ELSE l_start := DATE '2026-01-01'; END IF;
    l_start := ADD_MONTHS(l_start,MOD(l_local-1,9))+4+10*TRUNC((l_local-1)/9);
    l_end := l_start+150;
    l_actual := NULL;
    IF l_end <= c_as_of THEN l_status := 'ZAVRSEN'; l_actual := l_end;
    ELSIF MOD(p,11)=0 THEN l_status := 'PAUZIRAN';
    ELSE l_status := 'U_TIJEKU'; END IF;
    l_manager := MOD(p-1,24)+1;
    l_budget := 25000+500*p;
    IF MOD(p,7)=0 THEN l_budget := 8000; END IF;
    INSERT INTO demo_a_projects VALUES
      (p,'AN-'||TO_CHAR(l_year,'FM0000')||'-'||TO_CHAR(l_local,'FM00'),
       'Demo analiticki projekt '||TO_CHAR(p,'FM00'),
       'Demo kupac '||TO_CHAR(MOD(p-1,6)+1,'FM00'),
       MOD(l_manager-1,4)+1,l_manager,l_start,l_end,l_actual,l_status,l_budget);
    FOR k IN 0..5 LOOP
      IF l_start+25*k <= c_as_of THEN
        l_cost_id := l_cost_id+1;
        l_category := CASE MOD(k,4) WHEN 0 THEN 'RAD' WHEN 1 THEN 'CLOUD'
          WHEN 2 THEN 'LICENCE' ELSE 'VANJSKE_USLUGE' END;
        INSERT INTO demo_a_costs VALUES
          (l_cost_id,p,l_start+25*k,l_category,500+97*p+137*k);
      END IF;
    END LOOP;
  END LOOP;

  FOR y IN 2025..2026 LOOP
    IF y=2025 THEN
      l_base := DATE '2025-07-07'; l_cancel := DATE '2025-06-09';
      l_education := DATE '2025-02-03'; l_used_employees := 20;
    ELSE
      l_base := DATE '2026-07-06'; l_cancel := DATE '2026-06-08';
      l_education := DATE '2026-02-02'; l_used_employees := 22;
    END IF;
    FOR e IN 1..24 LOOP
      IF e <= l_used_employees THEN
        FOR d IN 0..4 LOOP
          l_leave_id := l_leave_id+1;
          INSERT INTO demo_a_leave_days VALUES
            (l_leave_id,e,l_base+7*MOD(e-1,3)+d,'GODISNJI','ISKORISTEN',1);
        END LOOP;
      END IF;
      l_leave_id := l_leave_id+1;
      INSERT INTO demo_a_leave_days VALUES
        (l_leave_id,e,l_cancel,'GODISNJI','OTKAZAN',1);
      l_leave_id := l_leave_id+1;
      INSERT INTO demo_a_leave_days VALUES
        (l_leave_id,e,l_education,'EDUKACIJA','ISKORISTEN',1);
    END LOOP;
  END LOOP;
  FOR e IN 1..24 LOOP
    FOR d IN 0..1 LOOP
      l_leave_id := l_leave_id+1;
      INSERT INTO demo_a_leave_days VALUES
        (l_leave_id,e,DATE '2026-10-05'+d,'GODISNJI','ODOBREN',1);
    END LOOP;
  END LOOP;
  DBMS_OUTPUT.PUT_LINE('Inserted costs: '||l_cost_id||'; leave-day records: '||l_leave_id);
END;
~';

  -- Metadata for the later Select AI profile. Comments are not access control.
  EXECUTE IMMEDIATE q'~COMMENT ON TABLE demo_a_departments IS 'Fictional analytics demo departments. Independent of DEMO_PROJECTS.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON TABLE demo_a_employees IS '24 fictional employees, all hired in 2024. One row per employee.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON TABLE demo_a_projects IS '36 independent fictional projects. Reporting snapshot 2026-09-24. Do not combine with DEMO_PROJECTS. Count projects directly here, not rows after joining costs.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_projects.start_date IS 'Actual project start. Projects started in a year are filtered on this date. Last year relative to demo snapshot means 2025.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_projects.actual_end_date IS 'Actual completion, NULL if unfinished at the snapshot. Active during a year means start before next year and actual end NULL or on/after year start.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_projects.budget_eur IS 'Approved total project budget in EUR, not actual spending. Do not sum this after a one-to-many join without preaggregating costs.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON TABLE demo_a_costs IS 'Actual fictional costs through 2026-09-24. One row per cost item. Total spending is SUM(amount_eur); annual spending is filtered on cost_date, NOT project start_date.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_costs.amount_eur IS 'Actual cost amount in EUR; not budget. No currency conversion is required.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON TABLE demo_a_leave_days IS 'One fictional employee absence day per row, not one request. Unique employee/date. Sample recorded workdays, not a complete holiday calendar or leave entitlement ledger.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_leave_days.leave_type IS 'GODISNJI = annual leave; EDUKACIJA = training, not annual leave.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_leave_days.leave_status IS 'ISKORISTEN = actually taken; ODOBREN = approved future absence, not taken; OTKAZAN = cancelled, not taken.'~';
  EXECUTE IMMEDIATE q'~COMMENT ON COLUMN demo_a_leave_days.day_fraction IS 'Recorded workday amount. Sum only GODISNJI plus ISKORISTEN for annual leave days. COUNT(DISTINCT employee_id) counts people who took leave. Filter year on leave_date.'~';

  COMMIT;
  DBMS_OUTPUT.PUT_LINE('USPJEH: 5 analytics demo tables loaded. Original DEMO_PROJECTS and MCP tools unchanged.');
EXCEPTION WHEN OTHERS THEN
  ROLLBACK;
  -- Oracle DDL is committed implicitly. A partial schema or committed rows may
  -- remain after an error. Preserve everything and report the error; no auto-cleanup.
  RAISE;
END;
/
