-- ADMIN, only AFTER configuring your own ADB dynamic group and IAM policy.
SET SERVEROUTPUT ON
BEGIN
  IF SYS_CONTEXT('USERENV','SESSION_USER') <> 'ADMIN' THEN
    RAISE_APPLICATION_ERROR(-20402,'Run as ADMIN.');
  END IF;
  DBMS_CLOUD_ADMIN.ENABLE_RESOURCE_PRINCIPAL();
END;
/
SELECT owner, credential_name FROM dba_credentials
WHERE owner='ADMIN' AND credential_name='OCI$RESOURCE_PRINCIPAL';
