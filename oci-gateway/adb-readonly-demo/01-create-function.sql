-- Database Actions > SQL, signed in as WEBUI_MCP (not ADMIN).
-- Preparation only: creates one function; never replaces existing objects.
-- Demo rows are synthetic SQL literals, NOT rows from a business table.
-- Execute this file separately, verify status, then run 02-register-tool.sql.

CREATE FUNCTION WEBUI_PROJECT_LOOKUP (
    P_PROJECT_CODE IN VARCHAR2
) RETURN CLOB
AUTHID CURRENT_USER
AS
    L_CODE    VARCHAR2(32);
    L_RESULT CLOB;
BEGIN
    -- Normalize only after bounding length. No SQL fragments or identifiers accepted.
    IF P_PROJECT_CODE IS NULL OR LENGTH(P_PROJECT_CODE) > 32 THEN
        RETURN '{"status":"INVALID_ARGUMENT","message":"Provide a project code such as ORION-742."}';
    END IF;
    L_CODE := UPPER(TRIM(P_PROJECT_CODE));
    IF L_CODE IS NULL OR NOT REGEXP_LIKE(L_CODE, '^[A-Z]{2,12}-[0-9]{1,6}$', 'c') THEN
        RETURN '{"status":"INVALID_ARGUMENT","message":"Invalid project code format."}';
    END IF;

    -- Fixed SELECT; caller cannot alter tables, columns, predicates or row limit.
    WITH DEMO_PROJECTS (PROJECT_CODE, PROJECT_NAME, PROJECT_STATUS, COMPLETION_PCT) AS (
        SELECT 'ORION-742', 'Demo Oracle AI integration', 'IN_PROGRESS', 65 FROM DUAL
        UNION ALL
        SELECT 'ATLAS-315', 'Demo sales analytics', 'PLANNED', 10 FROM DUAL
        UNION ALL
        SELECT 'VEGA-208', 'Demo document archive', 'COMPLETED', 100 FROM DUAL
    )
    SELECT JSON_OBJECT(
               'status' VALUE 'OK',
               'data_origin' VALUE 'SYNTHETIC_DEMO',
               'project_code' VALUE PROJECT_CODE,
               'project_name' VALUE PROJECT_NAME,
               'project_status' VALUE PROJECT_STATUS,
               'completion_pct' VALUE COMPLETION_PCT
               RETURNING CLOB
           )
      INTO L_RESULT
      FROM DEMO_PROJECTS
     WHERE PROJECT_CODE = L_CODE;
    RETURN L_RESULT;
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        RETURN '{"status":"NOT_FOUND","data_origin":"SYNTHETIC_DEMO","message":"Project not found."}';
END;
/

-- Must show VALID, and the errors query must return no rows.
SELECT USER AS CONNECTED_USER FROM DUAL;
SELECT OBJECT_NAME, STATUS FROM USER_OBJECTS
WHERE OBJECT_NAME = 'WEBUI_PROJECT_LOOKUP' AND OBJECT_TYPE = 'FUNCTION';
SELECT LINE, POSITION, TEXT FROM USER_ERRORS
WHERE NAME = 'WEBUI_PROJECT_LOOKUP' AND TYPE = 'FUNCTION'
ORDER BY SEQUENCE;

SELECT WEBUI_PROJECT_LOOKUP('ORION-742') AS RESULT FROM DUAL;
SELECT WEBUI_PROJECT_LOOKUP('UNKNOWN-999') AS RESULT FROM DUAL;
SELECT WEBUI_PROJECT_LOOKUP(q'[ORION-742' OR 1=1 --]') AS RESULT FROM DUAL;
