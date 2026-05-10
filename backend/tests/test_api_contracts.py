import unittest
from base64 import b64encode
from io import BytesIO
from os import environ
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import ImageGenerationSettings
from app.demo_data import DEFAULT_MODULES, DEFAULT_PRODUCT_INFO, DEMO_IMAGE_URLS, STYLE_OPTIONS
from app.dependencies.auth import require_app_user
from app.routers.models import build_public_model_config
from app.routers.projects import COMPOSE_JOBS, FIXED_PRODUCT_REFERENCE_REQUIRED_ERROR, build_layered_generated_image, check_project_text_compliance, compose_long_jpeg, edit_generated_image, generate_detail_images, render_layered_language_version, router as projects_router
from app.services.language_renderer import build_text_layers, render_text_layers_to_data_url
from app.services.app_session import AppSessionUserSnapshot


class ApiContractTests(unittest.TestCase):
    def test_default_module_registry_has_main_campaign_and_detail_modules(self):
        main_modules = [module for module in DEFAULT_MODULES if module.get("image_group") == "main"]
        campaign_modules = [module for module in DEFAULT_MODULES if module.get("image_group") == "campaign"]
        detail_modules = [module for module in DEFAULT_MODULES if module.get("image_group") == "detail"]

        self.assertEqual([module["id"] for module in main_modules], ["main_white_bg", "main_hero_selling_point", "main_ingredient", "main_effect", "main_usage_scene"])
        self.assertEqual([module["id"] for module in campaign_modules], ["campaign_white_bg", "campaign_hero_selling_point", "campaign_ingredient", "campaign_effect", "campaign_usage_scene"])
        self.assertEqual(
            [module["id"] for module in detail_modules],
            [
                "hero",
                "authority",
                "pain_scene",
                "effect_comparison",
                "competitor_comparison",
                "ingredient_overview",
                "ingredient_1",
                "ingredient_2",
                "ingredient_3",
                "usage",
            ],
        )
        self.assertNotIn("ingredient", [module["id"] for module in detail_modules])

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
        self.assertIn("gpt-image-2-vip", serialized)
        self.assertIn("gpt image2(1)", serialized)
        self.assertIn("gpt image2(2)", serialized)
        self.assertIn("gemini-3.1-flash-image-preview", serialized)
        self.assertIn("gpt-image-2-all", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("bearer", serialized)
        self.assertEqual(config["imageGeneration"]["defaultOptionId"], "primary")
        self.assertEqual(config["imageGeneration"]["options"][0]["id"], "primary")
        self.assertEqual(config["imageGeneration"]["options"][0]["label"], "gpt image2(1)")
        self.assertEqual(config["imageGeneration"]["options"][0]["model"], "gpt-image-2-vip")
        self.assertEqual(config["imageGeneration"]["options"][0]["defaults"]["size"], "2048x2048")
        self.assertEqual(config["imageGeneration"]["options"][0]["defaults"]["response_format"], "url")
        self.assertEqual(config["imageGeneration"]["options"][1]["id"], "fallback")
        self.assertEqual(config["imageGeneration"]["options"][1]["label"], "gpt image2(2)")


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

    async def test_generation_returns_errors_without_demo_images_when_primary_and_fallback_fail(self):
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
        self.assertEqual(result["images"], [{"module_id": "usage", "url": "https://example.com/usage.png"}])
        self.assertTrue(result["errors"])

    async def test_generation_does_not_return_fixed_demo_image_when_all_models_fail(self):
        async def fake_call_image_model(settings, prompt, image=None, size=None):
            raise RuntimeError("boom")

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

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["images"], [])
        self.assertEqual(len(result["errors"]), 2)

    async def test_generation_uses_fallback_when_primary_returns_empty_content(self):
        calls = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append(settings.model)
            if settings.model == "gpt-image-2-vip":
                return []
            return ["https://example.com/fallback.png"]

        previous_primary_key = environ.get("IMAGE_GENERATION_API_KEY")
        previous_fallback_key = environ.get("FALLBACK_IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        environ["FALLBACK_IMAGE_GENERATION_API_KEY"] = "fallback-key"
        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["hero"], "green_repair")
        finally:
            if previous_primary_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_primary_key
            if previous_fallback_key is None:
                environ.pop("FALLBACK_IMAGE_GENERATION_API_KEY", None)
            else:
                environ["FALLBACK_IMAGE_GENERATION_API_KEY"] = previous_fallback_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["images"], [{"module_id": "hero", "url": "https://example.com/fallback.png"}])
        self.assertEqual(calls, ["gpt-image-2-vip", "gpt-image-2-all"])

    async def test_fixed_product_composite_uses_local_product_compositor(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/background.png"])) as generate_mock:
                with patch("app.routers.projects._read_image_bytes", new=AsyncMock(side_effect=[b"background-bytes", b"product-bytes"])):
                    with patch("app.routers.projects.compose_fixed_product_image", return_value=b"composited-bytes") as compose_mock:
                        with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)) as upload_mock:
                            with patch("app.routers.projects.call_image_edit_model", new=AsyncMock(return_value=["https://example.com/model-edit.png"])) as edit_mock:
                                result = await generate_detail_images(
                                    ["hero"],
                                    "green_repair",
                                    product_info={"product_name": "积雪草修护精华"},
                                    reference_images=["data:image/png;base64,original"],
                                    generation_mode="fixed_product_composite",
                                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertTrue(result["images"][0]["url"].startswith("data:image/png;base64,"))
        generate_mock.assert_called_once()
        self.assertIn("背景层", generate_mock.call_args.args[1])
        self.assertNotIn("data:image/png;base64,original", generate_mock.call_args.kwargs.get("image") or [])
        compose_mock.assert_called_once_with(b"background-bytes", b"product-bytes", module_id="hero")
        upload_mock.assert_called_once()
        edit_mock.assert_not_called()

    async def test_fixed_product_composite_requires_product_reference(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/background.png"])):
                        result = await generate_detail_images(
                            ["hero"],
                            "green_repair",
                            product_info={"product_name": "积雪草修护精华"},
                            generation_mode="fixed_product_composite",
                        )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["images"], [])
        self.assertIn(FIXED_PRODUCT_REFERENCE_REQUIRED_ERROR, result["errors"][0])

    async def test_generation_reports_unconfigured_image_model(self):
        image = ImageGenerationSettings(
            id="primary",
            label="GPT Image 2",
            api_key="",
            base_url="https://example.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2",
            size="2048x2048",
            n=1,
        )
        fallback = ImageGenerationSettings(
            id="fallback",
            label="GPT Image 2 All",
            api_key="",
            base_url="https://fallback.example.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-all",
            size="2048x2048",
            n=1,
        )
        settings = SimpleNamespace(image=image, fallback_image=fallback, image_options={"primary": image})

        with patch("app.routers.projects.get_model_settings", return_value=settings):
            result = await generate_detail_images(["hero"], "green_repair")

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["images"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("hero", result["errors"][0])
        self.assertIn("GPT Image 2", result["errors"][0])
        self.assertIn("not configured", result["errors"][0])

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

    async def test_generation_prompt_can_target_english_full_image_text(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        prompts = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            prompts.append(prompt)
            return ["https://example.com/english.png"]

        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["hero"],
                    "blue_hydration",
                    product_info={"product_name": "水润保湿精华", "core_selling_points": ["深层补水"]},
                    target_language="en",
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertIn("English", prompts[0])
        self.assertIn("直接生成在图片里", prompts[0])
        self.assertNotIn("分层文字模式", prompts[0])

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

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["url"], "https://example.com/edited.png")
        self.assertEqual(result["compliance"]["summary"]["status"], "pass")
        self.assertIn("背景颜色改成深绿色", calls[0]["prompt"])
        self.assertEqual(calls[0]["image_bytes"], b"abc")
        self.assertEqual(calls[0]["size"], "800x800")

    async def test_layered_generation_builds_base_and_default_language_version(self):
        image = Image.new("RGB", (320, 320), (230, 244, 235))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        module = next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point")

        with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)):
            result = await build_layered_generated_image(
                module=module,
                product_info={"product_name": "修护精华", "core_selling_points": ["深层补水"], "functions": ["水润透亮"]},
                base_url=data_url,
            )

        self.assertEqual(result["module_id"], "main_hero_selling_point")
        self.assertEqual(result["base_url"], data_url)
        self.assertTrue(result["url"].startswith("data:image/png;base64,"))
        self.assertTrue(result["text_layers"])
        self.assertIn("zh-CN", result["language_versions"])

    async def test_render_language_version_translates_then_reuses_base_image(self):
        image = Image.new("RGB", (320, 320), (240, 240, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        layers = build_text_layers(
            {"product_name": "修护精华", "core_selling_points": ["深层补水"], "functions": ["水润透亮"]},
            next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point"),
        )

        with patch("app.routers.projects.translate_text_layers", new=AsyncMock(return_value=[{**layers[0], "text": "Deep Hydration"}])):
            with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)):
                result = await render_layered_language_version(base_url=data_url, layers=layers[:1], language="en")

        self.assertEqual(result["language"], "en")
        self.assertEqual(result["language_label"], "English")
        self.assertTrue(result["url"].startswith("data:image/png;base64,"))
        self.assertEqual(result["layers"][0]["text"], "Deep Hydration")

    async def test_layered_generation_includes_compliance_report(self):
        image = Image.new("RGB", (320, 320), (230, 244, 235))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        module = next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point")

        with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)):
            result = await build_layered_generated_image(
                module=module,
                product_info={"product_name": "修护精华", "core_selling_points": ["7天治愈敏感肌"], "functions": ["水润透亮"]},
                base_url=data_url,
                platform_id="tmall",
            )

        self.assertEqual(result["compliance"]["summary"]["status"], "block")
        self.assertEqual(result["language_versions"]["zh-CN"]["compliance"]["summary"]["status"], "block")

    async def test_render_language_version_includes_compliance_report(self):
        image = Image.new("RGB", (320, 320), (240, 240, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        layers = [
            {
                "id": "title",
                "role": "title",
                "source_text": "深层补水",
                "text": "深层补水",
                "x": 0.1,
                "y": 0.1,
                "width": 0.5,
                "height": 0.1,
                "font_size": 0.06,
            }
        ]

        with patch("app.routers.projects.translate_text_layers", new=AsyncMock(return_value=[{**layers[0], "text": "100% effective"}])):
            with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)):
                result = await render_layered_language_version(base_url=data_url, layers=layers, language="en", platform_id="tmall")

        self.assertEqual(result["compliance"]["summary"]["status"], "block")
        self.assertEqual(result["compliance"]["issues"][0]["category"], "absolute_claim")

    async def test_edit_generated_image_returns_instruction_compliance(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_edit_model", new=AsyncMock(return_value=["https://example.com/edited.png"])):
                result = await edit_generated_image(
                    "data:image/png;base64,YWJj",
                    "把标题改成全网最低价",
                    platform_size="800x800",
                    platform_id="tmall",
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["compliance"]["summary"]["status"], "block")

    def test_text_layer_renderer_returns_png_data_url(self):
        image = Image.new("RGB", (240, 240), (255, 255, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url, warnings = render_text_layers_to_data_url(
            buffer.getvalue(),
            [
                {
                    "id": "title",
                    "text": "Deep Hydration",
                    "x": 0.08,
                    "y": 0.08,
                    "width": 0.70,
                    "height": 0.20,
                    "font_size": 0.08,
                    "max_lines": 2,
                    "weight": "bold",
                }
            ],
            language="en",
        )

        self.assertTrue(data_url.startswith("data:image/png;base64,"))
        self.assertIsInstance(warnings, list)

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

    def test_text_compliance_endpoint_returns_report(self):
        response = self.make_client().post(
            "/api/projects/compliance/check-text",
            json={
                "platform_id": "tmall",
                "items": [
                    {
                        "text": "7天治愈敏感肌",
                        "location": {"source_type": "field", "field": "core_selling_points"},
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "rules")
        self.assertEqual(payload["summary"]["status"], "block")
        self.assertEqual(payload["issues"][0]["term"], "治愈")

    def test_image_compliance_endpoint_uses_ai_image_report(self):
        class FakeImageComplianceProvider:
            source = "fake_ai"

            async def check_image(self, image_bytes, *, location, platform_id=None, product_info=None, debug=False):
                return {
                    "issues": [
                        {
                            "id": "ai_absolute_claim",
                            "severity": "block",
                            "category": "absolute_claim",
                            "platform_ids": [platform_id],
                            "term": "100%",
                            "matched_text": "100%有效",
                            "location": location,
                            "reason": "AI 判断图片文案含绝对化数据承诺。",
                            "suggestion": "删除绝对化数据，改为有依据的温和表达。",
                            "qualification_hint": "",
                        }
                    ],
                    "extracted_texts": [{"text": "100%有效", "confidence": 0.91, "box": [0, 0, 80, 24], "location": location}],
                    "warnings": [],
                }

        with patch("app.routers.projects.create_default_image_compliance_provider", return_value=FakeImageComplianceProvider()):
            response = self.make_client().post(
                "/api/projects/compliance/check-images",
                json={"platform_id": "tmall", "image_urls": [self.png_data_url()]},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "image_ai")
        self.assertEqual(payload["ai_source"], "fake_ai")
        self.assertEqual(payload["summary"]["status"], "block")
        self.assertEqual(payload["issues"][0]["term"], "100%")
        self.assertEqual(payload["extracted_texts"][0]["text"], "100%有效")


if __name__ == "__main__":
    unittest.main()
