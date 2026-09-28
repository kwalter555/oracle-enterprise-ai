-- ADMIN only. Remove precisely the temporary privilege added by 08.
-- No model calls, no data changes. Do not change other users' privileges.
SET SERVEROUTPUT ON
DECLARE
  n PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20320,'Run as ADMIN.');
  END IF;
  SELECT COUNT(*) INTO n FROM dba_sys_privs
  WHERE grantee='DEMO_AI_READER' AND privilege='CREATE PROCEDURE';
  IF n = 1 THEN
    EXECUTE IMMEDIATE 'REVOKE CREATE PROCEDURE FROM DEMO_AI_READER';
  END IF;
  SELECT COUNT(*) INTO n FROM dba_objects
  WHERE owner='DEMO_AI_READER' AND object_name='DEMO_AI_SQL_PROPOSAL'
    AND object_type='FUNCTION' AND status='VALID';
  IF n <> 1 THEN RAISE_APPLICATION_ERROR(-20321,'Temporary privilege removed; proposal function is missing or invalid. Stop and inspect.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_sys_privs
  WHERE grantee='DEMO_AI_READER' AND privilege <> 'CREATE SESSION';
  IF n <> 0 THEN RAISE_APPLICATION_ERROR(-20322,'Unexpected remaining reader system privileges. Stop.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_role_privs WHERE grantee='DEMO_AI_READER';
  IF n <> 0 THEN RAISE_APPLICATION_ERROR(-20323,'Unexpected reader roles. Stop.'); END IF;
  DBMS_OUTPUT.PUT_LINE('USPJEH: temporary CREATE PROCEDURE removed; reader system privileges limited to CREATE SESSION.');
END;
/
SELECT privilege FROM dba_sys_privs WHERE grantee='DEMO_AI_READER' ORDER BY privilege;
