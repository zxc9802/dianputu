import asyncio
import unittest
from os import environ
from unittest.mock import AsyncMock, patch

from app.routers.projects import (
    UploadedMaterial,
    analyze_uploaded_materials,
    build_material_analysis_messages,
    generate_detail_images,
    normalize_product_info_from_model,
)
from app.services.prompt_builder import build_module_image_prompt


class MaterialAnalysisTests(unittest.TestCase):
    def test_multimodal_message_includes_uploaded_image_data_uri(self):
        messages = build_material_analysis_messages(
            [
                UploadedMaterial(
                    filename="main-product.png",
                    content_type="image/png",
                    data=b"\x89PNG\r\n",
                )
            ]
        )

        self.assertEqual(messages[0]["role"], "user")
        content = messages[0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertIn("main-product.png", content[0]["text"])
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_model_json_is_normalized_to_product_info(self):
        product_info = normalize_product_info_from_model(
            """
            ```json
            {
              "product_name": "玻色因紧致精华",
              "category": "护肤精华",
              "core_selling_points": ["紧致淡纹"],
              "functions": ["抗老", "紧致"],
              "ingredients": [{"name": "玻色因", "benefit": "支撑肌肤弹性"}],
              "usage_method": ["早晚使用"],
              "authority_assets": ["实验室测试"],
              "effect_claims": [{"claim": "细纹改善", "value": "87%", "source_type": "ai_generated"}]
            }
            ```
            """
        )

        self.assertEqual(product_info["product_name"], "玻色因紧致精华")
        self.assertEqual(product_info["ingredients"][0]["name"], "玻色因")
        self.assertEqual(product_info["confirmation_status"], "pending")

    def test_missing_model_fields_do_not_use_demo_product_copy(self):
        product_info = normalize_product_info_from_model('{"product_name": "Only Name"}')

        self.assertEqual(product_info["product_name"], "Only Name")
        self.assertEqual(product_info["core_selling_points"], [])
        self.assertEqual(product_info["ingredients"], [])
        self.assertEqual(product_info["effect_claims"], [])


    def test_main_image_prompts_use_module_specific_briefs_and_visual_constraints(self):
        product_info = {
            "product_name": "积雪草修护精华",
            "category": "护肤精华",
            "core_selling_points": ["舒缓修护", "清爽不黏腻", "屏障护理"],
            "functions": ["舒缓泛红", "补水保湿"],
            "ingredients": [{"name": "积雪草", "benefit": "帮助舒缓肌肤"}],
            "target_users": ["敏感肌人群"],
            "usage_method": ["早晚洁面后使用"],
            "authority_assets": ["实验室测试报告"],
            "effect_claims": [{"claim": "保湿提升", "value": "89%", "source_type": "ai_generated"}],
        }
        style = {"name": "绿色修护风", "primary_color": "#4E8F69", "keywords": ["清透", "自然"]}

        ingredient_prompt = build_module_image_prompt(
            product_info=product_info,
            style=style,
            module={"id": "main_ingredient", "name": "次图-成分", "description": "核心成分 + 原料质感", "image_group": "main"},
            module_index=3,
            total_modules=5,
        )
        effect_prompt = build_module_image_prompt(
            product_info=product_info,
            style=style,
            module={"id": "main_effect", "name": "次图-效果", "description": "核心功效 + 使用收益", "image_group": "main"},
            module_index=4,
            total_modules=5,
        )

        self.assertIn("当前模块精简 brief", ingredient_prompt)
        self.assertIn("左右分栏", ingredient_prompt)
        self.assertIn("原料实物微距特写", ingredient_prompt)
        self.assertIn("禁止出现：效果数据百分比", ingredient_prompt)
        self.assertIn("成分：积雪草", ingredient_prompt)
        self.assertNotIn("权威资料小报告", ingredient_prompt)
        self.assertNotIn("目标人群：", ingredient_prompt)

        self.assertIn("上下分区", effect_prompt)
        self.assertIn("数据仪表盘", effect_prompt)
        self.assertIn("禁止出现：成分详情列表", effect_prompt)
        self.assertIn("指标：保湿提升", effect_prompt)
        self.assertNotIn("权威资料小报告", effect_prompt)
        self.assertNotIn("成分：积雪草", effect_prompt)
    def test_white_background_prompt_preserves_product_packaging(self):
        prompt = build_module_image_prompt(
            product_info={"product_name": "积雪草修护精华", "spec": "30ml"},
            style={"name": "绿色修护风", "primary_color": "#4E8F69", "keywords": ["清透", "自然"]},
            module={"id": "main_white_bg", "name": "白底图", "description": "纯白背景 + 产品居中", "image_group": "main"},
            module_index=1,
            total_modules=5,
        )

        self.assertIn("抠图换白底", prompt)
        self.assertIn("只删除原背景", prompt)
        self.assertIn("标签文字、Logo、图案", prompt)
        self.assertIn("不能把产品标签抹成空白", prompt)
        self.assertIn("不能重绘包装", prompt)


class AnalyzeUploadedMaterialsConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_uploaded_materials_reports_missing_text_model_key_separately(self):
        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.text.api_key = ""

            result = await analyze_uploaded_materials(
                [UploadedMaterial(filename="test.txt", content_type="text/plain", data=b"product", text="product")]
            )

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["error"], "text model is not configured")


