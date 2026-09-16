import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import ImageGenerationSettings, TextAnalysisSettings
from app.services import usage_monitor as usage
from app.services.app_session import AppSessionUnauthorizedError, build_session_cookie_value
from app.services.image_model import call_image_model, call_image_edit_model
from app.services.text_model import call_text_model


class ProviderUsageTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_image_edit_and_actual_retries_report_separate_attempts(self):
        real_client = httpx.AsyncClient
        requests = []
        def upstream(request):
            requests.append(request)
            return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}], 'data': [{'url': 'https://image.test/result.png'}], 'usage': {'input_tokens': 8, 'output_tokens': 2, 'input_tokens_details': {'image_tokens': 6}}})
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'MAIN_APP_URL': 'https://main.test', 'USAGE_MONITOR_INTERNAL_SECRET': 'secret', 'USAGE_MONITOR_OUTBOX_DIR': directory}), patch.object(usage, '_deliver', AsyncMock(return_value=False)), patch('httpx.AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(upstream), **kwargs)), usage.usage_user('employee-a'):
            text = TextAnalysisSettings('fake', 'https://api.openlux.ai/v1', 'gemini', 10, 0.1)
            image = ImageGenerationSettings('fake', 'https://api.openlux.ai/v1', 'gpt-image-2', '1024x1024', 1)
            await call_text_model(text, [{'role': 'user', 'content': 'private prompt'}])
            await call_image_model(image, 'private prompt')
            await call_image_edit_model(image, 'private prompt', b'fake image')
            await call_image_model(image, 'private prompt')
            terminal = [json.loads(p.read_text()) for p in Path(directory).glob('*-1.json')]
            self.assertEqual(len(requests), 4)
            self.assertEqual(len(terminal), 4)
            self.assertEqual(len({e['requestId'] for e in terminal}), 4)
            self.assertTrue(all(e['userId'] == 'employee-a' and e['imageInputTokens'] == 6 for e in terminal))


class SessionUsageTests(unittest.TestCase):
    def test_deferred_style_jobs_keep_each_signed_owner_after_request_cleanup(self):
        from app.routers import projects
        from starlette.background import BackgroundTasks

        app = FastAPI()
        app.include_router(projects.router)
        deferred = []
        seen = []
        job_ids = []

        def defer(self, work, *args, **kwargs):
            deferred.append((work, args, kwargs))

        async def style_work(*args, **kwargs):
            seen.append(usage.current_usage_user())
            return {'source': 'test'}

        async def run_deferred():
            with usage.usage_user('unrelated-request'):
                for work, args, kwargs in deferred:
                    await work(*args, **kwargs)

        with patch.dict(os.environ, {'MAIN_APP_URL': 'https://main.test', 'REQUIRE_MAIN_APP_SSO': 'true', 'DETAIL_IMAGE_AGENT_SESSION_SECRET': 'test-only-secret'}), patch.object(BackgroundTasks, 'add_task', defer), patch.object(projects, 'plan_custom_style', style_work), patch.object(projects, 'analyze_style_reference', style_work), patch.object(projects, 'generate_custom_style_sample', style_work):
            with TestClient(app) as client:
                for user_id in ['employee-a', 'employee-b']:
                    cookie = build_session_cookie_value(token='verified-token', user={'id': user_id}, main_app_url='https://main.test')
                    client.cookies.set('detail_image_agent_session', cookie)
                    for route in ['plan-style', 'analyze-style-reference', 'plan-style-sample']:
                        response = client.post(f'/api/projects/{route}/jobs', json={'style': {}, 'userId': 'attacker'})
                        self.assertEqual(response.status_code, 200)
                        job_ids.append(response.json()['job_id'])
            self.assertIsNone(usage.current_usage_user())
            asyncio.run(run_deferred())

        self.assertEqual(seen, ['employee-a'] * 3 + ['employee-b'] * 3)
        self.assertTrue(all(projects.STYLE_JOBS[job_id]['status'] == 'done' for job_id in job_ids))

    def test_signed_identity_ignores_body_identity_and_background_task_preserves_owner(self):
        from app.routers import projects
        app = FastAPI()
        app.include_router(projects.router)
        seen = []
        async def analyze(*args, **kwargs):
            seen.append(usage.current_usage_user())
            return {'source': 'test'}
        async def job(*args, **kwargs):
            seen.append(usage.current_usage_user())
        with patch.dict(os.environ, {'MAIN_APP_URL': 'https://main.test', 'REQUIRE_MAIN_APP_SSO': 'true', 'DETAIL_IMAGE_AGENT_SESSION_SECRET': 'test-only-secret'}), patch.object(projects, 'analyze_product_materials', analyze), patch.object(projects, 'run_analysis_job', job), TestClient(app) as client:
            for user_id in ['employee-a', 'employee-b']:
                cookie = build_session_cookie_value(token='verified-token', user={'id': user_id}, main_app_url='https://main.test')
                client.cookies.set('detail_image_agent_session', cookie)
                response = client.post('/api/projects/analyze', json={'raw_text': 'test', 'userId': 'attacker'})
                self.assertEqual(response.status_code, 200)
                response = client.post('/api/projects/analyze-materials/jobs', json={'materials': [], 'userId': 'attacker'})
                self.assertEqual(response.status_code, 200)
            client.cookies.clear()
            client.cookies.set('detail_image_agent_session', 'forged.invalid')
            with self.assertRaises(AppSessionUnauthorizedError):
                client.post('/api/projects/analyze', json={'raw_text': 'test', 'userId': 'attacker'})
        self.assertEqual(seen, ['employee-a', 'employee-a', 'employee-b', 'employee-b'])
