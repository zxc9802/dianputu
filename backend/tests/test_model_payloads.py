import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.core.config import ImageGenerationSettings, get_model_settings
from app.services.image_model import build_chat_image_payload, build_image_generation_payload, call_image_model, extract_image_urls_from_response
from app.services.text_model import build_chat_completion_payload


class ModelPayloadTests(unittest.TestCase):
    def test_text_model_defaults_use_large_token_budget(self):
        settings = get_model_settings({})

        self.assertEqual(settings.text.model, "gemini-3.1-pro-preview")
        self.assertEqual(settings.text.max_tokens, 4096)
        self.assertFalse(hasattr(settings, "fallback_text"))
        self.assertEqual(settings.image.label, "gpt image2(1)")
        self.assertEqual(settings.image.base_url, "https://api.apiyi.com/v1")
        self.assertEqual(settings.image.model, "gpt-image-2-vip")
        self.assertEqual(settings.image.size, "2048x2048")
        self.assertEqual(settings.image.n, 0)
        self.assertEqual(settings.image.quality, "")
        self.assertEqual(settings.image.response_format, "b64_json")
        self.assertEqual(settings.fallback_image.size, "2048x2048")
        self.assertEqual(settings.fallback_image.label, "gpt image2(2)")
        self.assertEqual(settings.fallback_image.base_url, "https://api-xai.ainaibahub.com/v1")
        self.assertEqual(settings.fallback_image.model, "gpt-image-2")
        self.assertEqual(settings.fallback_image.response_format, "b64_json")
        self.assertEqual(settings.default_image_option_id, "fallback")
        self.assertIn("fallback", settings.image_options)
        self.assertIn("gemini_flash_image", settings.image_options)
        self.assertEqual(list(settings.image_options)[:2], ["primary", "fallback"])
        self.assertEqual(settings.image_options["gemini_flash_image"].model, "gemini-3.1-flash-image-preview")
        self.assertEqual(settings.image_options["gemini_flash_image"].base_url, "https://www.shanbaob.net/v1")
        self.assertEqual(settings.image_options["gemini_flash_image"].endpoint_path, "/chat/completions")
        self.assertEqual(settings.image_options["gemini_flash_image"].size, "2048x2048")

    def test_primary_image_can_include_backup_retry_api(self):
        settings = get_model_settings(
            {
                "IMAGE_GENERATION_BACKUP_API_KEY": "backup-key",
            }
        )

        self.assertEqual(settings.image.retry_groups, 5)
        self.assertEqual(len(settings.image.retry_alternates), 1)
        backup = settings.image.retry_alternates[0]
        self.assertEqual(backup.id, "primary_backup")
        self.assertEqual(backup.label, "gpt image2(1) backup")
        self.assertEqual(backup.api_key, "backup-key")
        self.assertEqual(backup.base_url, "https://api-xai.ainaibahub.com/v1")
        self.assertEqual(backup.endpoint_path, "/images/generations")
        self.assertEqual(backup.model, "gpt-image-2")
        self.assertEqual(backup.size, "2048x2048")
        self.assertEqual(backup.n, 1)
        self.assertEqual(backup.response_format, "b64_json")
        self.assertNotIn("primary_backup", settings.image_options)

    def test_fallback_image_can_include_backup_retry_api(self):
        settings = get_model_settings(
            {
                "FALLBACK_IMAGE_GENERATION_BACKUP_API_KEY": "backup-key",
            }
        )

        self.assertEqual(settings.fallback_image.retry_groups, 5)
        self.assertEqual(len(settings.fallback_image.retry_alternates), 1)
        backup = settings.fallback_image.retry_alternates[0]
        self.assertEqual(backup.id, "fallback_backup")
        self.assertEqual(backup.label, "gpt image2(2) backup")
        self.assertEqual(backup.api_key, "backup-key")
        self.assertEqual(backup.base_url, "https://yunwu.ai/v1")
        self.assertEqual(backup.endpoint_path, "/images/generations")
        self.assertEqual(backup.model, "gpt-image-2-all")
        self.assertEqual(backup.size, "2048x2048")
        self.assertEqual(backup.n, 1)
        self.assertEqual(backup.response_format, "b64_json")
        self.assertNotIn("fallback_backup", settings.image_options)

    def test_text_payload_contains_messages_model_and_defaults(self):
        payload = build_chat_completion_payload(
            messages=[{"role": "user", "content": "测试"}],
            model="gemini-3.1-pro-preview",
            max_tokens=4096,
            temperature=0.7,
        )

        self.assertEqual(payload["model"], "gemini-3.1-pro-preview")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "测试"}])
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["temperature"], 0.7)

    def test_image_payload_contains_generation_defaults(self):
        payload = build_image_generation_payload(
            prompt="生成绿色修护风详情图",
            model="gpt-image-2",
            size="2048x2048",
            n=1,
            quality="high",
            output_format="png",
            response_format="b64_json",
        )

        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["size"], "2048x2048")
        self.assertEqual(payload["n"], 1)
        self.assertEqual(payload["prompt"], "生成绿色修护风详情图")
        self.assertEqual(payload["quality"], "high")
        self.assertEqual(payload["output_format"], "png")
        self.assertEqual(payload["response_format"], "b64_json")

    def test_image_payload_allows_per_request_size_override(self):
        payload = build_image_generation_payload(
            prompt="生成抖音主图",
            model="gpt-image-2",
            size="600x600",
            n=1,
        )

        self.assertEqual(payload["size"], "600x600")

    def test_vip_image_payload_omits_unsupported_quality_and_n(self):
        payload = build_image_generation_payload(
            prompt="生成 2K 店铺图",
            model="gpt-image-2-vip",
            size="2048x2048",
            n=0,
            quality="",
            response_format="url",
        )

        self.assertEqual(payload["model"], "gpt-image-2-vip")
        self.assertEqual(payload["size"], "2048x2048")
        self.assertNotIn("n", payload)
        self.assertNotIn("quality", payload)
        self.assertEqual(payload["response_format"], "url")

    def test_chat_image_payload_contains_messages_and_reference_images(self):
        payload = build_chat_image_payload(
            prompt="生成详情图",
            model="gemini-3.1-flash-image-preview",
            image=["data:image/png;base64,abc123"],
        )

        self.assertEqual(payload["model"], "gemini-3.1-flash-image-preview")
        self.assertNotIn("prompt", payload)
        self.assertNotIn("size", payload)
        self.assertEqual(payload["messages"][0]["role"], "user")
        self.assertEqual(
            payload["messages"][0]["content"],
            [
                {"type": "text", "text": "生成详情图"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
            ],
        )

    def test_extract_image_urls_accepts_chat_completion_markdown_data_url(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": "![image](data:image/jpeg;base64,abc123)"
                    }
                }
            ]
        }

        self.assertEqual(extract_image_urls_from_response(payload, image_format="png"), ["data:image/jpeg;base64,abc123"])

    def test_extract_image_urls_accepts_chat_completion_image_url_object(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "done"},
                            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
                        ]
                    }
                }
            ]
        }

        self.assertEqual(extract_image_urls_from_response(payload, image_format="png"), ["data:image/png;base64,abc123"])

    def test_environment_overrides_are_supported(self):
        settings = get_model_settings(
            {
                "TEXT_ANALYSIS_MODEL": "custom-text",
                "TEXT_ANALYSIS_MAX_TOKENS": "8192",
                "IMAGE_GENERATION_MODEL": "custom-image",
                "IMAGE_GENERATION_SIZE": "1536x1024",
                "IMAGE_GENERATION_QUALITY": "medium",
                "FALLBACK_IMAGE_GENERATION_MODEL": "custom-fallback",
            }
        )

        self.assertEqual(settings.text.model, "custom-text")
        self.assertEqual(settings.text.max_tokens, 8192)
        self.assertEqual(settings.image.model, "custom-image")
        self.assertEqual(settings.image.size, "1536x1024")
        self.assertEqual(settings.image.quality, "medium")
        self.assertEqual(settings.fallback_image.model, "custom-fallback")

    def test_fallback_image_size_does_not_inherit_legacy_1024_default(self):
        settings = get_model_settings({"LEGACY_IMAGE_GENERATION_SIZE": "1024x1024"})

        self.assertEqual(settings.fallback_image.size, "2048x2048")
        self.assertEqual(settings.image_options["fallback"].size, "2048x2048")

    def test_dotenv_file_is_loaded_when_explicitly_provided(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "TEXT_ANALYSIS_API_KEY=text-key-from-file",
                        "IMAGE_GENERATION_API_KEY=\"image-key-from-file\"",
                        "TEXT_ANALYSIS_BASE_URL=https://text.example/v1",
                    ]
                ),
                encoding="utf-8",
            )

            settings = get_model_settings({}, env_file=env_path)

        self.assertEqual(settings.text.api_key, "text-key-from-file")
        self.assertEqual(settings.image.api_key, "image-key-from-file")
        self.assertEqual(settings.text.base_url, "https://text.example/v1")

    def test_environment_values_override_dotenv_values(self):
        with TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("TEXT_ANALYSIS_API_KEY=text-key-from-file", encoding="utf-8")

            settings = get_model_settings({"TEXT_ANALYSIS_API_KEY": "text-key-from-env"}, env_file=env_path)

        self.assertEqual(settings.text.api_key, "text-key-from-env")


class ImageModelReferenceInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_api_reference_inputs_use_edits_endpoint_multipart(self):
        settings = ImageGenerationSettings(
            id="primary",
            label="GPT Image 2",
            api_key="test-key",
            base_url="https://example.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2",
            size="2048x2048",
            n=1,
            quality="high",
            output_format="png",
            response_format="b64_json",
        )
        posts = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"b64_json": "abc123"}]}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def post(self, url, *, headers=None, json=None, files=None, data=None):
                posts.append({"url": url, "json": json, "files": files, "data": data})
                return FakeResponse()

        with patch("httpx.AsyncClient", FakeAsyncClient):
            urls = await call_image_model(
                settings,
                "基于上传产品图生成店铺首图",
                image=["data:image/png;base64,iVBORw0KGgo="],
                size="1024x1024",
            )

        self.assertEqual(urls, ["data:image/png;base64,abc123"])
        self.assertEqual(posts[0]["url"], "https://example.com/v1/images/edits")
        self.assertIsNone(posts[0]["json"])
        self.assertEqual(posts[0]["data"]["model"], "gpt-image-2")
        self.assertEqual(posts[0]["data"]["prompt"], "基于上传产品图生成店铺首图")
        self.assertEqual(posts[0]["data"]["size"], "1024x1024")
        self.assertEqual(posts[0]["data"]["quality"], "high")
        self.assertEqual(posts[0]["files"][0][0], "image")
        self.assertEqual(posts[0]["files"][0][1][1], b"\x89PNG\r\n\x1a\n")

    async def test_vip_reference_inputs_keep_2k_size_and_omit_unsupported_fields(self):
        settings = ImageGenerationSettings(
            id="primary",
            label="gpt image2(1)",
            api_key="test-key",
            base_url="https://api.apiyi.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-vip",
            size="2048x2048",
            n=0,
            quality="",
            output_format="png",
            response_format="url",
        )
        posts = []

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"url": "https://files.example.com/generated.png"}]}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return None

            async def post(self, url, *, headers=None, json=None, files=None, data=None):
                posts.append({"url": url, "json": json, "files": files, "data": data})
                return FakeResponse()

        with patch("httpx.AsyncClient", FakeAsyncClient):
            urls = await call_image_model(
                settings,
                "基于上传产品图生成店铺首图",
                image=["data:image/png;base64,iVBORw0KGgo="],
            )

        self.assertEqual(urls, ["https://files.example.com/generated.png"])
        self.assertEqual(posts[0]["url"], "https://api.apiyi.com/v1/images/edits")
        self.assertEqual(posts[0]["data"]["model"], "gpt-image-2-vip")
        self.assertEqual(posts[0]["data"]["size"], "2048x2048")
        self.assertEqual(posts[0]["data"]["response_format"], "url")
        self.assertNotIn("quality", posts[0]["data"])
        self.assertNotIn("n", posts[0]["data"])


if __name__ == "__main__":
    unittest.main()
