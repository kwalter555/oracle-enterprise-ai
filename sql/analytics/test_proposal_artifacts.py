"""Static packaging checks only, NOT an Oracle PL/SQL compiler/runtime test."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parent


def read(name):
    return (ROOT / name).read_text()


def body():
    sql = read('09-reader-create-proposal.sql')
    return re.search(r"EXECUTE IMMEDIATE q'~\n(CREATE FUNCTION.*?)\n~';", sql, re.S)[1]


class ProposalArtifacts(unittest.TestCase):
    def test_runtime_has_no_sql_executor(self):
        source = re.sub(r'--[^\n]*', '', body())
        self.assertNotRegex(source.upper(), r'\b(EXECUTE\s+IMMEDIATE|DBMS_SQL|OPEN\s+\w+\s+FOR|COMMIT|ROLLBACK|PRAGMA)\b')
        self.assertEqual(re.findall(r"action\s*=>\s*'([^']+)'", source), ['showsql'])
        self.assertIn("l_prompt := 'SELECT AI SHOWSQL ", source)
        self.assertLess(source.index("'SELECT[[:space:]]+AI'"), source.index('DBMS_CLOUD_AI.GENERATE'))
        self.assertIn("l_reply.put('executed', FALSE)", source)
        self.assertIn("l_reply.put('sql_validation', 'NOT_VALIDATED')", source)
        self.assertIn('AUTHID DEFINER', source)

    def test_input_and_output_bounds(self):
        source = body()
        self.assertIn('LENGTH(P_QUESTION) > 2000', source)
        self.assertIn("'[[:cntrl:]]'", source)
        self.assertIn('DBMS_LOB.GETLENGTH(l_sql)>16000', source)
        self.assertIn('LENGTH(l_text) <> DBMS_LOB.GETLENGTH(l_sql)', source)
        install = read('09-reader-create-proposal.sql')
        self.assertEqual(len(re.findall(r'^  expect_rejected\(', install, re.M)), 6)

    def test_fixed_whitelist(self):
        attrs = json.loads(re.search(r"attributes\s*=>\s*'(\{.*?\})'", body(), re.S)[1])
        names = {'DEMO_A_DEPARTMENTS','DEMO_A_EMPLOYEES','DEMO_A_PROJECTS','DEMO_A_COSTS','DEMO_A_LEAVE_DAYS'}
        self.assertEqual({x['name'] for x in attrs['object_list']}, names)
        self.assertTrue(all(x['owner'] == 'WEBUI_MCP' for x in attrs['object_list']))
        self.assertIs(attrs['enforce_object_list'], True)
        self.assertIs(attrs['conversation'], False)
        self.assertEqual(attrs['max_tokens'], 2048)

    def test_custom_proposal_tool_only(self):
        source = read('13-webui-register-proposal.sql')
        attrs = json.loads(re.search(r"attributes\s*=>\s*q'~(.*?)~'", source, re.S)[1])
        self.assertEqual(attrs['function'], 'WEBUI_SQL_PROPOSE')
        self.assertNotIn('tool_type', attrs)
        self.assertEqual([v['name'] for v in attrs['tool_inputs']], ['P_QUESTION'])
        self.assertNotIn('DBMS_CLOUD_AI.GENERATE', source)

    def test_nondestructive_install_and_cleanup(self):
        for pattern in ['08-*.sql','09-*.sql','10-*.sql','11-*.sql','12-*.sql','13-*.sql']:
            for path in ROOT.glob(pattern):
                self.assertNotIn('CREATE OR REPLACE', path.read_text().upper())
                self.assertNotRegex(path.read_text().upper(), r'\bDROP\s+(FUNCTION|TABLE|USER)\b')
        setup = read('08-admin-enable-proposal-install.sql')
        self.assertEqual(re.findall(r"EXECUTE IMMEDIATE '(GRANT[^']+)'", setup),
                         ['GRANT CREATE PROCEDURE TO DEMO_AI_READER'])
        cleanup = read('10-admin-finish-proposal-install.sql')
        self.assertIn('REVOKE CREATE PROCEDURE FROM DEMO_AI_READER', cleanup)
        self.assertLess(cleanup.index('REVOKE CREATE PROCEDURE'), cleanup.index("object_name='DEMO_AI_SQL_PROPOSAL'"))
        wrapper = read('11-webui-create-proposal-wrapper.sql')
        self.assertIn('RETURN DEMO_AI_READER.DEMO_AI_SQL_PROPOSAL(P_QUESTION)', wrapper)


if __name__ == '__main__':
    unittest.main(verbosity=2)