class GenerationMaterialTests(unittest.IsolatedAsyncioTestCase):
    async def test_generation_prompt_uses_product_info_and_reference_images(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/hero.png"])) as mocked:
                result = await generate_detail_images(
                    ["hero"],
                    "green_repair",
                    product_info={"product_name": "玻色因紧致精华", "category": "护肤精华"},
                    reference_images=["data:image/png;base64,abc"],
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        prompt = mocked.call_args.args[1] if len(mocked.call_args.args) > 1 else mocked.call_args.kwargs["prompt"]
        reference_images = mocked.call_args.kwargs["image"]
        self.assertIn("玻色因紧致精华", prompt)
        self.assertIn("固定模块结构", prompt)
        self.assertIn("当前模块：详情首图", prompt)
        self.assertIn("只生成当前模块", prompt)
        self.assertEqual(reference_images, ["data:image/png;base64,abc"])
    async def test_campaign_generation_prompt_uses_promotion_info(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/campaign.png"])) as mocked:
                result = await generate_detail_images(
                    ["campaign_hero_selling_point"],
                    "green_repair",
                    product_info={"product_name": "玻色因紧致精华", "category": "护肤精华"},
                    promotion_info="618 限时 8 折，满 199 减 30",
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        prompt = mocked.call_args.args[1] if len(mocked.call_args.args) > 1 else mocked.call_args.kwargs["prompt"]
        self.assertIn("活动促销信息", prompt)
        self.assertIn("618 限时 8 折，满 199 减 30", prompt)
        self.assertIn("中文电商活动主图", prompt)
    async def test_white_background_generation_reuses_product_reference_image(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/changed.png"])) as mocked:
                result = await generate_detail_images(
                    ["main_white_bg"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                    reference_images=["data:image/png;base64,original"],
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["images"], [{"module_id": "main_white_bg", "url": "data:image/png;base64,original"}])
        mocked.assert_not_called()

    async def test_generation_runs_image_calls_concurrently(self):
        started = 0
        release = asyncio.Event()

        async def fake_call_image_model(settings, prompt, image=None):
            nonlocal started
            started += 1
            if started == 2:
                release.set()
            await asyncio.wait_for(release.wait(), timeout=1)
            return [f"https://example.com/{started}.png"]

        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["main_ingredient", "main_effect"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual([image["module_id"] for image in result["images"]], ["main_ingredient", "main_effect"])
    async def test_image_generation_falls_back_per_image_without_disabling_primary(self):
        calls = []

        async def fake_call_image_model(settings, prompt, image=None):
            calls.append(settings.model)
            if settings.model == "gpt-image-2" and len([model for model in calls if model == "gpt-image-2"]) == 1:
                raise RuntimeError("primary failed once")
            return [f"https://example.com/{settings.model}-{len(calls)}.png"]

        previous_primary_key = environ.get("IMAGE_GENERATION_API_KEY")
        previous_fallback_key = environ.get("FALLBACK_IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "primary-key"
        environ["FALLBACK_IMAGE_GENERATION_API_KEY"] = "fallback-key"
        try:
            with patch("app.routers.projects.call_image_model", new=fake_call_image_model):
                result = await generate_detail_images(
                    ["main_ingredient", "main_effect"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
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
        self.assertEqual(calls, ["gpt-image-2", "gpt-image-2-all", "gpt-image-2"])
        self.assertIn("gpt-image-2-all", result["images"][0]["url"])
        self.assertIn("gpt-image-2", result["images"][1]["url"])


if __name__ == "__main__":
    unittest.main()
