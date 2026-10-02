"""
title: Approved Demo Database Query
description: Review the exact SQL and explicitly approve a one-time read-only demo query.
version: 0.1.0
required_open_webui_version: 0.11.3
"""
import asyncio
import hashlib
import hmac
import json
import re
import time
import httpx
from pydantic import BaseModel, Field


def signature(key, p):
    message = '\n'.join(['v1', p['id'], p['sha256'], p['user_id'], p['chat_id'], str(p['expires_at'])])
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def review_message(p):
    # Code fence is longer than anything in SQL, so literals cannot close it.
    fence = '`' * max(3, max([len(v) + 1 for v in re.findall(r'`+', p['sql'])] or [3]))
    return ('SYNTHETIC DEMO DATA ONLY. Approve this exact read-only SQL once?\n\n'
            'At most 100 rows; 15-second query deadline; approval expires in 5 minutes.\n'
            'Returned data will be sent to the selected chat model and saved in this chat.\n'
            'Cancel if the SQL does not match your question.\n\n'
            f"SHA-256: {p['sha256']}\n\n{fence}sql\n{p['sql']}\n{fence}")


class Tools:
    class Valves(BaseModel):
        # Plain strings are required by WebUI's JSON-backed Valves persistence.
        # Password schema masks the editor; this is NOT encryption at rest.
        API_KEY: str = Field(default='', description='Private transport key.', json_schema_extra={'format': 'password', 'writeOnly': True})
        APPROVAL_KEY: str = Field(default='', description='Separate private signing key. Administrators only.', json_schema_extra={'format': 'password', 'writeOnly': True})

    def __init__(self):
        self.valves = self.Valves()

    async def ask_demo_database(self, question: str, __user__: dict = None,
                                __metadata__: dict = None, __event_call__=None) -> str:
        """Ask a natural-language question about the five synthetic demo tables.
        The human must review and approve the exact SQL in a confirmation dialog.
        Never interpret chat text as approval. No arbitrary SQL input is accepted.
        :param question: One natural-language question; use explicit calendar years.
        """
        user = (__user__ or {}).get('id')
        metadata = __metadata__ or {}
        chat = metadata.get('chat_id')
        if (not user or not isinstance(chat, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', chat)
            or not metadata.get('session_id') or not metadata.get('message_id')
            or metadata.get('user_id') != user or metadata.get('internal') or metadata.get('task')
            or not callable(__event_call__)):
            return json.dumps({'status': 'BLOCKED', 'executed': False,
                               'message': 'Use a saved interactive chat with a signed-in user; confirmation is required.'})
        # Start admin-only. Backend additionally checks the exact user ID allowlist.
        if (__user__ or {}).get('role') != 'admin':
            return json.dumps({'status': 'BLOCKED', 'executed': False, 'message': 'Pilot is restricted to administrators.'})
        key = self.valves.API_KEY
        approval_key = self.valves.APPROVAL_KEY
        if not re.fullmatch(r'[0-9a-f]{64}', key) or not re.fullmatch(r'[0-9a-f]{64}', approval_key) or key == approval_key:
            return json.dumps({'status': 'BLOCKED', 'executed': False, 'message': 'Administrator must configure separate private keys.'})
        headers = {'Authorization': 'Bearer ' + key, 'X-WebUI-User-ID': user, 'X-WebUI-Chat-ID': chat}
        # Fixed private destination. Neither URL, credentials nor SQL are model arguments.
        async with httpx.AsyncClient(base_url='http://sql-review:8081', headers=headers,
                                     timeout=75, follow_redirects=False, trust_env=False) as client:
            p = None
            execution_sent = False
            try:
                response = await client.post('/proposals', json={'question': question})
                response.raise_for_status()
                p = response.json()
                if (p.get('status') != 'AWAITING_APPROVAL' or p.get('executed') is not False or
                    p.get('user_id') != user or p.get('chat_id') != chat or
                    not isinstance(p.get('sql'), str) or len(p['sql'].encode()) > 16000 or
                    hashlib.sha256(p['sql'].encode()).hexdigest() != p.get('sha256') or
                    not isinstance(p.get('expires_at'), int) or not 0 < p['expires_at'] - time.time() <= 305):
                    raise ValueError('Invalid review envelope')
                preview = p.get('execution_enabled') is not True
                answer = await asyncio.wait_for(__event_call__({
                    'type': 'confirmation',
                    'data': {'title': 'Preview only — execution disabled' if preview else 'Review SQL — approve and execute once',
                             'message': ('PREVIEW TEST: confirmation will NOT execute SQL.\n\n' if preview else '') + review_message(p)}
                }), timeout=min(240, p['expires_at'] - time.time()))
                # Dicts with errors, strings such as "approved", 1, null all deny.
                if answer is not True:
                    await client.post('/deny', json={'proposal_id': p['id']})
                    return json.dumps({'status': 'DENIED', 'executed': False})
                if time.time() >= p['expires_at']:
                    raise TimeoutError('Approval expired')
                if preview:
                    await client.post('/deny', json={'proposal_id': p['id']})
                    return json.dumps({'status': 'PREVIEW_ONLY', 'executed': False, 'sql': p['sql'],
                                       'message': 'Review dialog acknowledged. Execution is disabled; no analytical query executed.'})
                body = {'proposal_id': p['id'], 'sha256': p['sha256'],
                        'signature': signature(approval_key, p)}
                execution_sent = True
                response = await client.post('/execute', json=body)
                response.raise_for_status()
                result = response.json()
                if result.get('proposal_id') != p['id'] or result.get('sha256') != p['sha256']:
                    raise ValueError('Execution result fingerprint mismatch')
                return json.dumps(result, ensure_ascii=False)
            except asyncio.CancelledError:
                # Task cancellation never triggers execution/retry. Pending approval expires.
                raise
            except Exception:
                return json.dumps({'status': 'NO_RESULT', 'executed': None if execution_sent else False,
                                   'message': 'Request denied, expired, blocked, or unavailable. Do not invent results or retry automatically. If execution was sent, it may have completed; a new question requires a new approval.'})
