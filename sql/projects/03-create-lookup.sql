-- Run the ENTIRE file as WEBUI_MCP in Database Actions > SQL > Run Script.
-- Creates a NEW function; never replaces an existing object.
SET SERVEROUTPUT ON
DECLARE
  l_count PLS_INTEGER;
BEGIN
  IF SYS_CONTEXT('USERENV', 'SESSION_USER') <> 'WEBUI_MCP'
     OR SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') <> 'WEBUI_MCP' THEN
    RAISE_APPLICATION_ERROR(-20010, 'Sign in as WEBUI_MCP with current schema WEBUI_MCP.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM user_objects
  WHERE object_name = 'WEBUI_PROJECT_LOOKUP';
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20011, 'WEBUI_PROJECT_LOOKUP already exists. Nothing replaced. Stop and inspect.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM user_tables WHERE table_name = 'DEMO_PROJECTS';
  IF l_count <> 1 THEN
    RAISE_APPLICATION_ERROR(-20012, 'DEMO_PROJECTS table is missing.');
  END IF;

  EXECUTE IMMEDIATE q'~
CREATE FUNCTION WEBUI_PROJECT_LOOKUP (
  P_PROJECT_CODE IN VARCHAR2
) RETURN CLOB
AUTHID CURRENT_USER
AS
  l_code VARCHAR2(32);
  l_result CLOB;
BEGIN
  IF P_PROJECT_CODE IS NULL OR LENGTH(P_PROJECT_CODE) > 32
     OR REGEXP_LIKE(P_PROJECT_CODE, '[[:cntrl:]]') THEN
    RETURN '{"status":"INVALID_ARGUMENT","message":"Provide one project code, at most 32 characters."}';
  END IF;
  l_code := UPPER(TRIM(P_PROJECT_CODE));
  IF l_code IS NULL OR NOT REGEXP_LIKE(l_code, '^[A-Z]{2,12}-[0-9]{1,6}$', 'c') THEN
    RETURN '{"status":"INVALID_ARGUMENT","message":"Use a project code such as ORION-742. SQL is not accepted."}';
  END IF;

  SELECT JSON_OBJECT(
    'status' VALUE 'OK',
    'data_origin' VALUE 'SYNTHETIC_DEMO',
    'currency' VALUE 'EUR',
    'project_code' VALUE project_code,
    'project_name' VALUE project_name,
    'customer_name' VALUE customer_name,
    'project_status' VALUE status,
    'manager_name' VALUE manager_name,
    'start_date' VALUE TO_CHAR(start_date, 'YYYY-MM-DD'),
    'target_end_date' VALUE TO_CHAR(target_end_date, 'YYYY-MM-DD'),
    'budget_eur' VALUE budget_eur,
    'spent_eur' VALUE spent_eur,
    'remaining_budget_eur' VALUE (budget_eur - spent_eur),
    'progress_pct' VALUE progress_pct,
    'description' VALUE description
    RETURNING CLOB
  ) INTO l_result
  FROM WEBUI_MCP.DEMO_PROJECTS
  WHERE project_code = l_code;
  RETURN l_result;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RETURN '{"status":"NOT_FOUND","data_origin":"SYNTHETIC_DEMO","message":"Project not found. Do not invent project data."}';
END;
~';

  SELECT COUNT(*) INTO l_count FROM user_objects
  WHERE object_name = 'WEBUI_PROJECT_LOOKUP'
    AND object_type = 'FUNCTION' AND status = 'VALID';
  IF l_count <> 1 THEN
    RAISE_APPLICATION_ERROR(-20013, 'Function is not VALID. Inspect USER_ERRORS; do not register the tool.');
  END IF;
  DBMS_OUTPUT.PUT_LINE('SUCCESS: WEBUI_PROJECT_LOOKUP created and VALID. No table data changed.');
END;
/

SELECT line, position, text FROM user_errors
WHERE name = 'WEBUI_PROJECT_LOOKUP' AND type = 'FUNCTION'
ORDER BY sequence;
