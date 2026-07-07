import unittest
from base64 import b64decode, b64encode
from io import BytesIO
from os import environ
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import ImageGenerationSettings
from app.demo_data import ALL_MODULES, DEFAULT_DETAIL_LAYOUT_ID, DEFAULT_MODULES, DEFAULT_PRODUCT_INFO, DEMO_IMAGE_URLS, DETAIL_LAYOUTS, STYLE_OPTIONS
from app.dependencies.auth import require_app_user
from app.routers.models import build_public_model_config
from app.routers.projects import COMPOSE_JOBS, EDIT_JOBS, FIXED_PRODUCT_REFERENCE_REQUIRED_ERROR, STYLE_JOBS, UploadedMaterial, build_layered_generated_image, build_material_analysis_messages, build_style_reference_analysis_messages, compose_long_jpeg, edit_generated_image, generate_detail_images, normalize_style_reference_plan_from_model, render_layered_language_version, router as projects_router
from app.services.language_renderer import build_text_layers, render_text_layers_to_data_url
from app.services.app_session import AppSessionUserSnapshot


def _test_png_data_url(color=(120, 180, 220, 255), size=(96, 128)) -> str:
    image = Image.new("RGBA", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")


class StaticComplianceProvider:
    source = "fake_gemini"

    def __init__(self, status="pass", category="model_review", term=""):
        self.status = status
        self.category = category
        self.term = term

    def report(self, location=None, matched_text=""):
        if self.status == "pass":
            return {"summary": {"status": "pass", "block_count": 0, "warn_count": 0, "review_count": 0}, "issues": []}
        issue = {
            "severity": self.status,
            "category": self.category,
            "term": self.term or matched_text or "合规风险",
            "matched_text": matched_text,
            "location": location or {},
            "reason": "Gemini 判断该内容存在合规风险。",
            "suggestion": "请调整为真实、克制且有依据的表达。",
        }
        return {
            "summary": {
                "status": self.status,
                "block_count": 1 if self.status == "block" else 0,
                "warn_count": 1 if self.status == "warn" else 0,
                "review_count": 1 if self.status == "review" else 0,
            },
            "issues": [issue],
        }

    async def review_text(self, items, *, platform_id=None, product_info=None, debug=False):
        return self.report(location=items[0].get("location"), matched_text=items[0].get("text", ""))

    async def review_image(self, image_bytes, *, metadata, platform_id=None, product_info=None, debug=False):
        return self.report(location=metadata.get("location"), matched_text=self.term)


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
                "detail_ec_hero",
                "detail_ec_pain_matrix",
                "detail_ec_solution",
                "detail_ec_competitor_comparison",
                "detail_ec_real_trial",
                "detail_ec_effect_validation",
                "detail_ec_research_system",
                "detail_ec_ingredient_1_mechanism",
                "detail_ec_ingredient_1_proof",
                "detail_ec_ingredient_2_mechanism",
                "detail_ec_auxiliary_mechanism",
                "detail_ec_auxiliary_validation",
                "detail_ec_real_feedback",
                "detail_ec_texture",
                "detail_ec_brand_sensory",
                "detail_ec_usage",
            ],
        )
        self.assertNotIn("ingredient", [module["id"] for module in detail_modules])
        self.assertNotIn("authority", [module["id"] for module in detail_modules])
        self.assertNotIn("ingredient_1", [module["id"] for module in detail_modules])

    def test_detail_layout_registry_keeps_new_default_and_standard_option(self):
        self.assertEqual(DEFAULT_DETAIL_LAYOUT_ID, "detail_evidence_chain_16")
        layouts_by_id = {layout["id"]: layout for layout in DETAIL_LAYOUTS}

        self.assertEqual([module["id"] for module in layouts_by_id["detail_evidence_chain_16"]["modules"][:4]], ["detail_ec_hero", "detail_ec_pain_matrix", "detail_ec_solution", "detail_ec_competitor_comparison"])
        self.assertEqual(layouts_by_id["detail_evidence_chain_16"]["modules"][10]["id"], "detail_ec_auxiliary_mechanism")
        self.assertEqual(layouts_by_id["detail_evidence_chain_16"]["modules"][11]["id"], "detail_ec_auxiliary_validation")
        self.assertEqual([module["id"] for module in layouts_by_id["detail_standard_conversion_10"]["modules"][-2:]], ["usage", "product_info"])

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

    def test_preset_style_options_include_structured_skincare_themes(self):
        self.assertEqual(
            [style["id"] for style in STYLE_OPTIONS],
            [
                "space_repair",
                "deep_sea_hydration",
                "lab_clinical_tech",
                "oriental_herbal",
                "glacier_cooling",
                "floral_fragrance",
                "black_gold_luxury",
            ],
        )
        self.assertTrue(all(style.get("asset", "").startswith("/assets/style-") for style in STYLE_OPTIONS))
        self.assertTrue(all(style.get("asset", "").endswith(".png") for style in STYLE_OPTIONS))
        black_gold = STYLE_OPTIONS[-1]
        self.assertEqual(black_gold["name"], "黑金奢华风")
        self.assertIn("黑金高奢护肤视觉", black_gold["theme"])
        self.assertIn("module_usage", black_gold)
        self.assertIn("首图", black_gold["module_usage"])
        self.assertIn("forbidden", black_gold)

    def test_demo_image_urls_point_to_frontend_assets(self):
        self.assertEqual(set(DEMO_IMAGE_URLS), {module["id"] for module in ALL_MODULES})
        self.assertTrue(all(url.startswith("/assets/") for url in DEMO_IMAGE_URLS.values()))

    def test_defaults_endpoint_returns_selectable_detail_layouts(self):
        app = FastAPI()
        app.dependency_overrides[require_app_user] = lambda: AppSessionUserSnapshot(user_id="test-user")
        app.include_router(projects_router)
        response = TestClient(app).get("/api/projects/defaults")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["default_detail_layout_id"], "detail_evidence_chain_16")
        self.assertEqual([layout["id"] for layout in payload["detail_layouts"]], ["detail_evidence_chain_16", "detail_standard_conversion_10"])
        self.assertIn("detail_ec_auxiliary_mechanism", [module["id"] for module in payload["modules"]])

    def test_material_analysis_prompt_is_layout_aware_and_shared_with_main_images(self):
        messages = build_material_analysis_messages(
            [
                UploadedMaterial(
                    filename="long-detail.png",
                    content_type="image/png",
                    data=b"\x89PNG\r\n",
                )
            ],
            detail_layout_id="detail_evidence_chain_16",
        )
        prompt = messages[0]["content"][0]["text"]

        self.assertIn("cross_image_brief", prompt)
        self.assertIn("detail_layout_brief", prompt)
        self.assertIn("证据链长图结构", prompt)
        self.assertIn("辅助功效机制", prompt)
        self.assertIn("辅助功效验证", prompt)
        self.assertIn("可同步影响主图/活动图", prompt)

    def test_public_model_config_never_includes_api_keys(self):
        config = build_public_model_config()
        serialized = repr(config).lower()

        self.assertIn("gemini-3.1-pro-preview", serialized)
        self.assertIn("gpt-image-2-vip", serialized)
        self.assertIn("gpt image2(1)", serialized)
        self.assertIn("gpt image2(2)", serialized)
        self.assertIn("gemini-3.1-flash-image-preview", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("bearer", serialized)
        self.assertEqual(config["imageGeneration"]["model"], "gpt-image-2")
        self.assertEqual(config["imageGeneration"]["defaultOptionId"], "fallback")
        self.assertEqual(config["imageGeneration"]["options"][0]["id"], "primary")
        self.assertEqual(config["imageGeneration"]["options"][0]["label"], "gpt image2(1)")
        self.assertEqual(config["imageGeneration"]["options"][0]["model"], "gpt-image-2-vip")
        self.assertEqual(config["imageGeneration"]["options"][0]["defaults"]["size"], "2048x2048")
        self.assertEqual(config["imageGeneration"]["options"][0]["defaults"]["response_format"], "url")
        self.assertEqual(config["imageGeneration"]["options"][1]["id"], "fallback")
        self.assertEqual(config["imageGeneration"]["options"][1]["label"], "gpt image2(2)")

    def test_style_reference_analysis_prompt_covers_benchmark_dimensions(self):
        messages = build_style_reference_analysis_messages(
            {"product_name": "积雪草修护精华", "category": "修护精华"},
            [
                UploadedMaterial(
                    filename="benchmark.png",
                    content_type="image/png",
                    data=b"",
                    data_url="data:image/png;base64,abc123",
                    slot="style_reference",
                )
            ],
        )

        prompt = messages[0]["content"][0]["text"]
        for expected in [
            "主色、辅色、点缀色",
            "光影",
            "构图",
            "背景与材质",
            "字体层级",
            "信息密度",
            "低元素密度",
            "元素预算",
            "每屏只保留",
            "不要复刻",
        ]:
            self.assertIn(expected, prompt)
        self.assertEqual(messages[0]["content"][1]["image_url"]["url"], "data:image/png;base64,abc123")

    def test_style_reference_normalization_marks_style_as_benchmark_driven(self):
        style = normalize_style_reference_plan_from_model(
            """
            {
              "name": "冷萃晶透风",
              "primary_color": "#A8DDE8",
              "keywords": ["冷感", "晶透", "高级"],
              "visual_direction": "清透蓝绿色、柔光、玻璃材质",
              "layout_guidance": "中心产品、大留白、标题层级克制"
            }
            """
        )

        self.assertEqual(style["id"], "style_reference")
        self.assertEqual(style["seed_id"], "benchmark_image")
        self.assertEqual(style["name"], "冷萃晶透风")
        self.assertIn("不要复刻参考图中的品牌", style["forbidden"])
        self.assertIn("不要因为参考图好看而增加无信息价值装饰", style["forbidden"])


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
                result = await generate_detail_images(["hero"], "green_repair", image_model_id="primary")
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
        self.assertEqual(calls, ["gpt-image-2-vip", "gpt-image-2"])

    async def test_selected_primary_retries_primary_then_backup_for_five_groups(self):
        calls = []
        backup = ImageGenerationSettings(
            id="primary_backup",
            label="gpt image2(1) backup",
            api_key="backup-key",
            base_url="https://api-xai.ainaibahub.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2",
            size="2048x2048",
            n=1,
        )
        primary = ImageGenerationSettings(
            id="primary",
            label="gpt image2(1)",
            api_key="primary-key",
            base_url="https://api.apiyi.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-vip",
            size="2048x2048",
            n=0,
            retry_alternates=(backup,),
            retry_groups=5,
        )
        fallback = ImageGenerationSettings(
            id="fallback",
            label="gpt image2(2)",
            api_key="fallback-key",
            base_url="https://yunwu.ai/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-all",
            size="2048x2048",
            n=1,
        )
        settings = SimpleNamespace(
            image=primary,
            fallback_image=fallback,
            default_image_option_id="fallback",
            image_options={"primary": primary, "fallback": fallback},
        )

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append((settings.model, settings.base_url))
            if len(calls) == 10:
                return ["https://example.com/primary-backup.png"]
            return []

        with patch("app.routers.projects.get_model_settings", return_value=settings):
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["hero"], "green_repair", image_model_id="primary")

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["images"], [{"module_id": "hero", "url": "https://example.com/primary-backup.png"}])
        self.assertEqual(
            calls,
            [
                ("gpt-image-2-vip", "https://api.apiyi.com/v1"),
                ("gpt-image-2", "https://api-xai.ainaibahub.com/v1"),
            ]
            * 5,
        )

    async def test_generation_limits_model_reference_images_to_focused_subset(self):
        captured_images = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            captured_images.append(image)
            return ["https://example.com/hero.png"]

        previous_primary_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        product_1 = _test_png_data_url((40, 120, 220, 255))
        product_2 = _test_png_data_url((220, 120, 40, 255))
        product_3 = _test_png_data_url((120, 220, 40, 255))
        style_1 = _test_png_data_url((180, 220, 240, 255))
        style_2 = _test_png_data_url((240, 220, 180, 255))
        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["hero"],
                    "green_repair",
                    reference_images=[product_1, product_2, product_3],
                    style_reference_images=[style_1, style_2],
                    image_model_id="primary",
                )
        finally:
            if previous_primary_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_primary_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(len(captured_images[0]), 3)
        self.assertTrue(captured_images[0][0].startswith("data:image/png;base64,"))
        self.assertNotEqual(captured_images[0][0], product_1)
        self.assertEqual(
            captured_images,
            [
                [
                    captured_images[0][0],
                    product_1,
                    style_1,
                ]
            ],
        )

    async def test_reference_generation_sends_product_identity_board_before_original_product(self):
        captured_images = []
        captured_prompts = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            captured_images.append(image)
            captured_prompts.append(prompt)
            return ["https://example.com/hero.png"]

        previous_primary_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        product = _test_png_data_url((24, 80, 160, 255), size=(90, 140))
        style = _test_png_data_url((180, 230, 250, 255), size=(120, 80))
        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["hero"],
                    "green_repair",
                    reference_images=[product],
                    style_reference_images=[style],
                    image_model_id="primary",
                )
        finally:
            if previous_primary_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_primary_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(len(captured_images[0]), 3)
        identity_board, original_product, style_reference = captured_images[0]
        self.assertTrue(identity_board.startswith("data:image/png;base64,"))
        self.assertNotEqual(identity_board, product)
        self.assertEqual(original_product, product)
        self.assertEqual(style_reference, style)
        with Image.open(BytesIO(b64decode(identity_board.partition(",")[2]))) as board:
            self.assertEqual(board.size, (1024, 1024))
        self.assertIn("产品身份参考板", captured_prompts[0])
        self.assertIn("产品参考图只用于锁定商品外观", captured_prompts[0])
        self.assertIn("风格参考图只用于色彩、光影、版式和氛围", captured_prompts[0])
        self.assertIn("不可变产品身份", captured_prompts[0])

    async def test_selected_fallback_retries_api_xai_then_yunwu_backup_for_five_groups(self):
        calls = []
        primary = ImageGenerationSettings(
            id="primary",
            label="gpt image2(1)",
            api_key="primary-key",
            base_url="https://primary.example.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-vip",
            size="2048x2048",
            n=0,
        )
        backup = ImageGenerationSettings(
            id="fallback_backup",
            label="gpt image2(2) backup",
            api_key="backup-key",
            base_url="https://yunwu.ai/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-all",
            size="2048x2048",
            n=1,
        )
        fallback = ImageGenerationSettings(
            id="fallback",
            label="gpt image2(2)",
            api_key="api-xai-key",
            base_url="https://api-xai.ainaibahub.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2",
            size="2048x2048",
            n=1,
            retry_alternates=(backup,),
            retry_groups=5,
        )
        settings = SimpleNamespace(
            image=primary,
            fallback_image=fallback,
            default_image_option_id="fallback",
            image_options={"primary": primary, "fallback": fallback},
        )

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append((settings.model, settings.base_url))
            if len(calls) == 10:
                return ["https://example.com/backup.png"]
            return []

        with patch("app.routers.projects.get_model_settings", return_value=settings):
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["hero"], "green_repair", image_model_id="fallback")

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["images"], [{"module_id": "hero", "url": "https://example.com/backup.png"}])
        self.assertEqual(
            calls,
            [
                ("gpt-image-2", "https://api-xai.ainaibahub.com/v1"),
                ("gpt-image-2-all", "https://yunwu.ai/v1"),
            ]
            * 5,
        )

    async def test_selected_fallback_reports_error_after_five_retry_groups_fail(self):
        calls = []
        backup = ImageGenerationSettings(
            id="fallback_backup",
            label="gpt image2(2) backup",
            api_key="backup-key",
            base_url="https://yunwu.ai/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2-all",
            size="2048x2048",
            n=1,
        )
        fallback = ImageGenerationSettings(
            id="fallback",
            label="gpt image2(2)",
            api_key="api-xai-key",
            base_url="https://api-xai.ainaibahub.com/v1",
            endpoint_path="/images/generations",
            model="gpt-image-2",
            size="2048x2048",
            n=1,
            retry_alternates=(backup,),
            retry_groups=5,
        )
        settings = SimpleNamespace(
            image=ImageGenerationSettings(
                id="primary",
                label="gpt image2(1)",
                api_key="primary-key",
                base_url="https://primary.example.com/v1",
                endpoint_path="/images/generations",
                model="gpt-image-2-vip",
                size="2048x2048",
                n=0,
            ),
            fallback_image=fallback,
            default_image_option_id="fallback",
            image_options={"fallback": fallback},
        )

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append(settings.model)
            raise RuntimeError(f"{settings.model} down")

        with patch("app.routers.projects.get_model_settings", return_value=settings):
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["hero"], "green_repair", image_model_id="fallback")

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["images"], [])
        self.assertEqual(calls, ["gpt-image-2", "gpt-image-2-all"] * 5)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("failed after 5 retry groups", result["errors"][0])

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
        compose_mock.assert_called_once_with(b"background-bytes", b"product-bytes", module_id="hero", platform_id=None)
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
        settings = SimpleNamespace(
            image=image,
            fallback_image=fallback,
            default_image_option_id="fallback",
            image_options={"primary": image, "fallback": fallback},
        )

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

    async def test_detail_generation_forces_nine_to_sixteen_size(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        calls = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            calls.append(size)
            return ["https://example.com/detail.png"]

        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(["hero"], "green_repair", platform_size="2048x2048")
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(calls, ["1152x2048"])

    async def test_generation_uses_pdd_platform_strategy_in_image_prompt(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        prompts = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            prompts.append(prompt)
            return ["https://example.com/pdd-main.png"]

        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["main_hero_selling_point"],
                    "deep_sea_hydration",
                    product_info={
                        "product_name": "水润保湿精华",
                        "category": "护肤精华",
                        "core_selling_points": ["干皮急救", "妆前服帖"],
                        "functions": ["补水保湿"],
                    },
                    platform_id="pdd",
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertIn("拼多多主图强转化策略", prompts[0])
        self.assertIn("产品占画面 60%-70%", prompts[0])
        self.assertIn("低认知成本、高识别度、高点击转化", prompts[0])
        self.assertNotIn("像天猫", prompts[0])

    async def test_generation_can_select_prompt_optimization_branch(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        prompts = []

        async def fake_call_image_model(settings, prompt, image=None, size=None):
            prompts.append(prompt)
            return ["https://example.com/prompt-optimized.png"]

        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["main_hero_selling_point"],
                    "deep_sea_hydration",
                    product_info={
                        "product_name": "水润保湿精华",
                        "category": "护肤精华",
                        "core_selling_points": ["干皮急救", "妆前服帖"],
                        "functions": ["补水保湿"],
                    },
                    prompt_branch="prompt_optimization",
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertIn("提示词优化分支", prompts[0])
        self.assertIn("premium skincare commercial photography", prompts[0])

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
            with (
                patch("app.routers.projects.call_image_edit_model", new=fake_call_image_edit_model),
                patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("pass")),
            ):
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

    async def test_edit_generated_image_retries_primary_when_selected_fallback_fails(self):
        previous_primary_key = environ.get("IMAGE_GENERATION_API_KEY")
        previous_fallback_key = environ.get("FALLBACK_IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "primary-test-key"
        environ["FALLBACK_IMAGE_GENERATION_API_KEY"] = "fallback-test-key"
        attempted_channels = []

        async def fake_call_image_edit_model(settings, prompt, image_bytes, size=None):
            attempted_channels.append(settings.id)
            if settings.id == "fallback":
                raise RuntimeError("401 Unauthorized")
            return ["https://example.com/primary-edited.png"]

        try:
            with (
                patch("app.routers.projects.call_image_edit_model", new=fake_call_image_edit_model),
                patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("pass")),
            ):
                result = await edit_generated_image(
                    "data:image/png;base64,YWJj",
                    "把按钮改成蓝色",
                    platform_size="800x800",
                    image_model_id="fallback",
                )
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
        self.assertEqual(result["url"], "https://example.com/primary-edited.png")
        self.assertEqual(attempted_channels, ["fallback", "primary"])

    async def test_layered_generation_builds_base_and_default_language_version(self):
        image = Image.new("RGB", (320, 320), (230, 244, 235))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        module = next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point")

        with (
            patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)),
            patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("pass")),
        ):
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

    async def test_ingredient_overview_text_layers_use_specific_benefit_not_placeholder(self):
        layers = build_text_layers(
            {
                "product_name": "水润保湿面霜",
                "category": "面霜",
                "ingredients": [
                    {"name": "透明质酸钠", "benefit": "待确认"},
                    {"name": "烟酰胺", "benefit": ""},
                    {"name": "积雪草提取物", "benefit": "帮助舒缓干燥不适"},
                    {"name": "泛醇", "benefit": "辅助保湿维稳"},
                ],
            },
            next(module for module in ALL_MODULES if module["id"] == "ingredient_overview"),
        )

        layer_text = " / ".join(layer["text"] for layer in layers)
        self.assertIn("透明质酸钠 帮助提升水润肤感", layer_text)
        self.assertNotIn("待确认", layer_text)
        self.assertNotIn("泛醇", layer_text)

    async def test_render_language_version_translates_then_reuses_base_image(self):
        image = Image.new("RGB", (320, 320), (240, 240, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        layers = build_text_layers(
            {"product_name": "修护精华", "core_selling_points": ["深层补水"], "functions": ["水润透亮"]},
            next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point"),
        )

        with (
            patch("app.routers.projects.translate_text_layers", new=AsyncMock(return_value=[{**layers[0], "text": "Deep Hydration"}])),
            patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)),
            patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("pass")),
        ):
            result = await render_layered_language_version(base_url=data_url, layers=layers[:1], language="en")

        self.assertEqual(result["language"], "en")
        self.assertEqual(result["language_label"], "English")
        self.assertTrue(result["url"].startswith("data:image/png;base64,"))
        self.assertEqual(result["layers"][0]["text"], "Deep Hydration")

    async def test_render_language_version_supports_vietnamese(self):
        image = Image.new("RGB", (320, 320), (240, 240, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        layers = build_text_layers(
            {"product_name": "修护精华", "core_selling_points": ["深层补水"], "functions": ["水润透亮"]},
            next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point"),
        )

        with (
            patch("app.routers.projects.translate_text_layers", new=AsyncMock(return_value=[{**layers[0], "text": "Cấp ẩm sâu"}])),
            patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)),
            patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("pass")),
        ):
            result = await render_layered_language_version(base_url=data_url, layers=layers[:1], language="vi")

        self.assertEqual(result["language"], "vi")
        self.assertEqual(result["language_label"], "Tiếng Việt")
        self.assertEqual(result["layers"][0]["text"], "Cấp ẩm sâu")

    async def test_layered_generation_includes_compliance_report(self):
        image = Image.new("RGB", (320, 320), (230, 244, 235))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        module = next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point")

        with (
            patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)),
            patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("block", "medical_claim", "治愈")),
        ):
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

        with (
            patch("app.routers.projects.translate_text_layers", new=AsyncMock(return_value=[{**layers[0], "text": "100% effective"}])),
            patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)),
            patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("block", "absolute_claim", "100%")),
        ):
            result = await render_layered_language_version(base_url=data_url, layers=layers, language="en", platform_id="tmall")

        self.assertEqual(result["compliance"]["summary"]["status"], "block")
        self.assertEqual(result["compliance"]["issues"][0]["category"], "absolute_claim")

    async def test_edit_generated_image_returns_instruction_compliance(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with (
                patch("app.routers.projects.call_image_edit_model", new=AsyncMock(return_value=["https://example.com/edited.png"])),
                patch("app.routers.projects.create_default_compliance_provider", return_value=StaticComplianceProvider("block", "promotion_claim", "全网最低")),
            ):
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

    def test_text_compliance_endpoint_uses_gemini_review(self):
        class FakeComplianceProvider:
            source = "fake_gemini"

            async def review_text(self, items, *, platform_id=None, product_info=None, debug=False):
                return {
                    "summary": {"status": "warn", "block_count": 0, "warn_count": 1, "review_count": 0},
                    "issues": [
                        {
                            "severity": "warn",
                            "category": "medical_claim",
                            "term": "治愈",
                            "matched_text": items[0]["text"],
                            "location": items[0]["location"],
                            "reason": "Gemini 判断该表达存在功效宣称风险。",
                            "suggestion": "改为舒缓不适肤感。",
                        }
                    ],
                }

        with patch("app.routers.projects.create_default_compliance_provider", return_value=FakeComplianceProvider()):
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
        self.assertEqual(payload["source"], "fake_gemini")
        self.assertEqual(payload["summary"]["status"], "warn")
        self.assertEqual(payload["issues"][0]["term"], "治愈")

    def test_edit_image_job_endpoint_returns_pollable_result(self):
        job_result = {
            "source": "model",
            "url": "https://example.com/edited.png",
            "compliance": {"source": "gemini", "summary": {"status": "pass", "block_count": 0, "warn_count": 0, "review_count": 0}, "issues": []},
        }
        with patch("app.routers.projects.edit_generated_image", new=AsyncMock(return_value=job_result)):
            response = self.make_client().post(
                "/api/projects/edit-image/jobs",
                json={
                    "image_url": self.png_data_url(),
                    "instruction": "把标题放大一点",
                    "platform_size": "2048x2048",
                    "image_model_id": "primary",
                    "platform_id": "tmall",
                },
            )

        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        try:
            job_response = self.make_client().get(f"/api/projects/edit-image/jobs/{job_id}")
            self.assertEqual(job_response.status_code, 200)
            job = job_response.json()
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"], job_result)
        finally:
            EDIT_JOBS.pop(job_id, None)

    def test_analyze_materials_job_endpoint_returns_pollable_result(self):
        job_result = {
            "source": "model",
            "product_info": {"product_name": "积雪草修护精华"},
            "raw": '{"product_name":"积雪草修护精华"}',
            "uploaded_materials": [],
        }
        with patch("app.routers.projects.analyze_uploaded_materials", new=AsyncMock(return_value=job_result)):
            response = self.make_client().post(
                "/api/projects/analyze-materials/jobs",
                json={
                    "detail_layout_id": "detail_standard_conversion_10",
                    "materials": [
                        {
                            "id": "material-1",
                            "slot": "documents",
                            "filename": "product.txt",
                            "content_type": "text/plain",
                            "text": "积雪草修护精华",
                        }
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        try:
            job_response = self.make_client().get(f"/api/projects/analyze-materials/jobs/{job_id}")
            self.assertEqual(job_response.status_code, 200)
            job = job_response.json()
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"], job_result)
        finally:
            from app.routers import projects

            projects.ANALYSIS_JOBS.pop(job_id, None)

    def test_plan_style_job_endpoint_returns_pollable_result(self):
        job_result = {
            "source": "model",
            "style": {"id": "ai_custom", "name": "AI 自定义风格"},
            "raw": "{}",
            "warnings": [],
        }
        with patch("app.routers.projects.plan_custom_style", new=AsyncMock(return_value=job_result)):
            response = self.make_client().post(
                "/api/projects/plan-style/jobs",
                json={
                    "product_info": {"product_name": "积雪草修护精华"},
                    "product_images": [{"filename": "product.png", "content_type": "image/png", "data_url": self.png_data_url()}],
                },
            )

        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        try:
            job_response = self.make_client().get(f"/api/projects/plan-style/jobs/{job_id}")
            self.assertEqual(job_response.status_code, 200)
            job = job_response.json()
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"], job_result)
        finally:
            STYLE_JOBS.pop(job_id, None)

    def test_analyze_style_reference_job_endpoint_returns_pollable_result(self):
        job_result = {
            "source": "model",
            "style": {"id": "ai_reference", "name": "图片对标风格"},
            "raw": "{}",
            "uploaded_style_references": [],
            "warnings": [],
        }
        with patch("app.routers.projects.analyze_style_reference", new=AsyncMock(return_value=job_result)):
            response = self.make_client().post(
                "/api/projects/analyze-style-reference/jobs",
                json={
                    "product_info": {"product_name": "积雪草修护精华"},
                    "style_reference_images": [{"filename": "style.png", "content_type": "image/png", "data_url": self.png_data_url()}],
                },
            )

        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        try:
            job_response = self.make_client().get(f"/api/projects/analyze-style-reference/jobs/{job_id}")
            self.assertEqual(job_response.status_code, 200)
            job = job_response.json()
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"], job_result)
        finally:
            STYLE_JOBS.pop(job_id, None)

    def test_plan_style_sample_job_endpoint_returns_pollable_result(self):
        job_result = {
            "source": "model",
            "style": {"id": "ai_custom", "name": "AI 自定义风格", "asset": self.png_data_url()},
            "warnings": [],
        }
        with patch("app.routers.projects.generate_custom_style_sample", new=AsyncMock(return_value=job_result)):
            response = self.make_client().post(
                "/api/projects/plan-style-sample/jobs",
                json={
                    "style": {"id": "ai_custom", "name": "AI 自定义风格"},
                    "product_info": {"product_name": "积雪草修护精华"},
                },
            )

        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]
        try:
            job_response = self.make_client().get(f"/api/projects/plan-style-sample/jobs/{job_id}")
            self.assertEqual(job_response.status_code, 200)
            job = job_response.json()
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["result"], job_result)
        finally:
            STYLE_JOBS.pop(job_id, None)

    def test_image_compliance_endpoint_uses_gemini_image_review(self):
        class FakeComplianceProvider:
            source = "fake_gemini"

            async def review_image(self, image_bytes, *, metadata, platform_id=None, product_info=None, debug=False):
                return {
                    "summary": {"status": "block", "block_count": 1, "warn_count": 0, "review_count": 0},
                    "issues": [
                        {
                            "severity": "block",
                            "category": "absolute_claim",
                            "term": "100%",
                            "matched_text": "100%有效",
                            "location": metadata["location"],
                            "reason": "Gemini 判断图片中存在绝对化表达。",
                            "suggestion": "删除或改为有依据的数据表达。",
                        }
                    ],
                }

        with patch("app.routers.projects.create_default_compliance_provider", return_value=FakeComplianceProvider()):
            response = self.make_client().post(
                "/api/projects/compliance/check-images",
                json={"platform_id": "tmall", "image_urls": [self.png_data_url()]},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "fake_gemini")
        self.assertEqual(payload["summary"]["status"], "block")
        self.assertEqual(payload["issues"][0]["term"], "100%")
        self.assertEqual(payload["issues"][0]["location"]["source_type"], "image_review")
        self.assertEqual(set(payload), {"source", "summary", "issues", "image_count", "warnings"})


class SavedStylesContractTests(unittest.TestCase):
    def make_client(self) -> TestClient:
        from app.routers.styles import router as styles_router

        app = FastAPI()
        app.dependency_overrides[require_app_user] = lambda: AppSessionUserSnapshot(user_id="test-user")
        app.include_router(styles_router)
        return TestClient(app)

    def test_save_style_endpoint_uses_current_user(self):
        saved_record = {
            "id": "style-1",
            "name": "冷萃晶透风",
            "style": {
                "id": "style_reference",
                "name": "冷萃晶透风",
                "keywords": ["冷感"],
                "primary_color": "#A8DDE8",
            },
            "created_at": "2026-05-14T00:00:00+00:00",
            "updated_at": "2026-05-14T00:00:00+00:00",
        }
        with patch("app.routers.styles.save_style", new=AsyncMock(return_value=saved_record)) as save_mock:
            response = self.make_client().post(
                "/api/styles/saved",
                json={
                    "name": "冷萃晶透风",
                    "style": {
                        "id": "style_reference",
                        "name": "旧名",
                        "keywords": ["冷感"],
                        "primary_color": "#A8DDE8",
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["style"]["name"], "冷萃晶透风")
        self.assertEqual(save_mock.call_args.args[0], "test-user")

    def test_list_style_endpoint_returns_current_user_records(self):
        with patch(
            "app.routers.styles.list_saved_styles",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "style-1",
                        "name": "冷萃晶透风",
                        "style": {
                            "id": "style_reference",
                            "name": "冷萃晶透风",
                            "keywords": ["冷感"],
                            "primary_color": "#A8DDE8",
                        },
                        "created_at": "2026-05-14T00:00:00+00:00",
                        "updated_at": "2026-05-14T00:00:00+00:00",
                    }
                ]
            ),
        ) as list_mock:
            response = self.make_client().get("/api/styles/saved")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["name"], "冷萃晶透风")
        self.assertEqual(list_mock.call_args.args[0], "test-user")

    def test_delete_style_endpoint_deletes_current_user_record(self):
        with patch("app.routers.styles.delete_saved_style", new=AsyncMock(return_value=True)) as delete_mock:
            response = self.make_client().delete("/api/styles/saved/style-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True, "id": "style-1"})
        self.assertEqual(delete_mock.call_args.args, ("test-user", "style-1"))


if __name__ == "__main__":
    unittest.main()
