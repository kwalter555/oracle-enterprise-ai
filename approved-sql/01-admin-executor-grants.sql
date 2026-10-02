-- First create DEMO_SQL_EXECUTOR as ADMIN using SQL Developer's Create User dialog.
-- No roles, no quotas, no CREATE TABLE/PROCEDURE, no expired password.
-- Run this file as ADMIN in a fresh worksheet (F5). No passwords in this script.
-- Grants auto-commit in Oracle. On any error STOP and inspect; no automatic revokes.
SET SERVEROUTPUT ON
DECLARE
  n PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20501,'Run as ADMIN.');
  END IF;
  SELECT COUNT(*) INTO n FROM dba_users
    WHERE username='DEMO_SQL_EXECUTOR' AND account_status='OPEN';
  IF n<>1 THEN RAISE_APPLICATION_ERROR(-20502,'Create the dedicated OPEN executor account first.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_role_privs WHERE grantee='DEMO_SQL_EXECUTOR';
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20503,'Executor must not have roles. Nothing revoked.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_sys_privs WHERE grantee='DEMO_SQL_EXECUTOR'
    AND (privilege<>'CREATE SESSION' OR admin_option<>'NO');
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20504,'Unexpected system/admin privileges. Stop.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_objects WHERE owner='DEMO_SQL_EXECUTOR';
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20505,'Executor must not own objects.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_tab_privs WHERE grantee='DEMO_SQL_EXECUTOR'
    AND NOT (owner='WEBUI_MCP' AND table_name IN
      ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS')
      AND privilege='SELECT' AND grantable='NO');
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20506,'Unexpected object grants. Stop.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_col_privs WHERE grantee='DEMO_SQL_EXECUTOR';
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20507,'Unexpected column grants.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_tables WHERE owner='WEBUI_MCP' AND table_name IN
    ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS');
  IF n<>5 THEN RAISE_APPLICATION_ERROR(-20508,'Expected all five physical demo tables.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_tab_cols WHERE owner='WEBUI_MCP' AND table_name IN
    ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS')
    AND (virtual_column='YES' OR data_type NOT IN ('VARCHAR2','CHAR','NUMBER','DATE'));
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20509,'Only original scalar demo columns supported.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_policies WHERE object_owner='WEBUI_MCP' AND object_name IN
    ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS');
  IF n<>0 THEN RAISE_APPLICATION_ERROR(-20510,'VPD policies require separate review.'); END IF;

  EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO DEMO_SQL_EXECUTOR';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_DEPARTMENTS TO DEMO_SQL_EXECUTOR';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_EMPLOYEES TO DEMO_SQL_EXECUTOR';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_PROJECTS TO DEMO_SQL_EXECUTOR';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_COSTS TO DEMO_SQL_EXECUTOR';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_LEAVE_DAYS TO DEMO_SQL_EXECUTOR';
  DBMS_OUTPUT.PUT_LINE('SUCCESS: executor has CREATE SESSION and SELECT on five demo tables only.');
  DBMS_OUTPUT.PUT_LINE('Existing proposal profile, functions, tools and data were not changed.');
END;
/
SELECT privilege, admin_option FROM dba_sys_privs WHERE grantee='DEMO_SQL_EXECUTOR';
SELECT granted_role FROM dba_role_privs WHERE grantee='DEMO_SQL_EXECUTOR';
SELECT owner,table_name,privilege,grantable FROM dba_tab_privs
WHERE grantee='DEMO_SQL_EXECUTOR' ORDER BY table_name;
-- PUBLIC grants are inherited by Oracle users; this is not a full PUBLIC audit.
