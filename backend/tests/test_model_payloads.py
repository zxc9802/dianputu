import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.core.config import get_model_settings
from app.services.image_model import build_image_generation_payload
from app.services.text_model import build_chat_completion_payload


class ModelPayloadTests(unittest.TestCase):
    def test_text_model_defaults_use_large_token_budget(self):
        settings = get_model_settings({})

        self.assertEqual(settings.text.model, "gemini-3.1-pro-preview")
        self.assertEqual(settings.text.max_tokens, 4096)
        self.assertEqual(settings.fallback_text.base_url, "http://38.59.249.36:8080/v1")
        self.assertEqual(settings.fallback_text.model, "gpt-5.5")
        self.assertEqual(settings.image.size, "2048x2048")
        self.assertEqual(settings.fallback_image.size, "2048x2048")

    def test_text_payload_contains_messages_model_and_defaults(self):
        payload = build_chat_completion_payload(
            messages=[{"role": "user", "content": "测试"}],
            model="gemini-3.1-pro-preview",
            max_tokens=4096,
            temperature=0.2,
        )

        self.assertEqual(payload["model"], "gemini-3.1-pro-preview")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "测试"}])
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["temperature"], 0.2)

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

    def test_environment_overrides_are_supported(self):
        settings = get_model_settings(
            {
                "TEXT_ANALYSIS_MODEL": "custom-text",
                "TEXT_ANALYSIS_MAX_TOKENS": "8192",
                "IMAGE_GENERATION_MODEL": "custom-image",
                "IMAGE_GENERATION_SIZE": "1536x1024",
                "IMAGE_GENERATION_QUALITY": "medium",
                "FALLBACK_TEXT_ANALYSIS_MODEL": "custom-fallback-text",
                "FALLBACK_IMAGE_GENERATION_MODEL": "custom-fallback",
            }
        )

        self.assertEqual(settings.text.model, "custom-text")
        self.assertEqual(settings.text.max_tokens, 8192)
        self.assertEqual(settings.fallback_text.model, "custom-fallback-text")
        self.assertEqual(settings.image.model, "custom-image")
        self.assertEqual(settings.image.size, "1536x1024")
        self.assertEqual(settings.image.quality, "medium")
        self.assertEqual(settings.fallback_image.model, "custom-fallback")

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


if __name__ == "__main__":
    unittest.main()
