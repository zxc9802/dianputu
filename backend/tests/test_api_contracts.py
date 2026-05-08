import unittest
from base64 import b64encode
from io import BytesIO
from os import environ
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.demo_data import DEFAULT_MODULES, DEFAULT_PRODUCT_INFO, DEMO_IMAGE_URLS, STYLE_OPTIONS
from app.dependencies.auth import require_app_user
from app.routers.models import build_public_model_config
from app.routers.projects import COMPOSE_JOBS, compose_long_jpeg, edit_generated_image, generate_detail_images, router as projects_router
from app.services.app_session import AppSessionUserSnapshot


class ApiContractTests(unittest.TestCase):
    def test_default_module_registry_has_main_campaign_and_detail_modules(self):
        main_modules = [module for module in DEFAULT_MODULES if module.get("image_group") == "main"]
        campaign_modules = [module for module in DEFAULT_MODULES if module.get("image_group") == "campaign"]
        detail_modules = [module for module in DEFAULT_MODULES if module.get("image_group") == "detail"]

        self.assertEqual([module["id"] for module in main_modules], ["main_white_bg", "main_hero_selling_point", "main_ingredient", "main_effect", "main_usage_scene"])
        self.assertEqual([module["id"] for module in campaign_modules], ["campaign_white_bg", "campaign_hero_selling_point", "campaign_ingredient", "campaign_effect", "campaign_usage_scene"])
        self.assertEqual(detail_modules[0]["id"], "hero")
        self.assertEqual(detail_modules[-1]["id"], "usage")

    def test_product_info_contains_confirmation_fields(self):
        required = {
            "product_name",
            "category",
            "core_selling_points",
            "functions",
            "ingredients",
            "usage_method",
            "authority_assets",
            "effect_claims",
        }

        self.assertTrue(required.issubset(DEFAULT_PRODUCT_INFO.keys()))

    def test_three_style_options_are_available(self):
        self.assertEqual([style["id"] for style in STYLE_OPTIONS], ["green_repair", "blue_hydration", "gold_antiaging"])
        self.assertTrue(all(style.get("asset", "").startswith("/assets/") for style in STYLE_OPTIONS))

    def test_demo_image_urls_point_to_frontend_assets(self):
        self.assertEqual(set(DEMO_IMAGE_URLS), {module["id"] for module in DEFAULT_MODULES})
        self.assertTrue(all(url.startswith("/assets/") for url in DEMO_IMAGE_URLS.values()))

    def test_public_model_config_never_includes_api_keys(self):
        config = build_public_model_config()
        serialized = repr(config).lower()

        self.assertIn("gemini-3.1-pro-preview", serialized)
        self.assertIn("gpt-image-2", serialized)
        self.assertIn("gemini-3.1-flash-image-preview", serialized)
        self.assertIn("gpt-image-2-all", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("bearer", serialized)


class GenerationContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_returns_one_image_per_requested_module(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(side_effect=[["https://example.com/hero.png"], ["https://example.com/usage.png"]])):
                result = await generate_detail_images(["hero", "usage"], "green_repair")
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(
            result["images"],
            [
                {"module_id": "hero", "url": "https://example.com/hero.png"},
                {"module_id": "usage", "url": "https://example.com/usage.png"},
            ],
        )

    async def test_generation_uses_demo_image_when_primary_and_fallback_fail(self):
        async def fake_call_image_model(settings, prompt, image=None, size=None):
            if "详情首图" in prompt:
                raise RuntimeError("boom")
            return ["https://example.com/usage.png"]

        previous_primary_key = environ.get("IMAGE_GENERATION_API_KEY")
        previous_fallback_key = environ.get("FALLBACK_IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        environ["FALLBACK_IMAGE_GENERATION_API_KEY"] = "fallback-key"
        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["hero", "usage"], "green_repair")
        finally:
            if previous_primary_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_primary_key
            if previous_fallback_key is None:
                environ.pop("FALLBACK_IMAGE_GENERATION_API_KEY", None)
            else:
                environ["FALLBACK_IMAGE_GENERATION_API_KEY"] = previous_fallback_key

        self.assertEqual(result["source"], "mixed")
        self.assertEqual(result["images"][0]["module_id"], "hero")
        self.assertTrue(result["images"][0]["url"].startswith("/assets/"))
        self.assertEqual(result["images"][1], {"module_id": "usage", "url": "https://example.com/usage.png"})

    async def test_generation_accepts_single_module_for_regeneration(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/single.png"])):
                result = await generate_detail_images(["campaign_effect"], "green_repair", promotion_info="满 199 减 30")
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["images"], [{"module_id": "campaign_effect", "url": "https://example.com/single.png"}])

    async def test_generation_passes_platform_size_to_image_model(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        calls = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append(size)
            return ["https://example.com/douyin.png"]

        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["main_effect"], "green_repair", platform_size="600x600")
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(calls, ["600x600"])

    async def test_generation_can_select_gemini_flash_image_model(self):
        previous_key = environ.get("GEMINI_FLASH_IMAGE_API_KEY")
        environ["GEMINI_FLASH_IMAGE_API_KEY"] = "test-key"
        calls = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append({"model": settings.model, "base_url": settings.base_url, "endpoint_path": settings.endpoint_path, "size": size})
            return ["https://example.com/gemini.png"]

        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["main_effect"], "green_repair", platform_size="2048x2048", image_model_id="gemini_flash_image")
        finally:
            if previous_key is None:
                environ.pop("GEMINI_FLASH_IMAGE_API_KEY", None)
            else:
                environ["GEMINI_FLASH_IMAGE_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(
            calls,
            [
                {
                    "model": "gemini-3.1-flash-image-preview",
                    "base_url": "https://www.shanbaob.net/v1",
                    "endpoint_path": "/chat/completions",
                    "size": "2048x2048",
                }
            ],
        )

    async def test_edit_generated_image_uses_instruction_and_original_image(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        calls = []

        async def fake_call_image_edit_model(settings, prompt, image_bytes, size=None):
            calls.append({"prompt": prompt, "image_bytes": image_bytes, "size": size})
            return ["https://example.com/edited.png"]

        try:
            with patch("app.routers.projects.call_image_edit_model", new=fake_call_image_edit_model):
                result = await edit_generated_image("data:image/png;base64,YWJj", "背景颜色改成深绿色", platform_size="800x800")
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result, {"source": "model", "url": "https://example.com/edited.png"})
        self.assertIn("背景颜色改成深绿色", calls[0]["prompt"])
        self.assertEqual(calls[0]["image_bytes"], b"abc")
        self.assertEqual(calls[0]["size"], "800x800")

    async def test_compose_long_jpeg_stacks_images_vertically(self):
        def data_url(color: tuple[int, int, int]) -> str:
            image = Image.new("RGB", (20, 10), color)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")

        jpeg = await compose_long_jpeg([data_url((255, 0, 0)), data_url((0, 255, 0))], target_width=40)

        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        composed = Image.open(BytesIO(jpeg))
        self.assertEqual(composed.size, (40, 40))
        self.assertEqual(composed.mode, "RGB")


