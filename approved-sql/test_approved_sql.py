"""Offline regression checks. No Oracle, OCI, MCP or model calls."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import datetime
import decimal
import contextlib
import io
import json
from pathlib import Path
import secrets
import tempfile
import time
import unittest
import zipfile
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from database import Oracle, json_cell
from ledger import Ledger, sign
from policy import Rejected, TABLES, canonical_sql, validate_question
from service import create_app, load_config
import webui_tool
import configure
import preflight
import yaml

COUNT = 'SELECT COUNT(*) AS n FROM WEBUI_MCP.DEMO_A_PROJECTS'
COSTS = '''SELECT EXTRACT(YEAR FROM c.COST_DATE) AS year, SUM(c.AMOUNT_EUR) AS total
FROM WEBUI_MCP.DEMO_A_COSTS c GROUP BY EXTRACT(YEAR FROM c.COST_DATE) ORDER BY year'''
LEAVE = '''SELECT COUNT(DISTINCT ld.EMPLOYEE_ID) AS employees, SUM(ld.DAY_FRACTION) AS days
FROM WEBUI_MCP.DEMO_A_LEAVE_DAYS ld WHERE ld.LEAVE_TYPE = 'GODISNJI'
AND ld.LEAVE_STATUS = 'ISKORISTEN' AND ld.LEAVE_DATE >= DATE '2025-01-01'
AND ld.LEAVE_DATE < DATE '2026-01-01' '''


class PolicyTests(unittest.TestCase):
    def test_positive_roundtrips(self):
        queries = [COUNT, COSTS, LEAVE,
            'SELECT p.PROJECT_CODE, SUM(c.AMOUNT_EUR) AS total FROM WEBUI_MCP.DEMO_A_PROJECTS p JOIN WEBUI_MCP.DEMO_A_COSTS c ON p.PROJECT_ID=c.PROJECT_ID GROUP BY p.PROJECT_CODE HAVING SUM(c.AMOUNT_EUR)>10 ORDER BY total DESC',
            "SELECT CASE WHEN AMOUNT_EUR>10 THEN 'HIGH' ELSE 'LOW' END AS size_band FROM WEBUI_MCP.DEMO_A_COSTS",
            'SELECT ROUND(AVG(AMOUNT_EUR),2), COALESCE(MIN(AMOUNT_EUR),0), MAX(AMOUNT_EUR) FROM WEBUI_MCP.DEMO_A_COSTS']
        for sql in queries:
            with self.subTest(sql=sql):
                result = canonical_sql(sql)
                self.assertEqual(result, canonical_sql(result))
                self.assertIn('"WEBUI_MCP".', result)

    def test_negative_corpus(self):
        statements = [
            'DELETE FROM WEBUI_MCP.DEMO_A_PROJECTS', 'BEGIN NULL; END;',
            COUNT + '; DROP TABLE x', COUNT + ' FOR UPDATE',
            COUNT.replace('COUNT(*)', '*'), COUNT.replace('COUNT(*)', 'p.*'),
            COUNT.replace('COUNT(*)', 'SYS.DBMS_LOCK.SLEEP(5)'),
            COUNT.replace('COUNT(*)', "UTL_HTTP.REQUEST('https://example.invalid')"),
            COUNT.replace('COUNT(*)', 'WEBUI_MCP.CUSTOM_FN(PROJECT_ID)'),
            COUNT.replace('COUNT(*)', 'DEMO_SEQ.NEXTVAL'),
            COUNT.replace('COUNT(*)', 'PASSWORD'),
            COUNT.replace('WEBUI_MCP.DEMO_A_PROJECTS', 'SYS.DBA_USERS'),
            COUNT.replace('WEBUI_MCP.DEMO_A_PROJECTS', 'DEMO_A_PROJECTS'),
            COUNT + '@remote', COUNT + ' UNION ALL ' + COUNT,
            'WITH x AS (' + COUNT + ') SELECT * FROM x',
            COUNT + ' WHERE PROJECT_ID IN (SELECT PROJECT_ID FROM WEBUI_MCP.DEMO_A_PROJECTS)',
            'SELECT (SELECT COUNT(*) FROM WEBUI_MCP.DEMO_A_COSTS) FROM WEBUI_MCP.DEMO_A_PROJECTS',
            COUNT.replace('SELECT', 'SELECT /*+ PARALLEL(100) */'), COUNT + '-- end',
            COUNT.replace(' AS n', ' INTO another_table'),
            COUNT + ' CROSS JOIN WEBUI_MCP.DEMO_A_COSTS',
            COUNT + ' JOIN WEBUI_MCP.DEMO_A_COSTS USING(PROJECT_ID)',
            COUNT.replace('COUNT(*)', 'ROW_NUMBER() OVER(ORDER BY PROJECT_ID)'),
            COUNT.replace('COUNT(*)', 'XMLTYPE(PROJECT_NAME)'),
            COUNT + ' CONNECT BY LEVEL < 1000000000',
            COUNT + " WHERE START_DATE > TO_DATE(PROJECT_NAME, 'YYYY-MM-DD')",
            COUNT + " WHERE START_DATE > DATE '2025-99-99'",
            COUNT + " WHERE PROJECT_CODE='x;delete'",
            COUNT.replace('COUNT(*)', 'JSON_OBJECT(*)'),
            COUNT + ' AS OF TIMESTAMP SYSTIMESTAMP',
            COUNT.replace('COUNT(*)', 'ORA_HASH(PROJECT_NAME)'),
            COUNT.replace('COUNT(*)', 'LISTAGG(PROJECT_NAME)'),
            COUNT.replace('COUNT(*)', 'TO_CHAR(START_DATE)'),
            'SELECT 1 FROM dual', '', 'x' * 16001,
        ]
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(Rejected):
                canonical_sql(sql)

    def test_question_rejection(self):
        for q in ['', 'x'*2001, 'a\nb', 'SELECT AI RUNSQL x']:
            with self.subTest(q=q[:30]), self.assertRaises(Rejected):
                validate_question(q)
        self.assertEqual(validate_question(' How many projects? '), 'How many projects?')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 1000
        self.ledger = Ledger(Path(self.tmp.name)/'ledger.sqlite', clock=lambda: self.now)
        self.key = secrets.token_hex(32)
        self.p = self.ledger.create('user', 'chat', 'question', canonical_sql(COUNT))

    def claim(self, **kw):
        values = dict(proposal_id=self.p['id'], sql_hash=self.p['sha256'], user_id='user',
                      chat_id='chat', signature=sign(self.key, self.p), key=self.key)
        values.update(kw)
        return self.ledger.claim(**values)

    def test_identity_hash_and_signature(self):
        for override in [{'user_id':'other'}, {'chat_id':'other'}, {'sql_hash':'0'*64},
                         {'signature':'0'*64}, {'proposal_id':'0'*48}]:
            with self.subTest(override=override), self.assertRaises(Rejected):
                self.claim(**override)
        self.assertEqual(self.claim()['sql'], self.p['sql'])

    def test_expiry(self):
        self.now = self.p['expires_at']
        with self.assertRaises(Rejected): self.claim()

    def test_replay_after_restart(self):
        self.claim()
        self.ledger = Ledger(self.ledger.path, clock=lambda: self.now)
        with self.assertRaises(Rejected): self.claim()

    def test_denied(self):
        self.ledger.finish(self.p, 'DENIED')
        with self.assertRaises(Rejected): self.claim()

    def test_single_concurrent_winner(self):
        def attempt(_):
            try: self.claim(); return 1
            except Rejected: return 0
        with ThreadPoolExecutor(8) as pool:
            self.assertEqual(sum(pool.map(attempt, range(8))), 1)

    def test_rate_limit_includes_generation_failures(self):
        for _ in range(30): self.ledger.reserve_generation('user','chat')
        with self.assertRaises(Rejected): self.ledger.reserve_generation('user','chat')

    def test_tamper_and_cleanup(self):
        with self.ledger.db() as db:
            db.execute('UPDATE proposals SET sql=? WHERE id=?', ('other SQL', self.p['id']))
        with self.assertRaises(Rejected): self.claim()
        self.now += 301
        self.ledger.create('user', 'chat', 'new', canonical_sql(COUNT))
        with self.ledger.db() as db:
            row = db.execute('SELECT sql,question,state FROM proposals WHERE id=?',(self.p['id'],)).fetchone()
        self.assertEqual(tuple(row), (None,None,'EXPIRED'))


class FakeOracle:
    def __init__(self): self.sql=COUNT; self.executions=[]; self.fail=False; self.proposals=0
    def propose(self, question): self.proposals+=1; return self.sql
    def execute(self, sql, actor):
        self.executions.append((sql,actor))
        if self.fail: raise RuntimeError('private error')
        return {'columns':['N'], 'rows':[['36']], 'truncated':False, 'row_count_returned':1}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.config = dict(api_key=secrets.token_hex(32), approval_key=secrets.token_hex(32),
                           allowed_user_ids=['user'], execution_enabled=True)
        self.oracle = FakeOracle()
        self.ledger = Ledger(Path(self.tmp.name)/'ledger.sqlite')
        self.app = create_app(self.config, self.oracle, self.ledger)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.headers={'Authorization':'Bearer '+self.config['api_key'],
                      'X-WebUI-User-ID':'user','X-WebUI-Chat-ID':'chat'}

    def propose(self):
        response=self.client.post('/proposals',json={'question':'Count projects'},headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def approval(self,p):
        return dict(proposal_id=p['id'],sha256=p['sha256'],signature=sign(self.config['approval_key'],p))

    def test_auth_and_schema(self):
        self.assertEqual(self.client.post('/proposals',json={'question':'x'}).status_code,401)
        h={**self.headers,'X-WebUI-User-ID':'other'}
        self.assertEqual(self.client.post('/proposals',headers=h,json={'question':'x'}).status_code,403)
        for data in [{'question':'x','sql':COUNT}, {'question':'x','approved':True}]:
            self.assertEqual(self.client.post('/proposals',headers=self.headers,json=data).status_code,422)
        self.assertFalse(self.oracle.executions)

    def test_unsigned_then_exact_once(self):
        p=self.propose(); self.assertFalse(self.oracle.executions)
        body=self.approval(p)
        bad={**body,'signature':'0'*64}
        self.assertEqual(self.client.post('/execute',headers=self.headers,json=bad).status_code,400)
        self.assertFalse(self.oracle.executions)
        response=self.client.post('/execute',headers=self.headers,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(response.json()['executed'])
        self.assertEqual(self.oracle.executions,[(p['sql'],'user')])
        self.assertEqual(self.client.post('/execute',headers=self.headers,json=body).status_code,400)
        self.assertEqual(len(self.oracle.executions),1)

    def test_no_sql_replacement(self):
        p=self.propose()
        self.assertEqual(self.client.post('/execute',headers=self.headers,
                         json={**self.approval(p),'sql':COUNT}).status_code,422)
        self.assertFalse(self.oracle.executions)

    def test_disabled(self):
        self.config['execution_enabled']=False; p=self.propose()
        self.assertEqual(self.client.post('/execute',headers=self.headers,json=self.approval(p)).status_code,403)
        self.assertFalse(self.oracle.executions)

    def test_failed_execution_consumed(self):
        p=self.propose(); self.oracle.fail=True
        response=self.client.post('/execute',headers=self.headers,json=self.approval(p))
        self.assertEqual(response.status_code,502); self.assertIsNone(response.json()['executed'])
        self.assertNotIn('private error',response.text)
        self.assertEqual(self.client.post('/execute',headers=self.headers,json=self.approval(p)).status_code,400)

    def test_bad_proposal_never_executed(self):
        self.oracle.sql='DELETE FROM WEBUI_MCP.DEMO_A_PROJECTS'
        response=self.client.post('/proposals',headers=self.headers,json={'question':'x'})
        self.assertEqual(response.status_code,400); self.assertFalse(self.oracle.executions)

    def test_plugin_confirmation_boundary(self):
        real_client=httpx.AsyncClient
        def client_factory(**kwargs):
            return real_client(transport=httpx.ASGITransport(app=self.app),**kwargs)
        tool=webui_tool.Tools()
        tool.valves=tool.Valves(API_KEY=self.config['api_key'],APPROVAL_KEY=self.config['approval_key'])
        metadata={'user_id':'user','chat_id':'chat','session_id':'socket','message_id':'message'}
        async def run(answer, meta=metadata):
            before=len(self.oracle.executions)
            async def confirm(event):
                self.assertEqual(before,len(self.oracle.executions))
                self.assertIn(canonical_sql(COUNT),event['data']['message'])
                self.assertEqual(event['type'],'confirmation')
                if isinstance(answer,Exception): raise answer
                return answer
            with patch.object(webui_tool.httpx,'AsyncClient',side_effect=client_factory):
                return json.loads(await tool.ask_demo_database('Count projects',
                    __user__={'id':'user','role':'admin'}, __metadata__=meta, __event_call__=confirm))
        for answer in [False,None,1,'approved',{'error':'disconnected'},TimeoutError()]:
            with self.subTest(answer=answer):
                result=asyncio.run(run(answer))
                self.assertIs(result['executed'],False); self.assertFalse(self.oracle.executions)
        for meta in [{}, {**metadata,'internal':True}, {**metadata,'chat_id':'channel:test'},
                     {**metadata,'user_id':'other'}, {**metadata,'session_id':None}]:
            self.assertEqual(asyncio.run(run(True,meta))['status'],'BLOCKED')
        self.config['execution_enabled']=False
        self.assertEqual(asyncio.run(run(True))['status'],'PREVIEW_ONLY')
        self.assertFalse(self.oracle.executions)
        self.config['execution_enabled']=True
        self.assertIs(asyncio.run(run(True))['executed'],True)
        self.assertEqual(len(self.oracle.executions),1)


class DatabaseTests(unittest.TestCase):
    def test_exact_decimals_and_value_limits(self):
        self.assertEqual(json_cell(decimal.Decimal('123456789012345678.01')),'123456789012345678.01')
        self.assertEqual(json_cell(datetime.date(2025,1,1)),'2025-01-01')
        for value in [object(),'a'*2001,1.234]:
            with self.assertRaises(Rejected): json_cell(value)

    def test_read_only_first_and_bounded_fetch(self):
        class Cursor:
            def __init__(self): self.statements=[]; self.description=[('N',)]
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def execute(self,sql): self.statements.append(sql)
            def fetchmany(self,n):
                self.limit=n
                return [(decimal.Decimal(i),) for i in range(101)]
        class Connection:
            def __init__(self): self.c=Cursor()
            def __enter__(self): return self
            def __exit__(self,*a): pass
            def cursor(self): return self.c
            def cancel(self): pass
        connection=Connection(); oracle=Oracle({})
        with patch.object(oracle,'connect',return_value=connection), patch.object(oracle,'check_executor') as check:
            result=oracle.execute(canonical_sql(COUNT),'user')
        check.assert_called_once_with(connection.c)
        self.assertEqual(connection.c.statements,['SET TRANSACTION READ ONLY',canonical_sql(COUNT)])
        self.assertEqual(connection.c.limit,101)
        self.assertEqual(len(result['rows']),100); self.assertTrue(result['truncated'])

    def test_executor_privilege_guard(self):
        class Cursor:
            def __init__(self,privs): self.privs=privs
            def execute(self,sql,*args): self.sql=sql
            def fetchone(self): return ('DEMO_SQL_EXECUTOR',) if self.sql=='SELECT USER FROM dual' else (0,)
            def fetchall(self):
                if 'session_privs' in self.sql: return [(p,) for p in self.privs]
                if 'user_tab_privs_recd' in self.sql: return [('WEBUI_MCP',t,'SELECT','NO') for t in TABLES]
                if 'all_tables' in self.sql: return [(t,) for t in TABLES]
                return []
        Oracle.check_executor(Cursor(['CREATE SESSION']))
        with self.assertRaises(Rejected): Oracle.check_executor(Cursor(['CREATE SESSION','CREATE TABLE']))

    def test_private_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'config.json'
            cfg=dict(api_key=secrets.token_hex(32),approval_key=secrets.token_hex(32),
                     allowed_user_ids=['user'],execution_enabled=False,dsn='demo_low',
                     proposal_password='fixture',executor_password='fixture',wallet_password='fixture')
            path.write_text(json.dumps(cfg)); path.chmod(0o600)
            self.assertEqual(load_config(path),cfg)
            path.chmod(0o644)
            with self.assertRaises(ValueError): load_config(path)


class InstallTests(unittest.TestCase):
    def test_compose_private_isolation(self):
        root=Path(__file__).resolve().parent
        compose=yaml.safe_load((root/'compose.approved-sql.yaml').read_text())
        self.assertEqual(set(compose['services']),{'sql-review'})
        service=compose['services']['sql-review']
        self.assertNotIn('ports',service); self.assertTrue(service['read_only'])
        self.assertEqual(service['cap_drop'],['ALL'])
        self.assertTrue(compose['networks']['existing-webui']['external'])
        self.assertEqual((root/'.dockerignore').read_text().splitlines()[0],'**')

    def test_local_configuration_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); archive=root/'fixture.zip'
            with zipfile.ZipFile(archive,'w') as out:
                out.writestr('ewallet.pem','synthetic non-key test bytes')
                out.writestr('tnsnames.ora','demo_low = (DESCRIPTION=fixture)')
            answers=['webui_network','test-user','demo_low',str(archive)]
            with patch.object(configure,'ROOT',root), patch.object(configure.os,'geteuid',return_value=0), \
                 patch.object(configure.os,'chown'), patch('builtins.input',side_effect=answers), \
                 patch.object(configure.getpass,'getpass',return_value='private fixture'), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                old_umask=configure.os.umask(0o077)
                try: configure.main()
                finally: configure.os.umask(old_umask)
                path=root/'private/sql-review.json'
                cfg=load_config(path)
                self.assertFalse(cfg['execution_enabled'])
                self.assertNotEqual(cfg['api_key'],cfg['approval_key'])
                self.assertNotIn(cfg['api_key'],output.getvalue())
                self.assertNotIn('private fixture',output.getvalue())
                before=path.read_bytes()
                with self.assertRaises(ValueError): configure.main()
                self.assertEqual(path.read_bytes(),before)

    def test_archive_path_and_alias_rejection(self):
        for entry,alias in [('../outside','demo_low'),('extra','missing_low')]:
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as folder:
                archive=Path(folder)/'fixture.zip'
                with zipfile.ZipFile(archive,'w') as out:
                    out.writestr(entry,'fixture')
                    out.writestr('ewallet.pem','fixture')
                    out.writestr('tnsnames.ora','demo_low = fixture')
                with self.assertRaises(ValueError): configure.wallet_members(archive,alias)

    def test_host_inventory_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'oci-gateway').mkdir()
            for name in ['compose.yaml','compose.oci.yaml','oci-gateway/app.py']:
                (root/name).write_text('synthetic fixture')
            response=['container-id',json.dumps({'image':'ghcr.io/open-webui/open-webui:v0.11.3',
                       'running':True,'networks':{'fixture-network':{}}}),'PASS']
            with patch.object(preflight,'run',side_effect=response) as call, contextlib.redirect_stdout(io.StringIO()):
                preflight.check(root)
            for args in call.call_args_list:
                cmd=args.args[0]
                self.assertFalse(set(cmd)&{'up','down','restart','build','rm','stop'})
                self.assertNotIn('.Config.Env',' '.join(cmd))

    def test_host_version_drift_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'oci-gateway').mkdir()
            for name in ['compose.yaml','compose.oci.yaml','oci-gateway/app.py']:
                (root/name).write_text('fixture')
            with patch.object(preflight,'run',side_effect=['id',json.dumps({'image':'other','running':True})]):
                with self.assertRaises(ValueError): preflight.check(root)


if __name__=='__main__':
    # These tests must not silently turn into live network/database/model tests.
    with patch('socket.create_connection',side_effect=AssertionError('Network disabled')):
        unittest.main()
