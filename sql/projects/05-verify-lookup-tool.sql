-- Run as WEBUI_MCP after 04 succeeds. No LLM invocation or table writes.
SELECT DBMS_CLOUD_AI_AGENT.DESCRIBE_TOOL(
  tool_name => 'WEBUI_PROJECT_LOOKUP'
) AS opis_alata FROM dual;

-- Expect successful tool execution with inner status OK, ORION-742,
-- project_status U_TIJEKU, remaining_budget_eur 33000, progress_pct 65.
SELECT DBMS_CLOUD_AI_AGENT.RUN_TOOL(
  tool_name => 'WEBUI_PROJECT_LOOKUP',
  input => '{"P_PROJECT_CODE":"ORION-742"}'
) AS rezultat_alata FROM dual;

-- Outer tool execution may succeed; inner business status must be NOT_FOUND.
SELECT DBMS_CLOUD_AI_AGENT.RUN_TOOL(
  tool_name => 'WEBUI_PROJECT_LOOKUP',
  input => '{"P_PROJECT_CODE":"UNKNOWN-999"}'
) AS nepostojeci_projekt FROM dual;
