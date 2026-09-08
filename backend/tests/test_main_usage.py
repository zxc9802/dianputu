import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from app.services import main_usage as usage


class UsageReportingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'MAIN_APP_URL': 'https://main.test', 'USAGE_TOOL': 'dianputu',
            'USAGE_REPORT_SECRET': 'test-only-secret', 'USAGE_OUTBOX_DIR': self.temp.name})
        self.env.start()

    async def asyncTearDown(self):
        self.env.stop()
        self.temp.cleanup()

    async def test_identity_counts_and_private_content(self):
        calls = []
        async def upstream(request):
            calls.append(request)
            return httpx.Response(200, json={'usage': {'prompt_tokens': 20, 'completion_tokens': 5,
                'total_tokens': 25, 'prompt_tokens_details': {'cached_tokens': 4}}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
            with self.assertRaisesRegex(RuntimeError, 'authenticated employee'):
                await usage.metered_post(client, 'https://provider.test/v1/chat/completions')
            self.assertEqual(len(calls), 0)
            async def generate(user):
                token = usage.usage_user.set(user)
                try:
                    response = await usage.metered_post(client, 'https://provider.test/v1/chat/completions',
                        json={'model': 'test', 'messages': [{'content': 'PRIVATE PROMPT'}]})
                    self.assertEqual(response.status_code, 200)
                finally:
                    usage.usage_user.reset(token)
            await asyncio.gather(generate('employee-a'), generate('employee-b'))
        events = [json.loads(p.read_text()) for p in Path(self.temp.name).glob('*.json')]
        self.assertEqual({e['userId'] for e in events}, {'employee-a', 'employee-b'})
        self.assertEqual(events[0]['totalTokens'], 25)
        self.assertEqual(events[0]['cachedInputTokens'], 4)
        self.assertNotIn('PRIVATE PROMPT', json.dumps(events))
        self.assertEqual(len(set(e['requestId'] for e in events)), 2)

    async def test_failure_unknown_and_retry_same_id(self):
        token = usage.usage_user.set('employee-a')
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(429, json={'error': 'busy'}))) as client:
                await usage.metered_post(client, 'https://provider.test/v1/images/generations', json={'model': 'image'})
        finally:
            usage.usage_user.reset(token)
        file = next(Path(self.temp.name).glob('*.json'))
        event = json.loads(file.read_text())
        self.assertEqual(event['status'], 'failed')
        self.assertIsNone(event['totalTokens'])
        self.assertEqual(event['tokenBasis'], 'missing')
        received = []
        reject = True
        def main(request):
            received.append(json.loads(request.content))
            self.assertEqual(request.headers['x-usage-secret'], 'test-only-secret')
            return httpx.Response(503 if reject else 200, json={'success': not reject})
        original_client = httpx.AsyncClient
        with patch.object(usage.httpx, 'AsyncClient', side_effect=lambda **kw: original_client(transport=httpx.MockTransport(main), **kw)):
            with self.assertRaises(RuntimeError):
                await usage.flush_usage()
            self.assertTrue(file.exists())
            reject = False
            await usage.flush_usage()
        self.assertFalse(file.exists())
        self.assertEqual(received[0]['requestId'], received[1]['requestId'])

    def test_gemini_and_anthropic_normalization(self):
        gemini = usage.token_usage({'usageMetadata': {'promptTokenCount': 20, 'candidatesTokenCount': 4, 'thoughtsTokenCount': 3, 'totalTokenCount': 27}})
        self.assertEqual(gemini['outputTokens'], 7)
        anthropic = usage.token_usage({'usage': {'input_tokens': 10, 'cache_read_input_tokens': 5, 'cache_creation_input_tokens': 2, 'output_tokens': 3}})
        self.assertEqual(anthropic['inputTokens'], 17)
        self.assertEqual(anthropic['totalTokens'], 20)

    async def test_signed_session_scopes_background_tasks_and_rejects_spoofing(self):
        import time
        from fastapi import BackgroundTasks
        from app.main import create_app
        from app.services.app_session import build_session_cookie_value, get_session_cookie_name
        env = {'REQUIRE_MAIN_APP_SSO': 'true', 'DETAIL_IMAGE_AGENT_SESSION_SECRET': 'test-signing-secret'}
        with patch.dict(os.environ, env):
            app = create_app()
            owners = []
            async def background():
                owners.append(usage.usage_user.get())
            @app.post('/api/projects/usage-test')
            async def endpoint(tasks: BackgroundTasks):
                tasks.add_task(background)
                return {'owner': usage.usage_user.get()}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://tool.test') as client:
                denied = await client.post('/api/projects/usage-test', json={'userId': 'spoofed'})
                self.assertEqual(denied.status_code, 401)
                cookie = build_session_cookie_value(token='main-token', user={'id': 'signed-employee'},
                    main_app_url='https://main.test', expires_at_ms=int(time.time() * 1000) + 60000)
                accepted = await client.post('/api/projects/usage-test', json={'userId': 'spoofed'},
                    headers={'cookie': get_session_cookie_name() + '=' + cookie})
                self.assertEqual(accepted.status_code, 200)
                self.assertEqual(accepted.json()['owner'], 'signed-employee')
                self.assertEqual(owners, ['signed-employee'])
