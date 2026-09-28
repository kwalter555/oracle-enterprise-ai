-- READ ONLY. Run as ADMIN after loading/verifying the demo data.
-- Prints only capability/account/privilege metadata. No secret values or LLM calls.
SELECT SYS_CONTEXT('USERENV','SESSION_USER') AS connected_user FROM dual;

SELECT owner, object_name, procedure_name
FROM all_procedures
WHERE (object_name='DBMS_CLOUD_AI' AND procedure_name IN ('CREATE_PROFILE','GENERATE'))
   OR (object_name='DBMS_CLOUD_ADMIN' AND procedure_name='ENABLE_RESOURCE_PRINCIPAL')
ORDER BY object_name, procedure_name;

SELECT username, account_status FROM dba_users
WHERE username IN ('WEBUI_MCP','DEMO_AI_READER') ORDER BY username;

SELECT owner, credential_name FROM dba_credentials
WHERE owner='ADMIN' AND credential_name='OCI$RESOURCE_PRINCIPAL';

SELECT grantee, owner, table_name, privilege FROM dba_tab_privs
WHERE grantee IN ('WEBUI_MCP','DEMO_AI_READER')
  AND ((owner='ADMIN' AND table_name='OCI$RESOURCE_PRINCIPAL')
    OR table_name IN ('DBMS_CLOUD_AI','DBMS_CLOUD_AI_AGENT'))
ORDER BY grantee, owner, table_name;

-- Zero rows for the resource principal is not an error: it may not be enabled yet.
-- This does NOT establish that IAM policies or model access are configured.
