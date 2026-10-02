"""Two separate database identities; no model-generated SQL in proposal account."""
import contextlib
import datetime
import decimal
import json
import threading
import time
import oracledb

from policy import TABLES, Rejected

oracledb.defaults.fetch_decimals = True
MAX_ROWS = 100
MAX_BYTES = 64000


@contextlib.contextmanager
def deadline(connection, seconds):
    end = time.monotonic() + seconds
    def cancel():
        try:
            connection.cancel()
        except Exception:
            pass
    timer = threading.Timer(seconds, cancel)
    timer.daemon = True
    timer.start()
    def check():
        if time.monotonic() >= end:
            raise TimeoutError('Database operation exceeded its deadline.')
    try:
        yield check
    finally:
        timer.cancel()
        timer.join(timeout=1)


def json_cell(value):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)  # Preserve NUMBER precision; explicitly documented.
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, str) and len(value) <= 2000:
        return value
    raise Rejected('Unsupported/oversized result value; no partial answer returned.')


class Oracle:
    def __init__(self, config):
        self.config = config

    def connect(self, execution=False):
        return oracledb.connect(
            user='DEMO_SQL_EXECUTOR' if execution else 'DEMO_AI_READER',
            password=self.config['executor_password' if execution else 'proposal_password'],
            dsn=self.config['dsn'], config_dir='/run/wallet', wallet_location='/run/wallet',
            wallet_password=self.config['wallet_password'],
            ssl_server_dn_match=True, tcp_connect_timeout=10, retry_count=0,
        )

    def propose(self, question):
        with self.connect() as connection:
            connection.call_timeout = 60000
            with deadline(connection, 60) as check, connection.cursor() as cursor:
                # Function name fixed in code; question is a bound value.
                lob = cursor.callfunc('DEMO_AI_READER.DEMO_AI_SQL_PROPOSAL',
                                      oracledb.DB_TYPE_CLOB, [question])
                check()
                if lob is None or lob.size() > 24000:
                    raise Rejected('Proposal function returned an invalid response.')
                data = json.loads(lob.read())
                check()
                if data.get('status') != 'PROPOSAL_ONLY' or data.get('executed') is not False:
                    raise Rejected('Proposal function did not return unexecuted SQL.')
                return data['sql']

    @staticmethod
    def check_executor(cursor):
        cursor.execute('SELECT USER FROM dual')
        if cursor.fetchone()[0] != 'DEMO_SQL_EXECUTOR':
            raise Rejected('Unexpected database execution identity.')
        cursor.execute('SELECT privilege FROM session_privs')
        if {r[0] for r in cursor.fetchall()} != {'CREATE SESSION'}:
            raise Rejected('Executor has unexpected effective system privileges.')
        cursor.execute('SELECT role FROM session_roles')
        if cursor.fetchall():
            raise Rejected('Executor must not have roles.')
        cursor.execute('SELECT COUNT(*) FROM user_objects')
        if cursor.fetchone()[0]:
            raise Rejected('Executor must not own schema objects.')
        cursor.execute('SELECT owner,table_name,privilege,grantable FROM user_tab_privs_recd')
        expected = {('WEBUI_MCP', name, 'SELECT', 'NO') for name in TABLES}
        if set(cursor.fetchall()) != expected:
            raise Rejected('Executor must have only the five direct demo SELECT grants.')
        cursor.execute('SELECT COUNT(*) FROM user_col_privs_recd')
        if cursor.fetchone()[0]:
            raise Rejected('Executor must not have extra column grants.')
        names = ','.join(':'+str(i+1) for i in range(len(TABLES)))
        binds = list(TABLES)
        cursor.execute("SELECT table_name FROM all_tables WHERE owner='WEBUI_MCP' AND table_name IN ("+names+')', binds)
        if {r[0] for r in cursor.fetchall()} != set(TABLES):
            raise Rejected('All five objects must remain physical demo tables, not views/synonyms.')
        cursor.execute("SELECT COUNT(*) FROM all_tab_cols WHERE owner='WEBUI_MCP' AND table_name IN ("+names+") AND (virtual_column='YES' OR data_type NOT IN ('VARCHAR2','CHAR','NUMBER','DATE'))", binds)
        if cursor.fetchone()[0]:
            raise Rejected('Only the original scalar demo columns are supported.')
        cursor.execute("SELECT COUNT(*) FROM all_policies WHERE object_owner='WEBUI_MCP' AND object_name IN ("+names+')', binds)
        if cursor.fetchone()[0]:
            raise Rejected('VPD policies require a separate security review; pilot blocked.')

    def preflight(self):
        # Fixed metadata checks only. Does not call Select AI or execute generated SQL.
        with self.connect(execution=True) as connection:
            connection.call_timeout = 15000
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                self.check_executor(cursor)
        with self.connect() as connection:
            connection.call_timeout = 15000
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM user_objects WHERE object_name='DEMO_AI_SQL_PROPOSAL' AND object_type='FUNCTION' AND status='VALID'")
                if cursor.fetchone()[0] != 1:
                    raise Rejected('Reader proposal function is not VALID.')
        return {'database_metadata_checks': 'PASS', 'model_called': False}

    def execute(self, sql, actor):
        with self.connect(execution=True) as connection:
            connection.call_timeout = 15000
            connection.client_identifier = actor[:64]
            connection.module = 'WEBUI_APPROVED_SQL'
            with deadline(connection, 15) as check, connection.cursor() as cursor:
                cursor.arraysize = 101
                cursor.prefetchrows = 101
                # First statement in a new, unpooled session. No autocommit.
                cursor.execute('SET TRANSACTION READ ONLY')
                self.check_executor(cursor)
                check()
                # Exactly the canonical SQL shown to the human; never a new model answer.
                cursor.execute(sql)
                check()
                if cursor.description is None or len(cursor.description) > 20:
                    raise Rejected('Unexpected query result shape.')
                columns = [d[0] for d in cursor.description]
                if len(set(columns)) != len(columns):
                    raise Rejected('Result columns need unique names/aliases.')
                rows = cursor.fetchmany(MAX_ROWS + 1)
                check()
                result = {'columns': columns,
                          'rows': [[json_cell(v) for v in row] for row in rows[:MAX_ROWS]],
                          'row_count_returned': min(len(rows), MAX_ROWS),
                          'truncated': len(rows) > MAX_ROWS,
                          'numeric_encoding': 'Oracle NUMBER values may be decimal strings.'}
                if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_BYTES:
                    raise Rejected('Result exceeds 64 KB; ask for a smaller aggregate.')
                check()
                return result
