import asyncio
import unittest
from os import environ
from unittest.mock import AsyncMock, patch

from app.routers.projects import (
    UploadedMaterial,
    analyze_product_visuals,
    analyze_uploaded_materials,
    build_custom_style_sample_prompt,
    build_material_analysis_messages,
    build_product_visual_analysis_messages,
    build_style_planning_messages,
    generate_custom_style_sample,
    generate_detail_images,
    normalize_product_visual_suggestion_from_model,
    normalize_product_info_from_model,
    normalize_style_plan_from_model,
    prepare_compose_image_urls,
    plan_custom_style,
    run_compose_job,
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

    def test_product_visual_analysis_message_includes_product_image(self):
        messages = build_product_visual_analysis_messages(
            UploadedMaterial(
                filename="main-product.png",
                content_type="image/png",
                data=b"\x89PNG\r\n",
                slot="product_image",
            ),
            {"product_name": "琉光面霜", "category": "面霜乳液"},
        )

        content = messages[0]["content"]
        self.assertIn("根据产品图给出电商视觉建议", content[0]["text"])
        self.assertIn("琉光面霜", content[0]["text"])
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

    def test_model_json_is_normalized_to_custom_style_plan(self):
        style = normalize_style_plan_from_model(
            """
            ```json
            {
              "name": "微晶冻感修护风",
              "primary_color": "#8ECFE6",
              "keywords": ["微晶", "冻感", "舒缓"],
              "visual_direction": "透明凝胶质感、冷感光影、留白高级",
              "layout_guidance": "主图用产品大图配半透明凝胶纹理，详情页用模块化卡片承接数据",
              "reasoning": "包装为浅蓝色，适合突出清透舒缓和修护科技感"
            }
            ```
            """
        )

        self.assertEqual(style["id"], "ai_custom")
        self.assertEqual(style["name"], "微晶冻感修护风")
        self.assertEqual(style["primary_color"], "#8ECFE6")
        self.assertEqual(style["keywords"], ["微晶", "冻感", "舒缓"])
        self.assertIn("透明凝胶", style["visual_direction"])
        self.assertIn("模块化卡片", style["layout_guidance"])

    def test_model_json_is_normalized_to_product_visual_suggestion(self):
        suggestion = normalize_product_visual_suggestion_from_model(
            """
            {
              "recommended_colors": ["#D8C7B4", "#F4EFE8", "#8A6A55", "bad"],
              "keywords": ["柔光", "滋润", "高级"],
              "visual_direction": "暖调柔光和半透明膏霜质感",
              "reasoning": "产品包装偏暖米色，适合表现滋润修护"
            }
            """
        )

        self.assertEqual(suggestion["recommended_colors"], ["#D8C7B4", "#F4EFE8", "#8A6A55"])
        self.assertEqual(suggestion["keywords"], ["柔光", "滋润", "高级"])
        self.assertIn("暖调柔光", suggestion["visual_direction"])

    def test_style_planning_message_asks_gemini_to_create_not_choose(self):
        messages = build_style_planning_messages(
            {
                "product_name": "积雪草修护精华",
                "category": "护肤精华",
                "core_selling_points": ["舒缓泛红", "屏障修护"],
            },
            "护肤精华",
            ["#D8F1EA", "#2D8C6F"],
        )

        text = messages[0]["content"]
        self.assertIn("规划一个全新的电商视觉风格", text)
        self.assertIn("不要从现有三套预设风格里选择", text)
        self.assertIn("积雪草修护精华", text)
        self.assertIn("#D8F1EA", text)


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
    async def test_analyze_product_visuals_calls_gemini_with_product_image(self):
        captured_messages = []

        async def fake_call_text_model(settings, messages):
            captured_messages.extend(messages)
            return '{"recommended_colors":["#D8C7B4"],"keywords":["柔光"],"visual_direction":"暖调柔光","reasoning":"匹配包装"}'

        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.text.api_key = "text-key"
            with patch("app.routers.projects.call_text_model", new=fake_call_text_model):
                result = await analyze_product_visuals(
                    UploadedMaterial(filename="main.png", content_type="image/png", data=b"\x89PNG\r\n"),
                    {"product_name": "琉光面霜"},
                )

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["suggestion"]["recommended_colors"], ["#D8C7B4"])
        self.assertEqual(captured_messages[0]["content"][1]["type"], "image_url")

    async def test_analyze_uploaded_materials_reports_missing_text_model_key_separately(self):
        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.text.api_key = ""
            mocked_settings.return_value.fallback_text.api_key = ""

            result = await analyze_uploaded_materials(
                [UploadedMaterial(filename="test.txt", content_type="text/plain", data=b"product", text="product")]
            )

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["error"], "text model is not configured")

    async def test_analyze_uploaded_materials_uses_r2_urls_for_uploaded_images(self):
        captured_messages = []

        async def fake_call_text_model(settings, messages):
            captured_messages.extend(messages)
            return '{"product_name":"积雪草修护精华"}'

        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.text.api_key = "text-key"
            with (
                patch("app.routers.projects.upload_material_image_if_configured", new=AsyncMock(return_value="https://img.example.com/prod/materials/main.png")) as upload_mocked,
                patch("app.routers.projects.call_text_model", new=fake_call_text_model),
            ):
                result = await analyze_uploaded_materials(
                    [UploadedMaterial(filename="main.png", content_type="image/png", data=b"\x89PNG\r\n")]
                )

        self.assertEqual(result["source"], "model")
        upload_mocked.assert_awaited_once()
        content = captured_messages[0]["content"]
        self.assertEqual(content[1]["image_url"]["url"], "https://img.example.com/prod/materials/main.png")

    async def test_analyze_uploaded_materials_falls_back_to_secondary_text_model(self):
        calls = []

        async def fake_call_text_model(settings, messages):
            calls.append(settings.model)
            if settings.model == "gemini-3.1-pro-preview":
                raise RuntimeError("primary unavailable")
            return '{"product_name":"积雪草修护精华"}'

        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.text.api_key = "primary-key"
            mocked_settings.return_value.text.model = "gemini-3.1-pro-preview"
            mocked_settings.return_value.fallback_text.api_key = "fallback-key"
            mocked_settings.return_value.fallback_text.model = "gpt-5.5"
            with patch("app.routers.projects.call_text_model", new=fake_call_text_model):
                result = await analyze_uploaded_materials(
                    [UploadedMaterial(filename="test.txt", content_type="text/plain", data=b"product", text="product")]
                )

        self.assertEqual(result["source"], "model")
        self.assertEqual(calls, ["gemini-3.1-pro-preview", "gpt-5.5"])

    async def test_plan_custom_style_calls_text_model_and_returns_style_without_generating_sample(self):
        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.text.api_key = "text-key"
            mocked_settings.return_value.image.api_key = "image-key"
            with patch(
                "app.routers.projects.call_text_model",
                new=AsyncMock(
                    return_value='{"name":"微晶冻感修护风","primary_color":"#8ECFE6","keywords":["微晶","冻感"],"visual_direction":"清透冷感","layout_guidance":"主图留白，详情页卡片化","reasoning":"匹配包装色"}'
                ),
            ) as text_mocked:
                with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/style-sample.png"])) as image_mocked:
                    result = await plan_custom_style(
                        product_info={"product_name": "积雪草修护精华", "category": "护肤精华"},
                        category="护肤精华",
                        brand_colors=["#8ECFE6"],
                    )

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["style"]["id"], "ai_custom")
        self.assertEqual(result["style"]["name"], "微晶冻感修护风")
        self.assertIn("清透冷感", result["style"]["visual_direction"])
        self.assertEqual(result["style"]["asset"], "")
        self.assertIn("积雪草修护精华", text_mocked.call_args.args[1][0]["content"])
        image_mocked.assert_not_called()

    async def test_generate_custom_style_sample_uses_image_model_and_returns_asset(self):
        style = {
            "id": "ai_custom",
            "name": "微晶冻感修护风",
            "primary_color": "#8ECFE6",
            "keywords": ["微晶", "冻感"],
            "asset": "",
            "visual_direction": "清透冷感",
            "layout_guidance": "主图留白，详情页卡片化",
        }
        with patch("app.routers.projects.get_model_settings") as mocked_settings:
            mocked_settings.return_value.image.api_key = "image-key"
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/style-sample.png"])) as image_mocked:
                result = await generate_custom_style_sample(
                    style=style,
                    product_info={"product_name": "积雪草修护精华", "category": "护肤精华"},
                )

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["style"]["asset"], "https://example.com/style-sample.png")
        self.assertIn("风格样例图", image_mocked.call_args.args[1])

    def test_custom_style_sample_prompt_uses_style_and_product_context(self):
        prompt = build_custom_style_sample_prompt(
            {
                "name": "琉光云纱凝润美学",
                "primary_color": "#EBE9E9",
                "keywords": ["琉光透润", "柔纱触感"],
                "visual_direction": "暖调米白与晨光香槟色，半透明柔纱和凝固透明树脂",
                "layout_guidance": "主图留白，详情页使用柔和卡片",
            },
            {"product_name": "LUMERA HYDRA CREAM", "category": "面霜乳液"},
        )

        self.assertIn("风格样例图", prompt)
        self.assertIn("琉光云纱凝润美学", prompt)
        self.assertIn("LUMERA HYDRA CREAM", prompt)
        self.assertIn("不要生成真实品牌 Logo", prompt)


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

    async def test_generation_uses_custom_style_brief_when_provided(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        custom_style = {
            "id": "ai_custom",
            "name": "微晶冻感修护风",
            "primary_color": "#8ECFE6",
            "keywords": ["微晶", "冻感"],
            "visual_direction": "透明凝胶质感、冷感光影、留白高级",
            "layout_guidance": "主图用产品大图配半透明凝胶纹理，详情页用模块化卡片承接数据",
        }
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/hero.png"])) as mocked:
                result = await generate_detail_images(
                    ["hero"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                    custom_style=custom_style,
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        prompt = mocked.call_args.args[1] if len(mocked.call_args.args) > 1 else mocked.call_args.kwargs["prompt"]
        self.assertIn("微晶冻感修护风", prompt)
        self.assertIn("透明凝胶质感", prompt)
        self.assertIn("模块化卡片", prompt)

    async def test_generation_sends_style_reference_images_separately_and_prefers_style_reference_prompt(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/hero.png"])) as mocked:
                result = await generate_detail_images(
                    ["hero"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                    reference_images=["data:image/png;base64,product"],
                    style_reference_images=["data:image/png;base64,style"],
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        prompt = mocked.call_args.args[1] if len(mocked.call_args.args) > 1 else mocked.call_args.kwargs["prompt"]
        self.assertIn("上传的风格参考图优先", prompt)
        self.assertEqual(mocked.call_args.kwargs["image"], ["data:image/png;base64,product", "data:image/png;base64,style"])

    async def test_white_background_ignores_style_reference_images(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/changed.png"])) as mocked:
                result = await generate_detail_images(
                    ["main_white_bg"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                    reference_images=["data:image/png;base64,product"],
                    style_reference_images=["data:image/png;base64,style"],
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["images"], [{"module_id": "main_white_bg", "url": "data:image/png;base64,product"}])
        mocked.assert_not_called()
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

    async def test_white_background_generation_requires_product_reference_image(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/redrawn.png"])) as mocked:
                result = await generate_detail_images(
                    ["main_white_bg", "campaign_white_bg"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "error")
        self.assertEqual(result["images"], [])
        self.assertIn("白底图需要先上传产品图", result["errors"][0])
        mocked.assert_not_called()

    async def test_generation_runs_image_calls_concurrently(self):
        started = 0
        release = asyncio.Event()

        async def fake_call_image_model(settings, prompt, image=None, size=None):
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

        async def fake_call_image_model(settings, prompt, image=None, size=None):
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

    async def test_generated_data_urls_are_uploaded_to_object_storage(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with (
                patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["data:image/png;base64,aGVsbG8="])),
                patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(return_value="https://img.example.com/prod/generated/hero.png")) as upload_mocked,
            ):
                result = await generate_detail_images(
                    ["main_ingredient"],
                    "green_repair",
                    product_info={"product_name": "积雪草修护精华"},
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["images"], [{"module_id": "main_ingredient", "url": "https://img.example.com/prod/generated/hero.png"}])
        upload_mocked.assert_awaited_once()

    async def test_edited_data_url_is_uploaded_to_object_storage(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with (
                patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["data:image/png;base64,aGVsbG8="])),
                patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(return_value="https://img.example.com/prod/edited/image.png")),
            ):
                from app.routers.projects import edit_generated_image

                result = await edit_generated_image("https://example.com/source.png", "加一点水光")
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result, {"source": "model", "url": "https://img.example.com/prod/edited/image.png"})

    async def test_compose_job_uploads_finished_jpeg_to_object_storage(self):
        from app.routers import projects

        projects.COMPOSE_JOBS["compose_test"] = {
            "status": "pending",
            "stage": "pending",
            "current": 0,
            "total": 1,
            "message": "等待开始合成",
            "content": b"",
            "created_at": "2026-05-07T00:00:00+00:00",
        }
        try:
            with (
                patch("app.routers.projects.compose_long_jpeg", new=AsyncMock(return_value=b"jpeg-bytes")),
                patch("app.routers.projects.upload_bytes_if_configured", new=AsyncMock(return_value="https://img.example.com/prod/composed/full-detail.jpg")),
            ):
                await run_compose_job("compose_test", ["data:image/png;base64,aGVsbG8="])

            job = projects.COMPOSE_JOBS["compose_test"]
            self.assertEqual(job["status"], "done")
            self.assertEqual(job["url"], "https://img.example.com/prod/composed/full-detail.jpg")
            self.assertEqual(job["content"], b"")
        finally:
            projects.COMPOSE_JOBS.pop("compose_test", None)

    async def test_prepare_compose_image_urls_uploads_data_urls_before_job_creation(self):
        with patch(
            "app.routers.projects.upload_image_url_if_configured",
            new=AsyncMock(side_effect=["https://img.example.com/composed/source-1.png", "https://img.example.com/source-2.png"]),
        ) as upload_mocked:
            result = await prepare_compose_image_urls(
                [
                    "data:image/png;base64,aGVsbG8=",
                    "https://img.example.com/source-2.png",
                ]
            )

        self.assertEqual(result, ["https://img.example.com/composed/source-1.png", "https://img.example.com/source-2.png"])
        upload_mocked.assert_any_await("data:image/png;base64,aGVsbG8=", "compose-sources")
        upload_mocked.assert_any_await("https://img.example.com/source-2.png", "compose-sources")


if __name__ == "__main__":
    unittest.main()
