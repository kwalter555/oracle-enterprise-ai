-- Run as ADMIN, AFTER creating DEMO_AI_READER in SQL Developer's Create User dialog.
-- No password in this file. No account creation/reset, quotas or broad roles.
-- Use a new worksheet with no unrelated uncommitted work. Run Script / F5.
SET SERVEROUTPUT ON
DECLARE
  l_count PLS_INTEGER;
  l_status VARCHAR2(32);
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20201,'Run this file as ADMIN.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_users WHERE username='DEMO_AI_READER';
  IF l_count <> 1 THEN
    RAISE_APPLICATION_ERROR(-20202,'Create DEMO_AI_READER first using the user dialog. Do not send its password.');
  END IF;
  SELECT account_status INTO l_status FROM dba_users WHERE username='DEMO_AI_READER';
  IF l_status <> 'OPEN' THEN
    RAISE_APPLICATION_ERROR(-20203,'DEMO_AI_READER is not OPEN. Stop and inspect account status.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_role_privs WHERE grantee='DEMO_AI_READER';
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20204,'Reader has role grants. Stop and inspect; no automatic revokes.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_sys_privs
  WHERE grantee='DEMO_AI_READER' AND privilege <> 'CREATE SESSION';
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20205,'Reader has unexpected system privileges. Stop and inspect.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_objects
  WHERE owner='DEMO_AI_READER' AND object_type IN
    ('TABLE','VIEW','MATERIALIZED VIEW','FUNCTION','PROCEDURE','PACKAGE','TRIGGER','SYNONYM','DATABASE LINK');
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20206,'Reader already owns application objects. Stop and inspect.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_tab_privs
  WHERE grantee='DEMO_AI_READER'
    AND NOT (
      (owner='WEBUI_MCP' AND table_name IN
        ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS')
        AND privilege='SELECT' AND grantable='NO')
      OR (owner='C##CLOUD$SERVICE' AND table_name='DBMS_CLOUD_AI' AND privilege='EXECUTE' AND grantable='NO')
      OR (owner='ADMIN' AND table_name='OCI$RESOURCE_PRINCIPAL' AND grantable='NO')
    );
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20207,'Reader has unexpected direct object privileges. Stop and inspect.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_col_privs WHERE grantee='DEMO_AI_READER';
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20208,'Reader has column-level grants. Stop and inspect.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_tables
  WHERE owner='WEBUI_MCP' AND table_name IN
    ('DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS');
  IF l_count <> 5 THEN
    RAISE_APPLICATION_ERROR(-20209,'Expected all five source demo tables.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM dba_credentials
  WHERE owner='ADMIN' AND credential_name='OCI$RESOURCE_PRINCIPAL';
  IF l_count <> 1 THEN
    RAISE_APPLICATION_ERROR(-20210,'ADMIN resource principal is not enabled.');
  END IF;

  EXECUTE IMMEDIATE 'GRANT CREATE SESSION TO DEMO_AI_READER';
  EXECUTE IMMEDIATE 'GRANT EXECUTE ON DBMS_CLOUD_AI TO DEMO_AI_READER';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_DEPARTMENTS TO DEMO_AI_READER';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_EMPLOYEES TO DEMO_AI_READER';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_PROJECTS TO DEMO_AI_READER';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_COSTS TO DEMO_AI_READER';
  EXECUTE IMMEDIATE 'GRANT SELECT ON WEBUI_MCP.DEMO_A_LEAVE_DAYS TO DEMO_AI_READER';
  DBMS_CLOUD_ADMIN.ENABLE_RESOURCE_PRINCIPAL(username => 'DEMO_AI_READER');
  DBMS_OUTPUT.PUT_LINE('USPJEH: reader access configured for five demo tables and Select AI.');
END;
/

SELECT grantee, privilege FROM dba_sys_privs
WHERE grantee='DEMO_AI_READER' ORDER BY privilege;
SELECT grantee, granted_role FROM dba_role_privs WHERE grantee='DEMO_AI_READER';
SELECT grantee, owner, table_name, privilege, grantable FROM dba_tab_privs
WHERE grantee='DEMO_AI_READER' ORDER BY owner, table_name, privilege;

-- These checks cover direct grants and roles, not a complete PUBLIC/package audit.
-- They do not make unrestricted generated SQL safe for production use.
