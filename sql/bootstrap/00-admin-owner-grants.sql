-- ADMIN, fresh demo database. First create WEBUI_MCP via Create User dialog.
-- Password only in the dialog, never in Git. No broad roles.
SET SERVEROUTPUT ON
DECLARE
  n PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20400,'Run as ADMIN.');
  END IF;
  SELECT COUNT(*) INTO n FROM dba_users WHERE username='WEBUI_MCP' AND account_status='OPEN';
  IF n <> 1 THEN RAISE_APPLICATION_ERROR(-20401,'Create an unlocked WEBUI_MCP user first.'); END IF;
  EXECUTE IMMEDIATE 'GRANT CREATE SESSION, CREATE PROCEDURE TO WEBUI_MCP';
  EXECUTE IMMEDIATE 'GRANT EXECUTE ON DBMS_CLOUD_AI_AGENT TO WEBUI_MCP';
  DBMS_OUTPUT.PUT_LINE('Owner grants ready. Run sql/projects/00-admin-permissions.sql for CREATE TABLE and limited quota.');
END;
/
