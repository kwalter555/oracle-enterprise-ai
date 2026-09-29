-- Run as WEBUI_MCP, in a NEW SQL worksheet, using Run Script.
-- All customers, managers and projects below are fictional demo data.
-- Creates one table and inserts 12 rows. Does NOT expose a new MCP tool.
-- No DROP, DELETE, TRUNCATE, UPDATE or CREATE OR REPLACE.
-- If the name already exists, the entire block stops before data insertion.
SET SERVEROUTPUT ON
DECLARE
  l_exists PLS_INTEGER;
  l_rows PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'WEBUI_MCP'
     OR SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') <> 'WEBUI_MCP' THEN
    RAISE_APPLICATION_ERROR(-20002, 'Log in as WEBUI_MCP; current schema must also be WEBUI_MCP.');
  END IF;

  SELECT COUNT(*) INTO l_exists FROM user_objects
  WHERE object_name = 'DEMO_PROJECTS';
  IF l_exists > 0 THEN
    RAISE_APPLICATION_ERROR(-20003, 'DEMO_PROJECTS already exists. Nothing overwritten; do not delete it automatically.');
  END IF;

  EXECUTE IMMEDIATE q'~
    CREATE TABLE demo_projects (
      project_code    VARCHAR2(32 CHAR) CONSTRAINT demo_projects_pk PRIMARY KEY,
      project_name    VARCHAR2(120 CHAR) NOT NULL,
      customer_name   VARCHAR2(120 CHAR) NOT NULL,
      status          VARCHAR2(20 CHAR) NOT NULL,
      manager_name    VARCHAR2(80 CHAR) NOT NULL,
      start_date      DATE NOT NULL,
      target_end_date DATE NOT NULL,
      budget_eur      NUMBER(12,2) NOT NULL,
      spent_eur       NUMBER(12,2) NOT NULL,
      progress_pct    NUMBER(3) NOT NULL,
      description    VARCHAR2(500 CHAR) NOT NULL,
      CONSTRAINT demo_projects_status_ck
        CHECK (status IN ('PLANIRAN', 'U_TIJEKU', 'PAUZIRAN', 'ZAVRSEN')),
      CONSTRAINT demo_projects_dates_ck CHECK (target_end_date >= start_date),
      CONSTRAINT demo_projects_budget_ck CHECK (budget_eur >= 0),
      CONSTRAINT demo_projects_spent_ck CHECK (spent_eur >= 0),
      CONSTRAINT demo_projects_progress_ck CHECK (progress_pct BETWEEN 0 AND 100)
    )
  ~';

  -- Dynamic SQL is used because the table is created in this same block.
  -- This is a fixed literal, with no user-supplied SQL or inputs.
  EXECUTE IMMEDIATE q'~
    INSERT ALL
      INTO demo_projects VALUES
        ('ORION-742', 'AI support assistant', 'Demo Adria Retail', 'U_TIJEKU',
         'Ana Demo', DATE '2026-05-04', DATE '2026-11-30', 85000, 52000, 65,
         'Search internal documentation and provide answers with source citations.')
      INTO demo_projects VALUES
        ('ATLAS-315', 'Reporting migration', 'Demo Sjever Logistics', 'U_TIJEKU',
         'Marko Demo', DATE '2026-03-02', DATE '2026-10-15', 120000, 98000, 80,
         'Migrate daily reports to Autonomous Database.')
      INTO demo_projects VALUES
        ('VEGA-208', 'Supplier portal', 'Demo Jadran Industries', 'PAUZIRAN',
         'Iva Demo', DATE '2026-02-16', DATE '2026-09-15', 60000, 38000, 45,
         'Project awaiting approval of the revised integration scope.')
      INTO demo_projects VALUES
        ('LYRA-104', 'Digital archive', 'Demo Bor Services', 'ZAVRSEN',
         'Luka Demo', DATE '2026-01-12', DATE '2026-06-30', 45000, 42000, 100,
         'Contract archive with metadata search implemented.')
      INTO demo_projects VALUES
        ('NOVA-550', 'Demand forecasting', 'Demo Adria Retail', 'PLANIRAN',
         'Ana Demo', DATE '2026-10-01', DATE '2027-03-31', 95000, 0, 0,
         'Planned sales analysis using fictional test data.')
      INTO demo_projects VALUES
        ('PULSAR-630', 'Infrastructure monitoring', 'Demo Sjever Logistics', 'U_TIJEKU',
         'Petar Demo', DATE '2026-04-01', DATE '2026-09-01', 75000, 81000, 90,
         'Example of a project exceeding its budget and planned deadline.')
      INTO demo_projects VALUES
        ('AURORA-220', 'Invoice automation', 'Demo Lipa Finance', 'U_TIJEKU',
         'Iva Demo', DATE '2026-06-01', DATE '2026-12-15', 70000, 26000, 35,
         'Test data extraction and validation of incoming invoices.')
      INTO demo_projects VALUES
        ('ZENIT-410', 'Data catalog', 'Demo Jadran Industries', 'PLANIRAN',
         'Marko Demo', DATE '2026-11-02', DATE '2027-02-28', 50000, 0, 0,
         'Planned inventory of data sources and their owners.')
      INTO demo_projects VALUES
        ('COMET-905', 'Mobile service orders', 'Demo Bor Services', 'ZAVRSEN',
         'Luka Demo', DATE '2026-02-02', DATE '2026-08-31', 55000, 57000, 100,
         'Completed project with a small budget overrun.')
      INTO demo_projects VALUES
        ('TITAN-180', 'Sales data warehouse', 'Demo Lipa Finance', 'U_TIJEKU',
         'Petar Demo', DATE '2026-07-01', DATE '2027-01-31', 150000, 49000, 30,
         'Consolidate demo data for analytics.')
      INTO demo_projects VALUES
        ('IRIS-360', 'Training portal', 'Demo Kvarner Edu', 'PAUZIRAN',
         'Ana Demo', DATE '2026-04-15', DATE '2026-12-01', 35000, 12000, 25,
         'Awaiting preparation of training materials.')
      INTO demo_projects VALUES
        ('POLARIS-810', 'System security review', 'Demo Kvarner Edu', 'ZAVRSEN',
         'Iva Demo', DATE '2026-07-06', DATE '2026-09-18', 30000, 28000, 100,
         'Completed configuration review of the demonstration system.')
    SELECT 1 FROM dual
  ~';

  l_rows := SQL%ROWCOUNT;
  IF l_rows <> 12 THEN
    RAISE_APPLICATION_ERROR(-20004, 'Unexpected inserted row count.');
  END IF;
  COMMIT;
  DBMS_OUTPUT.PUT_LINE('SUCCESS: WEBUI_MCP.DEMO_PROJECTS created; 12 demo rows committed.');
EXCEPTION
  WHEN OTHERS THEN
    ROLLBACK;
    -- Oracle DDL commits: a successfully created table remains if INSERT fails.
    -- Preserve it for diagnosis; do not silently drop or reuse it.
    RAISE;
END;
/