class DownloadContractTests(unittest.TestCase):
    def make_client(self) -> TestClient:
        app = FastAPI()
        app.dependency_overrides[require_app_user] = lambda: AppSessionUserSnapshot(user_id="test-user")
        app.include_router(projects_router)
        return TestClient(app)

    def png_data_url(self) -> str:
        image = Image.new("RGB", (2, 2), (12, 34, 56))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")

    def test_image_download_proxy_returns_attachment(self):
        response = self.make_client().post(
            "/api/projects/download-image",
            json={"url": self.png_data_url(), "filename": "generated.png"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertIn('filename="generated.png"', response.headers["content-disposition"])
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n"))

    def test_composed_job_download_proxies_remote_url_as_attachment(self):
        job_id = "compose_download_contract"
        COMPOSE_JOBS[job_id] = {
            "status": "done",
            "stage": "done",
            "current": 1,
            "total": 1,
            "message": "done",
            "content": b"",
            "url": self.png_data_url(),
        }
        try:
            response = self.make_client().get(f"/api/projects/compose-long-image/jobs/{job_id}/download")
        finally:
            COMPOSE_JOBS.pop(job_id, None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertNotEqual(response.headers["content-type"], "application/json")
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n"))


if __name__ == "__main__":
    unittest.main()
