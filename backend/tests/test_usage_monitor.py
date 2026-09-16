import asyncio
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


class UsageMonitorTests(unittest.IsolatedAsyncioTestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('app.services.usage_monitor'), 'metadata-only reporter is missing')
        from app.services import usage_monitor
        return usage_monitor

    def test_hostname_missing_zero_cache_image(self):
        m = self.module()
        self.assertTrue(m.is_openlux('https://api.openlux.ai/v1'))
        for url in ['https://yunwu.ai/api.openlux.ai', 'https://api.openlux.ai.evil.test', 'invalid']:
            self.assertFalse(m.is_openlux(url))
        self.assertIsNone(m.parse_usage({})['inputTokens'])
        self.assertEqual(m.parse_usage({})['tokenBasis'], 'missing')
        zero = m.parse_usage({'usage': {'input_tokens': 0, 'output_tokens': 0, 'input_tokens_details': {'image_tokens': 0}}})
        self.assertEqual((zero['inputTokens'], zero['totalTokens'], zero['imageInputTokens']), (0, 0, 0))
        usage = m.parse_usage({'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'prompt_tokens_details': {'cached_tokens': 40, 'image_tokens': 30}, 'completion_tokens_details': {'reasoning_tokens': 5}}})
        self.assertEqual((usage['totalTokens'], usage['cachedInputTokens'], usage['imageInputTokens']), (120, 40, 30))
        gemini = m.parse_usage({'usageMetadata': {'promptTokenCount': 80, 'candidatesTokenCount': 5, 'thoughtsTokenCount': 3, 'promptTokensDetails': [{'modality': 'IMAGE', 'tokenCount': 50}]}})
        self.assertEqual((gemini['imageInputTokens'], gemini['outputTokens'], gemini['totalTokens']), (50, 8, 88))
        self.assertEqual(m.parse_usage({'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 99}})['totalTokens'], 15)

    async def test_delivery_requires_explicit_json_acknowledgement(self):
        import httpx
        m = self.module()
        real_client = httpx.AsyncClient
        for body in ['{"success":false}', '<html>Sign in</html>', '{}', '{"success":true}']:
            with patch('httpx.AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)), **kwargs)):
                accepted = await m._deliver({'requestId': 'test-id'}, {'url': 'https://main.test/api/sso/usage', 'secret': 'fake'})
                self.assertEqual(accepted, body == '{"success":true}')

    async def test_durable_retry_same_id_no_sensitive_content_and_user_isolation(self):
        m = self.module()
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'MAIN_APP_URL': 'https://main.test', 'USAGE_MONITOR_INTERNAL_SECRET': 'PRIVATE_SECRET', 'USAGE_MONITOR_OUTBOX_DIR': directory}), patch.object(m, '_deliver', AsyncMock(return_value=False)):
            client = SimpleNamespace(post=AsyncMock(return_value=SimpleNamespace(status_code=200, json=lambda: {'data': [{'b64_json': 'PRIVATE_IMAGE'}]})))
            await m.tracked_post(client, 'https://api.openlux.ai/v1', 'gpt-image-2', json={'prompt': 'PRIVATE_PROMPT'})
            with m.usage_user('employee-a'):
                await m.tracked_post(client, 'https://yunwu.ai/v1', 'openlux-model')
            self.assertEqual(list(Path(directory).glob('*.json')), [])

            async def generate(user):
                with m.usage_user(user):
                    await m.tracked_post(client, 'https://api.openlux.ai/v1', 'gpt-image-2', json={'prompt': 'PRIVATE_PROMPT'})
                    bad = SimpleNamespace(post=AsyncMock(side_effect=RuntimeError('PRIVATE_KEY')))
                    with self.assertRaises(RuntimeError):
                        await m.tracked_post(bad, 'https://api.openlux.ai/v1', 'gpt-image-2')
            await asyncio.gather(generate('employee-a'), generate('employee-b'))
            contents = [p.read_text() for p in Path(directory).glob('*.json')]
            self.assertEqual(len(contents), 8)
            self.assertTrue(all('PRIVATE_' not in text for text in contents))
            terminal = [json.loads(text) for text in contents if json.loads(text)['status'] != 'pending']
            self.assertEqual(len({e['requestId'] for e in terminal}), 4)
            self.assertEqual(sorted(e['userId'] for e in terminal), ['employee-a'] * 2 + ['employee-b'] * 2)
            self.assertTrue(all(e['inputTokens'] is None for e in terminal))
            delivered = []
            async def deliver(event, settings):
                delivered.append(event)
                return True
            with patch.object(m, '_deliver', deliver):
                await m.drain_usage_outbox()
            self.assertEqual(list(Path(directory).glob('*.json')), [])
            self.assertEqual({e['requestId'] for e in terminal}, {e['requestId'] for e in delivered})

    async def test_background_task_captures_owner_after_request_context_exits(self):
        m = self.module()
        seen = []
        async def work():
            seen.append(m.current_usage_user())
        with m.usage_user('employee-a'):
            task = m.capture_usage_task(work)
        with m.usage_user('employee-b'):
            await task()
            self.assertEqual(m.current_usage_user(), 'employee-b')
        self.assertEqual(seen, ['employee-a'])

    async def test_async_accepted_stays_pending(self):
        m = self.module()
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'MAIN_APP_URL': 'https://main.test', 'USAGE_MONITOR_INTERNAL_SECRET': 'secret', 'USAGE_MONITOR_OUTBOX_DIR': directory}), patch.object(m, '_deliver', AsyncMock(return_value=False)), m.usage_user('employee'):
            client = SimpleNamespace(post=AsyncMock(return_value=SimpleNamespace(status_code=202, json=lambda: {'id': 'task-id'})))
            await m.tracked_post(client, 'https://api.openlux.ai/v1', 'gpt-image-2')
            events = [json.loads(p.read_text()) for p in Path(directory).glob('*.json')]
            self.assertTrue(events and all(e['status'] == 'pending' for e in events))
