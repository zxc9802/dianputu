import unittest

from app.demo_data import DEFAULT_MODULES, STYLE_OPTIONS


def load_prompt_builder():
    try:
        from app.services.prompt_builder import build_module_image_prompt
    except (ModuleNotFoundError, ImportError) as exc:
        raise AssertionError("build_module_image_prompt should be implemented") from exc
    return build_module_image_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_authority_prompt_prefers_lab_scientist_scene_and_soft_report_visuals(self):
        build_module_image_prompt = load_prompt_builder()
        authority_module = next(module for module in DEFAULT_MODULES if module["id"] == "authority")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "用户修改后的 CICA 精华",
                "category": "屏障修护精华",
                "spec": "50ml",
                "core_selling_points": ["用户补充的强韧屏障卖点"],
                "functions": ["舒缓泛红", "屏障修护"],
                "ingredients": [{"name": "积雪草提取物", "benefit": "帮助舒缓脆弱肌肤"}],
                "target_users": ["换季泛红人群"],
                "usage_method": ["洁面后取 2-3 滴涂抹"],
                "authority_assets": [
                    "SGS 第三方检测报告：经皮水分流失测试，样本 32 人，连续 14 天，报告编号 SGS-CICA-2026-042"
                ],
                "effect_claims": [],
            },
            style=STYLE_OPTIONS[0],
            module=authority_module,
            module_index=2,
            total_modules=7,
        )

        self.assertIn("固定模块结构", prompt)
        self.assertIn("只生成当前模块", prompt)
        self.assertIn("不能新增一级模块", prompt)
        self.assertIn("当前模块：权威资质展示", prompt)
        self.assertIn("用户修改后的 CICA 精华", prompt)
        self.assertIn("用户补充的强韧屏障卖点", prompt)
        self.assertIn("SGS 第三方检测报告", prompt)
        self.assertIn("科学家/研究员", prompt)
        self.assertIn("实验室", prompt)
        self.assertIn("报告轮廓", prompt)
        self.assertIn("文字要小", prompt)
        self.assertIn("不写具体报告编号", prompt)
        self.assertNotIn("样本 32 人", prompt)
        self.assertNotIn("SGS-CICA-2026-042", prompt)

    def test_effect_prompt_contains_complete_metrics_sources_and_compliance_limits(self):
        build_module_image_prompt = load_prompt_builder()
        effect_module = next(module for module in DEFAULT_MODULES if module["id"] == "effect_comparison")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "玻色因紧致精华",
                "category": "抗老精华",
                "spec": "30ml",
                "core_selling_points": ["紧致淡纹"],
                "functions": ["紧致", "淡纹"],
                "ingredients": [{"name": "玻色因", "benefit": "支撑肌肤弹性"}],
                "target_users": ["初老肌人群"],
                "usage_method": ["早晚使用"],
                "authority_assets": [],
                "effect_claims": [
                    {"claim": "肌肤含水量提升", "value": "92%", "source_type": "14 天人体功效测试"},
                    {"claim": "细纹观感改善", "value": "87%", "source_type": "ai_generated"},
                ],
            },
            style=STYLE_OPTIONS[0],
            module=effect_module,
            module_index=4,
            total_modules=7,
        )

        self.assertIn("当前模块：效果对比", prompt)
        self.assertIn("肌肤含水量提升", prompt)
        self.assertIn("92%", prompt)
        self.assertIn("14 天人体功效测试", prompt)
        self.assertIn("细纹观感改善", prompt)
        self.assertIn("87%", prompt)
        self.assertIn("ai_generated", prompt)
        self.assertIn("示意型数据", prompt)
        self.assertIn("避免绝对化医疗表达", prompt)

    def test_style_reference_prompt_overrides_preset_style_for_non_white_background_images(self):
        build_module_image_prompt = load_prompt_builder()
        hero_module = next(module for module in DEFAULT_MODULES if module["id"] == "hero")

        prompt = build_module_image_prompt(
            product_info={"product_name": "积雪草修护精华"},
            style=STYLE_OPTIONS[0],
            module=hero_module,
            module_index=1,
            total_modules=7,
            has_style_reference=True,
        )

        self.assertIn("上传的风格参考图优先", prompt)
        self.assertIn("只参考排版、色调、光影和氛围", prompt)
        self.assertIn("不要混入预设风格", prompt)
        self.assertNotIn("预设风格只作为兜底", prompt)
        self.assertNotIn("绿色修护风", prompt)


if __name__ == "__main__":
    unittest.main()
