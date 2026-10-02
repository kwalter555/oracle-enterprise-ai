"""Durable, one-use approval ledger. Never takes replacement SQL at execution."""
import contextlib
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import time

from policy import Rejected, digest


def approval_message(p):
    return '\n'.join(['v1', p['id'], p['sha256'], p['user_id'], p['chat_id'], str(p['expires_at'])]).encode()


def sign(key, proposal):
    return hmac.new(key.encode(), approval_message(proposal), hashlib.sha256).hexdigest()


class Ledger:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        Path(path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL, chat_id TEXT NOT NULL,
                question TEXT, sql TEXT, sha256 TEXT NOT NULL,
                created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                state TEXT NOT NULL, finished_at INTEGER)''')
            db.execute('''CREATE TABLE IF NOT EXISTS audit (
                sequence INTEGER PRIMARY KEY, at INTEGER NOT NULL, proposal_id TEXT,
                user_id TEXT, chat_id TEXT, event TEXT NOT NULL)''')
        Path(path).chmod(0o600)

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level='IMMEDIATE')
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def event(self, db, p, event):
        db.execute('INSERT INTO audit(at,proposal_id,user_id,chat_id,event) VALUES(?,?,?,?,?)',
                   (int(self.clock()), p['id'], p['user_id'], p['chat_id'], event))

    def create(self, user_id, chat_id, question, sql):
        now = int(self.clock())
        p = dict(id=secrets.token_hex(24), user_id=user_id, chat_id=chat_id,
                 question=question, sql=sql, sha256=digest(sql), created_at=now,
                 expires_at=now+300, state='PENDING')
        with self.db() as db:
            # Keep hashes/events, not old question/SQL bodies. Prune after 30 days.
            db.execute("UPDATE proposals SET sql=NULL, question=NULL, state=CASE WHEN state='PENDING' THEN 'EXPIRED' ELSE state END WHERE expires_at<?", (now,))
            db.execute('DELETE FROM audit WHERE at<?', (now-30*86400,))
            db.execute('DELETE FROM proposals WHERE created_at<?', (now-30*86400,))
            count = db.execute('SELECT COUNT(*) FROM proposals WHERE user_id=? AND created_at>?',
                               (user_id, now-3600)).fetchone()[0]
            if count >= 30:
                raise Rejected('Hourly proposal limit reached.')
            db.execute('INSERT INTO proposals(id,user_id,chat_id,question,sql,sha256,created_at,expires_at,state) VALUES(:id,:user_id,:chat_id,:question,:sql,:sha256,:created_at,:expires_at,:state)', p)
            self.event(db, p, 'PROPOSED')
        return p

    def claim(self, proposal_id, sql_hash, user_id, chat_id, signature, key):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM proposals WHERE id=?', (proposal_id,)).fetchone()
            if not row:
                raise Rejected('Unknown or expired proposal.')
            p = dict(row)
            if p['user_id'] != user_id or p['chat_id'] != chat_id:
                raise Rejected('Approval belongs to a different user or chat.')
            if p['state'] != 'PENDING' or p['expires_at'] <= self.clock() or not p['sql']:
                raise Rejected('Proposal expired, denied, or already consumed. Ask again.')
            if not hmac.compare_digest(sql_hash, p['sha256']) or digest(p['sql']) != p['sha256']:
                raise Rejected('SQL fingerprint mismatch.')
            if not hmac.compare_digest(signature, sign(key, p)):
                raise Rejected('A signed UI approval is required.')
            db.execute("UPDATE proposals SET state='EXECUTING' WHERE id=?", (proposal_id,))
            self.event(db, p, 'APPROVED_AND_CLAIMED')
        # Claim commits before any Oracle call. Crashes/errors never reopen it.
        return p

    def finish(self, p, state):
        if state not in {'SUCCEEDED', 'FAILED', 'DENIED'}:
            raise ValueError('Invalid terminal state')
        with self.db() as db:
            expected = 'PENDING' if state == 'DENIED' else 'EXECUTING'
            n = db.execute('UPDATE proposals SET state=?,finished_at=? WHERE id=? AND user_id=? AND chat_id=? AND state=?',
                           (state, int(self.clock()), p['id'], p['user_id'], p['chat_id'], expected)).rowcount
            if n:
                self.event(db, p, state)

    def reserve_generation(self, user_id, chat_id):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            count = db.execute("SELECT COUNT(*) FROM audit WHERE user_id=? AND at>? AND event='GENERATION_STARTED'",
                               (user_id, int(self.clock())-3600)).fetchone()[0]
            if count >= 30:
                raise Rejected('Hourly proposal limit reached.')
            self.event(db, dict(id=None, user_id=user_id, chat_id=chat_id), 'GENERATION_STARTED')
