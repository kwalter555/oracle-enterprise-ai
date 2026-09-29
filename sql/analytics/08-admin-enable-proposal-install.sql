-- ADMIN only. Temporary CREATE PROCEDURE for installing one proposal function.
-- No model calls. No table-data changes. Run Script / F5 in a new worksheet.
SET SERVEROUTPUT ON
DECLARE
  n PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20300,'Run as ADMIN.');
  END IF;
  SELECT COUNT(*) INTO n FROM dba_users
  WHERE username='DEMO_AI_READER' AND account_status='OPEN';
  IF n <> 1 THEN RAISE_APPLICATION_ERROR(-20301,'Reader must exist and be OPEN.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_role_privs WHERE grantee='DEMO_AI_READER';
  IF n <> 0 THEN RAISE_APPLICATION_ERROR(-20302,'Unexpected reader roles. Stop.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_sys_privs
  WHERE grantee='DEMO_AI_READER' AND privilege <> 'CREATE SESSION';
  IF n <> 0 THEN RAISE_APPLICATION_ERROR(-20303,'Unexpected reader system privileges; inspect before proceeding.'); END IF;
  SELECT COUNT(*) INTO n FROM dba_objects
  WHERE owner='DEMO_AI_READER' AND object_name='DEMO_AI_SQL_PROPOSAL';
  IF n <> 0 THEN RAISE_APPLICATION_ERROR(-20304,'Proposal object already exists. Nothing replaced.'); END IF;
  EXECUTE IMMEDIATE 'GRANT CREATE PROCEDURE TO DEMO_AI_READER';
  DBMS_OUTPUT.PUT_LINE('SUCCESS: temporary CREATE PROCEDURE granted. Run 09 as reader, then 10 as ADMIN.');
END;
/
