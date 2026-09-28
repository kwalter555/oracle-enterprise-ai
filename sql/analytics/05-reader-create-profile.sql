-- Run as DEMO_AI_READER, never ADMIN or WEBUI_MCP. Run Script / F5.
-- Creates a new profile. Does not replace an existing profile or call the LLM.
SET SERVEROUTPUT ON
DECLARE
  l_count PLS_INTEGER;
BEGIN
  IF '__OCI_COMPARTMENT_OCID__' LIKE '\_\_%' ESCAPE '\' THEN
    RAISE_APPLICATION_ERROR(-20406,'Template only: replace all compartment placeholders in a LOCAL copy before running.');
  END IF;
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'DEMO_AI_READER'
     OR SYS_CONTEXT('USERENV','CURRENT_SCHEMA') <> 'DEMO_AI_READER' THEN
    RAISE_APPLICATION_ERROR(-20220,'Run as DEMO_AI_READER with current schema DEMO_AI_READER.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM user_cloud_ai_profiles
  WHERE profile_name='DEMO_ANALYTICS_OCI';
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20221,'DEMO_ANALYTICS_OCI already exists. Nothing replaced.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM session_privs WHERE privilege <> 'CREATE SESSION';
  IF l_count <> 0 THEN
    RAISE_APPLICATION_ERROR(-20222,'Unexpected effective system privileges. Stop and inspect.');
  END IF;
  SELECT COUNT(*) INTO l_count FROM WEBUI_MCP.DEMO_A_PROJECTS;
  IF l_count <> 36 THEN
    RAISE_APPLICATION_ERROR(-20223,'Expected 36 analytic demo projects.');
  END IF;

  DBMS_CLOUD_AI.CREATE_PROFILE(
    profile_name => 'DEMO_ANALYTICS_OCI',
    attributes => q'~{
      "provider": "oci",
      "credential_name": "OCI$RESOURCE_PRINCIPAL",
      "region": "eu-frankfurt-1",
      "oci_compartment_id": "__OCI_COMPARTMENT_OCID__",
      "model": "cohere.command-a-03-2025",
      "oci_apiformat": "COHERE",
      "object_list": [
        {"owner":"WEBUI_MCP","name":"DEMO_A_DEPARTMENTS"},
        {"owner":"WEBUI_MCP","name":"DEMO_A_EMPLOYEES"},
        {"owner":"WEBUI_MCP","name":"DEMO_A_PROJECTS"},
        {"owner":"WEBUI_MCP","name":"DEMO_A_COSTS"},
        {"owner":"WEBUI_MCP","name":"DEMO_A_LEAVE_DAYS"}
      ],
      "enforce_object_list": true,
      "comments": true,
      "constraints": true,
      "conversation": false,
      "temperature": 0,
      "max_tokens": 2048
    }~',
    description => 'Fictional analytics snapshot 2026-09-24; only five DEMO_A tables; not the original DEMO_PROJECTS.'
  );
  DBMS_OUTPUT.PUT_LINE('USPJEH: DEMO_ANALYTICS_OCI profile created. Model access not tested yet.');
END;
/

SELECT profile_name, status FROM user_cloud_ai_profiles
WHERE profile_name='DEMO_ANALYTICS_OCI';
