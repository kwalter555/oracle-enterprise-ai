-- Run as DEMO_AI_READER after 05 succeeds. Run Script / F5.
-- ONE PAID MODEL REQUEST via OCI Cohere in Frankfurt.
-- Sends the synthetic question and allowed schema metadata/comments to the model.
-- SHOWSQL generates SQL but DOES NOT execute the generated SQL.
-- Review its output before running it. This file has no RUNSQL or NARRATE call.
SET SERVEROUTPUT ON
DECLARE
  l_sql CLOB;
  l_offset PLS_INTEGER := 1;
  l_piece VARCHAR2(4000);
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'DEMO_AI_READER'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'DEMO_AI_READER' THEN
    RAISE_APPLICATION_ERROR(-20230,'Run as DEMO_AI_READER.');
  END IF;
  l_sql := DBMS_CLOUD_AI.GENERATE(
    prompt => 'Koliko je projekata zapocelo u kalendarskoj 2025. godini? Koristi samo WEBUI_MCP.DEMO_A_PROJECTS i stupac START_DATE. Prebroji projekte s datumom pocetka od 2025-01-01 ukljucivo do 2026-01-01 iskljucivo. Vrati jedan stupac BROJ_PROJEKATA.',
    profile_name => 'DEMO_ANALYTICS_OCI',
    action => 'showsql'
  );
  IF l_sql IS NULL THEN
    RAISE_APPLICATION_ERROR(-20231,'Empty SHOWSQL response.');
  END IF;
  DBMS_OUTPUT.PUT_LINE('GENERIRANI SQL - NIJE IZVRSEN:');
  WHILE l_offset <= DBMS_LOB.GETLENGTH(l_sql) LOOP
    l_piece := DBMS_LOB.SUBSTR(l_sql,4000,l_offset);
    DBMS_OUTPUT.PUT_LINE(l_piece);
    l_offset := l_offset+LENGTH(l_piece);
  END LOOP;
END;
/

-- Independent, hand-written reference query. This does not execute model output.
-- Expected BROJ_PROJEKATA = 18.
SELECT COUNT(*) AS broj_projekata
FROM WEBUI_MCP.DEMO_A_PROJECTS
WHERE start_date >= DATE '2025-01-01' AND start_date < DATE '2026-01-01';
