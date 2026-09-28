-- Run as DEMO_AI_READER in a NEW worksheet, Run Script / F5.
-- Two billable model requests with fictional demo metadata/questions.
-- Generated SQL is printed ONLY; it is never executed by this script.
-- Reference SELECTs below are hand-written, not model output.
SET SERVEROUTPUT ON
DECLARE
  PROCEDURE show_question(p_label VARCHAR2, p_question VARCHAR2) IS
    l_sql CLOB;
    l_offset PLS_INTEGER := 1;
    l_piece VARCHAR2(4000);
  BEGIN
    DBMS_OUTPUT.PUT_LINE(p_label);
    DBMS_OUTPUT.PUT_LINE(p_question);
    l_sql := DBMS_CLOUD_AI.GENERATE(
      prompt => p_question,
      profile_name => 'DEMO_ANALYTICS_OCI',
      action => 'showsql'
    );
    IF l_sql IS NULL OR DBMS_LOB.GETLENGTH(l_sql) = 0 THEN
      RAISE_APPLICATION_ERROR(-20240, 'Empty SHOWSQL response.');
    END IF;
    DBMS_OUTPUT.PUT_LINE('GENERIRANI SQL - NIJE IZVRSEN:');
    WHILE l_offset <= DBMS_LOB.GETLENGTH(l_sql) LOOP
      l_piece := DBMS_LOB.SUBSTR(l_sql, 4000, l_offset);
      DBMS_OUTPUT.PUT_LINE(l_piece);
      l_offset := l_offset + LENGTH(l_piece);
    END LOOP;
  END;
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'DEMO_AI_READER'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'DEMO_AI_READER' THEN
    RAISE_APPLICATION_ERROR(-20241, 'Run as DEMO_AI_READER.');
  END IF;
  show_question('TEST 1: TROSKOVI PO GODINI',
    'Koliki su stvarno evidentirani troskovi svih projekata po kalendarskoj godini nastanka troska? Prikazi godinu i ukupni trosak u EUR, sortirano po godini. Nemoj koristiti planirani budzet ili godinu pocetka projekta.');
  show_question('TEST 2: GODISNJI ODMORI 2025',
    'Koliko je razlicitih zaposlenika tijekom kalendarske 2025. godine stvarno iskoristilo godisnji odmor i koliko je ukupno dana godisnjeg odmora iskoristeno? Iskljuci samo odobrene ili otkazane dane i druge vrste odsutnosti.');
END;
/

-- These reference results do NOT prove the model-generated SQL is correct.
-- Expected: 2025 = 185523; 2026 = 288176 (snapshot through 2026-09-24).
SELECT EXTRACT(YEAR FROM cost_date) AS godina,
       SUM(amount_eur) AS trosak_eur
FROM WEBUI_MCP.DEMO_A_COSTS
GROUP BY EXTRACT(YEAR FROM cost_date)
ORDER BY godina;

-- Expected: 473699 EUR, all recorded costs across both years.
SELECT SUM(amount_eur) AS ukupni_trosak_eur
FROM WEBUI_MCP.DEMO_A_COSTS;

-- Expected: 20 employees, 100 days.
SELECT COUNT(DISTINCT employee_id) AS broj_zaposlenika,
       SUM(day_fraction) AS iskoristeni_dani
FROM WEBUI_MCP.DEMO_A_LEAVE_DAYS
WHERE leave_type = 'GODISNJI'
  AND leave_status = 'ISKORISTEN'
  AND leave_date >= DATE '2025-01-01'
  AND leave_date < DATE '2026-01-01';
