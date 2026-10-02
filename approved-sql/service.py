"""Private HTTP bridge for the trusted Open WebUI tool, not a public MCP executor."""
import hmac
import json
import logging
import os
from pathlib import Path
import re
import stat
import threading

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from database import Oracle
from ledger import Ledger
from policy import Rejected, canonical_sql, digest, validate_question


def diagnostic(phase, error):
    # Deliberately omit raw exceptions: they can contain SQL or connection data.
    detail = error.args[0] if error.args else None
    code = getattr(detail, 'full_code', '')
    code = code if isinstance(code,str) and re.fullmatch(r'[A-Z]+-[0-9]+',code) else ''
    logging.getLogger('approved_sql').error('%s: %s %s', phase, type(error).__name__, code)


def load_config(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Configuration must be a regular private file, mode 0600 or 0400.')
    config = json.loads(path.read_text())
    for key in ['api_key', 'approval_key']:
        if not re.fullmatch(r'[0-9a-f]{64}', config.get(key, '')):
            raise ValueError('Configure two independent random keys.')
    if hmac.compare_digest(config['api_key'], config['approval_key']):
        raise ValueError('Approval and transport keys must differ.')
    if not isinstance(config.get('execution_enabled'), bool):
        raise ValueError('execution_enabled must be a boolean.')
    users = config.get('allowed_user_ids')
    if not isinstance(users, list) or not users or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', u) for u in users):
        raise ValueError('Configure explicit permitted WebUI user IDs; no wildcard.')
    if not re.fullmatch(r'[A-Za-z0-9_]+_low', config.get('dsn', '')):
        raise ValueError('Use a low-service wallet alias, not an arbitrary connection string.')
    for key in ['proposal_password', 'executor_password', 'wallet_password']:
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError('Configure your own database and wallet passwords locally.')
    return config


class Ask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=2000)


class Approval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    proposal_id: str = Field(pattern=r'^[0-9a-f]{48}$')
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    signature: str = Field(pattern=r'^[0-9a-f]{64}$')


class Denial(BaseModel):
    model_config = ConfigDict(extra='forbid')
    proposal_id: str = Field(pattern=r'^[0-9a-f]{48}$')


def create_app(config, oracle, ledger):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    # Single database operation at a time; no queued model bursts/retries.
    operation = threading.Lock()

    @app.middleware('http')
    async def guard(request: Request, call_next):
        if request.url.path == '/health' and request.method == 'GET':
            return await call_next(request)
        token = request.headers.get('authorization', '')
        if not hmac.compare_digest(token, 'Bearer ' + config['api_key']):
            return JSONResponse({'detail': 'Unauthorized'}, status_code=401)
        user = request.headers.get('x-webui-user-id', '')
        chat = request.headers.get('x-webui-chat-id', '')
        if user not in config['allowed_user_ids'] or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', chat):
            return JSONResponse({'detail': 'User/chat is not authorized'}, status_code=403)
        if request.method == 'POST':
            length = request.headers.get('content-length', '')
            if request.headers.get('transfer-encoding') or not length.isdigit() or int(length) > 24000:
                return JSONResponse({'detail': 'Bounded JSON body required'}, status_code=413)
        request.state.user, request.state.chat = user, chat
        return await call_next(request)

    @app.exception_handler(Rejected)
    async def rejected(request, error):
        return JSONResponse({'detail': str(error), 'status': 'BLOCKED'}, status_code=400)

    @app.get('/health')
    def health():
        return {'service': 'approved-sql', 'version': '0.1.0',
                'execution_enabled': config['execution_enabled'], 'database_tested': False}

    @app.post('/proposals')
    def proposal(body: Ask, request: Request):
        question = validate_question(body.question)
        if not operation.acquire(blocking=False):
            raise HTTPException(429, 'Service busy; no automatic retry.')
        try:
            ledger.reserve_generation(request.state.user, request.state.chat)
            try:
                sql = canonical_sql(oracle.propose(question))
            except Rejected:
                raise
            except Exception as error:
                diagnostic('proposal', error)
                raise HTTPException(502, 'Proposal unavailable. No analytical SQL executed; inspect private service diagnostics.') from None
            p = ledger.create(request.state.user, request.state.chat, question, sql)
            return {**p, 'executed': False, 'status': 'AWAITING_APPROVAL',
                    'data_origin': 'SYNTHETIC_DEMO', 'data_snapshot': '2026-09-24',
                    'max_rows': 100, 'query_deadline_seconds': 15,
                    'execution_enabled': config['execution_enabled']}
        finally:
            operation.release()

    @app.post('/deny')
    def deny(body: Denial, request: Request):
        ledger.finish(dict(id=body.proposal_id, user_id=request.state.user, chat_id=request.state.chat), 'DENIED')
        return {'status': 'DENIED', 'executed': False}

    @app.post('/execute')
    def execute(body: Approval, request: Request):
        if not config['execution_enabled']:
            raise HTTPException(403, 'Execution is disabled by the administrator.')
        if not operation.acquire(blocking=False):
            raise HTTPException(429, 'Service busy; approval is not consumed. No automatic retry.')
        try:
            p = ledger.claim(body.proposal_id, body.sha256, request.state.user,
                             request.state.chat, body.signature, config['approval_key'])
            try:
                # Re-check the immutable, stored SQL against current policy.
                if canonical_sql(p['sql']) != p['sql'] or digest(p['sql']) != p['sha256']:
                    raise Rejected('Policy/fingerprint changed; obtain a new proposal.')
                result = oracle.execute(p['sql'], p['user_id'])
                ledger.finish(p, 'SUCCEEDED')
                return {'status': 'SUCCEEDED', 'executed': True, 'proposal_id': p['id'],
                        'sha256': p['sha256'], 'data_origin': 'SYNTHETIC_DEMO',
                        'data_snapshot': '2026-09-24', **result}
            except Exception as error:
                diagnostic('execution', error)
                ledger.finish(p, 'FAILED')
                # Statement may have begun/completed even if fetching/audit failed.
                return JSONResponse({'status': 'EXECUTION_FAILED', 'executed': None,
                                     'proposal_id': p['id'], 'sha256': p['sha256'],
                                     'message': 'No usable result. Approval consumed. Never retry automatically; request a new proposal and approval.'}, status_code=502)
        finally:
            operation.release()

    return app


def production_app():
    os.umask(0o077)
    config = load_config('/run/secrets/sql-review.json')
    return create_app(config, Oracle(config), Ledger('/state/approvals.sqlite'))
