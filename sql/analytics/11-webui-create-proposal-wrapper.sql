-- WEBUI_MCP only, AFTER 10 succeeds. No model calls. No tool registration yet.
-- Creates a local function for stable MCP argument discovery; never replaces.
SET SERVEROUTPUT ON
DECLARE
  n PLS_INTEGER;
  l_result CLOB;
  l_status VARCHAR2(40);
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'WEBUI_MCP'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'WEBUI_MCP' THEN
    RAISE_APPLICATION_ERROR(-20330,'Run as WEBUI_MCP.');
  END IF;
  SELECT COUNT(*) INTO n FROM user_objects WHERE object_name='WEBUI_SQL_PROPOSE';
  IF n <> 0 THEN RAISE_APPLICATION_ERROR(-20331,'Wrapper already exists. Nothing replaced.'); END IF;
  EXECUTE IMMEDIATE q'~
CREATE FUNCTION WEBUI_SQL_PROPOSE(P_QUESTION IN VARCHAR2)
RETURN CLOB
AUTHID CURRENT_USER
AS
BEGIN
  RETURN DEMO_AI_READER.DEMO_AI_SQL_PROPOSAL(P_QUESTION);
END;
~';
  SELECT COUNT(*) INTO n FROM user_objects
  WHERE object_name='WEBUI_SQL_PROPOSE' AND object_type='FUNCTION' AND status='VALID';
  IF n <> 1 THEN RAISE_APPLICATION_ERROR(-20332,'Wrapper not VALID; inspect USER_ERRORS.'); END IF;
  EXECUTE IMMEDIATE 'BEGIN :r := WEBUI_SQL_PROPOSE(:q); END;'
    USING OUT l_result, IN 'SELECT AI RUNSQL anything';
  SELECT JSON_VALUE(l_result,'$.status') INTO l_status FROM dual;
  IF l_status IS NULL OR l_status <> 'INVALID_ARGUMENT' THEN
    RAISE_APPLICATION_ERROR(-20333,'Cross-schema rejection test failed.');
  END IF;
  DBMS_OUTPUT.PUT_LINE('USPJEH: wrapper VALID; cross-schema invalid-input test passed, no model call.');
END;
/
SELECT line, position, text FROM user_errors
WHERE name='WEBUI_SQL_PROPOSE' AND type='FUNCTION' ORDER BY sequence;
