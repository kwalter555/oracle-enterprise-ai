-- WEBUI_MCP only. ONE billable model request, no generated SQL execution.
-- This live test must succeed before tool registration in 13.
SET SERVEROUTPUT ON
DECLARE
  l_result CLOB;
  l_status VARCHAR2(40);
  l_executed VARCHAR2(10);
  l_offset PLS_INTEGER := 1;
  l_piece VARCHAR2(4000);
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'WEBUI_MCP'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'WEBUI_MCP' THEN
    RAISE_APPLICATION_ERROR(-20340,'Run as WEBUI_MCP.');
  END IF;
  l_result := WEBUI_SQL_PROPOSE('Koliki su stvarno evidentirani troskovi svih projekata po godini nastanka troska?');
  SELECT JSON_VALUE(l_result,'$.status'), JSON_VALUE(l_result,'$.executed')
    INTO l_status,l_executed FROM dual;
  IF l_status IS NULL OR l_status <> 'PROPOSAL_ONLY'
     OR l_executed IS NULL OR l_executed <> 'false' THEN
    RAISE_APPLICATION_ERROR(-20341,'Unexpected proposal result. Do not register tool.');
  END IF;
  DBMS_OUTPUT.PUT_LINE('REZULTAT PRIJEDLOGA - SQL NIJE IZVRSEN:');
  WHILE l_offset <= DBMS_LOB.GETLENGTH(l_result) LOOP
    l_piece := DBMS_LOB.SUBSTR(l_result,4000,l_offset);
    DBMS_OUTPUT.PUT_LINE(l_piece);
    l_offset := l_offset + LENGTH(l_piece);
  END LOOP;
  DBMS_OUTPUT.PUT_LINE('USPJEH: cross-schema profile/model call returned proposal only. Send this output for review before 13.');
END;
/
