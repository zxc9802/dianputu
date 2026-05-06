import unittest
from base64 import b64encode
from io import BytesIO
from os import environ
from unittest.mock import AsyncMock, patch

from PIL import Image

from app.demo_data import DEFAULT_MODULES, DEFAULT_PRODUCT_INFO, DEMO_IMAGE_URLS, STYLE_OPTIONS
from app.routers.models import build_public_model_config
from app.routers.projects import compose_long_jpeg, generate_detail_images


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
        async def fake_call_image_model(settings, prompt, image=None):
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


if __name__ == "__main__":
    unittest.main()
