-- Run as ADMIN in Database Actions > SQL > Run Script.
-- Existing WEBUI_MCP user only; no password changes or broad roles.
SET SERVEROUTPUT ON
DECLARE
  l_tablespace VARCHAR2(128);
  l_max_bytes NUMBER;
BEGIN
  IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20001, 'Run this file as ADMIN.');
  END IF;

  SELECT default_tablespace INTO l_tablespace
  FROM dba_users WHERE username = 'WEBUI_MCP';

  SELECT NVL(MAX(max_bytes), 0) INTO l_max_bytes
  FROM dba_ts_quotas
  WHERE username = 'WEBUI_MCP' AND tablespace_name = l_tablespace;

  -- Preserve existing positive or unlimited quotas. Grant 10 MiB only
  -- if there is no quota, or the quota is zero.
  IF l_max_bytes = 0 THEN
    EXECUTE IMMEDIATE 'ALTER USER WEBUI_MCP QUOTA 10M ON '
      || DBMS_ASSERT.ENQUOTE_NAME(l_tablespace, FALSE);
    DBMS_OUTPUT.PUT_LINE('Quota: 10 MiB on ' || l_tablespace);
  ELSE
    DBMS_OUTPUT.PUT_LINE('Existing quota preserved.');
  END IF;

  EXECUTE IMMEDIATE 'GRANT CREATE TABLE TO WEBUI_MCP';
  DBMS_OUTPUT.PUT_LINE('CREATE TABLE granted to WEBUI_MCP.');
END;
/
