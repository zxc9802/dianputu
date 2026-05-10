import unittest

from app.demo_data import DEFAULT_MODULES, STYLE_OPTIONS


def load_prompt_builder():
    try:
        from app.services.prompt_builder import build_module_image_prompt
    except (ModuleNotFoundError, ImportError) as exc:
        raise AssertionError("build_module_image_prompt should be implemented") from exc
    return build_module_image_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_authority_prompt_prefers_scientist_lab_scene_with_paper_report_support(self):
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
        self.assertIn("科学家实验画面为主体", prompt)
        self.assertIn("研究员", prompt)
        self.assertIn("实验室", prompt)
        self.assertIn("显微镜", prompt)
        self.assertIn("纸质资质只占画面局部", prompt)
        self.assertIn("不超过画面 25%", prompt)
        self.assertIn("纸张纤维", prompt)
        self.assertIn("不要半透明 UI 卡片", prompt)
        self.assertIn("不要让纸质资质成为主视觉", prompt)
        self.assertIn("不写具体报告编号", prompt)
        self.assertIn("安心品质", prompt)
        self.assertIn("真实保障", prompt)
        self.assertIn("成分可信", prompt)
        self.assertIn("品控流程", prompt)
        self.assertIn("使用放心", prompt)
        self.assertNotIn("研发资质感呈现", prompt)
        self.assertNotIn("核心视觉必须是真实纸质检测报告", prompt)
        self.assertNotIn("不要把实验室人物当作主视觉", prompt)
        self.assertNotIn("样本 32 人", prompt)
        self.assertNotIn("SGS-CICA-2026-042", prompt)

    def test_detail_prompts_keep_hidden_notes_out_of_visible_image_copy(self):
        build_module_image_prompt = load_prompt_builder()
        authority_module = next(module for module in DEFAULT_MODULES if module["id"] == "authority")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "CICA 修护精华",
                "authority_assets": ["实验室研发", "实验报告", "专研配方理念"],
            },
            style=STYLE_OPTIONS[0],
            module=authority_module,
            module_index=2,
            total_modules=7,
        )

        self.assertIn("图片必须像可直接用于店铺上架的成品物料", prompt)
        self.assertIn("隐藏 brief、模块职责、资料限制、合规提醒只作为生成依据", prompt)
        self.assertIn("不能排版成图片里的说明框、段落、清单、脚注或底部文字区域", prompt)
        self.assertIn("纸质资质只作为辅助物件", prompt)
        self.assertIn("当报告出现时只能做成真实纸质材质", prompt)
        self.assertIn("仅短标题、极短标签、必要数值或步骤编号需要清晰可读", prompt)
        self.assertNotIn("数据/说明区", prompt)
        self.assertNotIn("底部补充区", prompt)
        self.assertNotIn("1-2 句克制的权威背书短文案", prompt)
        self.assertNotIn("说明文字清晰可读", prompt)
        self.assertNotIn("免责声明", prompt)
        self.assertNotIn("占位纹理", prompt)
        self.assertNotIn("半透明报告轮廓卡片", prompt)

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
        self.assertNotIn("ai_generated", prompt)
        self.assertIn("体验型视觉", prompt)
        self.assertIn("避免绝对化医疗表达", prompt)
        self.assertIn("局部前后对比组件", prompt)
        self.assertIn("不要让左右对比占满整张画面", prompt)
        self.assertIn("产品主体、标题、使用前/使用后局部对比卡片", prompt)
        self.assertIn("功效说明或数据指标区", prompt)
        self.assertIn("约 30%-45%", prompt)
        self.assertNotIn("全屏左右分屏", prompt)

    def test_hydration_effect_prompt_uses_prominent_increase_percent_metric(self):
        build_module_image_prompt = load_prompt_builder()
        effect_module = next(module for module in DEFAULT_MODULES if module["id"] == "effect_comparison")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿精华",
                "functions": ["补水保湿", "改善干燥"],
                "effect_claims": [
                    {"claim": "肌肤含水量提升", "value": "92%", "source_type": "14 天人体功效测试"},
                ],
            },
            style=STYLE_OPTIONS[0],
            module=effect_module,
            module_index=4,
            total_modules=7,
        )

        self.assertIn("水润数据指标区", prompt)
        self.assertIn("醒目大数字", prompt)
        self.assertIn("增加了 XX%", prompt)
        self.assertIn("提升 XX%", prompt)
        self.assertIn("优先使用已有百分比数据", prompt)
        self.assertIn("不要为了画面效果编造百分比", prompt)

    def test_prompts_enforce_realistic_people_when_people_may_appear(self):
        build_module_image_prompt = load_prompt_builder()
        usage_module = next(module for module in DEFAULT_MODULES if module["id"] == "usage")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿精华",
                "target_users": ["日常护肤人群"],
                "usage_method": ["洁面后取适量涂抹"],
            },
            style=STYLE_OPTIONS[0],
            module=usage_module,
            module_index=7,
            total_modules=7,
        )

        self.assertIn("人物真实感约束", prompt)
        self.assertIn("真实自然的普通消费者或真实模特", prompt)
        self.assertIn("保留自然肤质、毛孔、细纹", prompt)
        self.assertIn("不要生成过度漂亮", prompt)
        self.assertIn("网红脸", prompt)
        self.assertIn("AI感强", prompt)
        self.assertIn("磨皮严重", prompt)

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

    def test_custom_style_prompt_keeps_style_elements_consistent_without_forcing_one_color(self):
        build_module_image_prompt = load_prompt_builder()
        hero_module = next(module for module in DEFAULT_MODULES if module["id"] == "hero")

        prompt = build_module_image_prompt(
            product_info={"product_name": "积雪草修护精华"},
            style={
                "id": "ai_custom",
                "name": "微晶冻感修护风",
                "primary_color": "#8ECFE6",
                "keywords": ["微晶", "冻感"],
                "visual_direction": "透明凝胶质感、冷感光影、柔雾摄影",
                "layout_guidance": "统一使用半透明凝胶纹理、细线图标和柔和卡片层级",
            },
            module=hero_module,
            module_index=1,
            total_modules=7,
        )

        self.assertIn("风格参考色", prompt)
        self.assertIn("只作为局部点缀和 UI 兼容参考", prompt)
        self.assertIn("每张图可以根据模块内容使用不同主色、背景色或辅助色", prompt)
        self.assertIn("材质、光影、版式、字体层级、装饰元素和图标语言必须一致", prompt)
        self.assertNotIn("共享统一的背景色调", prompt)
        self.assertNotIn("- 主色：#8ECFE6", prompt)

    def test_ingredient_overview_prompt_summarizes_selected_ingredient_system(self):
        build_module_image_prompt = load_prompt_builder()
        ingredient_module = {
            "id": "ingredient_overview",
            "name": "成分总览",
            "description": "成分体系总览",
            "image_group": "detail",
        }

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿面霜",
                "category": "面霜",
                "ingredients": [
                    {"name": "透明质酸钠", "benefit": "帮助提升水润肤感"},
                    {"name": "烟酰胺", "benefit": "帮助提亮肤色观感"},
                    {"name": "积雪草提取物", "benefit": "帮助舒缓干燥不适"},
                    {"name": "泛醇", "benefit": "辅助保湿维稳"},
                ],
            },
            style=STYLE_OPTIONS[0],
            module=ingredient_module,
            module_index=6,
            total_modules=10,
        )

        self.assertIn("成分体系总览", prompt)
        self.assertIn("可直接用于店铺上架", prompt)
        self.assertIn("透明质酸钠", prompt)
        self.assertIn("烟酰胺", prompt)
        self.assertIn("积雪草提取物", prompt)
        self.assertIn("多重成分复配体系", prompt)
        self.assertNotIn("泛醇", prompt)
        for forbidden in [
            "待确认",
            "待说明",
            "待根据",
            "AI 待确认",
            "未展示完整成分",
            "作用待确认",
            "实际成分以",
            "备案为准",
            "免责声明",
            "占位纹理",
        ]:
            self.assertNotIn(forbidden, prompt)

    def test_single_ingredient_prompt_only_explains_assigned_ingredient(self):
        build_module_image_prompt = load_prompt_builder()
        ingredient_module = {
            "id": "ingredient_2",
            "name": "成分 2 讲解",
            "description": "单个核心成分作用讲解",
            "image_group": "detail",
        }

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿面霜",
                "category": "面霜",
                "ingredients": [
                    {"name": "透明质酸钠", "benefit": "帮助提升水润肤感"},
                    {"name": "烟酰胺", "benefit": "帮助提亮肤色观感"},
                    {"name": "积雪草提取物", "benefit": "帮助舒缓干燥不适"},
                    {"name": "泛醇", "benefit": "辅助保湿维稳"},
                ],
            },
            style=STYLE_OPTIONS[0],
            module=ingredient_module,
            module_index=8,
            total_modules=10,
        )

        self.assertIn("单成分讲解图", prompt)
        self.assertIn("只讲 1 个核心成分", prompt)
        self.assertIn("成分序号：2", prompt)
        self.assertIn("烟酰胺", prompt)
        self.assertIn("帮助提亮肤色观感", prompt)
        self.assertNotIn("透明质酸钠", prompt)
        self.assertNotIn("积雪草提取物", prompt)
        self.assertNotIn("泛醇", prompt)

    def test_target_language_prompt_asks_model_to_render_visible_text_directly(self):
        build_module_image_prompt = load_prompt_builder()
        hero_module = next(module for module in DEFAULT_MODULES if module["id"] == "hero")

        prompt = build_module_image_prompt(
            product_info={"product_name": "水润保湿精华", "core_selling_points": ["深层补水"]},
            style=STYLE_OPTIONS[1],
            module=hero_module,
            module_index=1,
            total_modules=7,
            target_language="en",
        )

        self.assertIn("【图片语言】", prompt)
        self.assertIn("English", prompt)
        self.assertIn("所有可见标题、标签、数字说明和角标文字都必须直接生成在图片里", prompt)
        self.assertIn("不要把中文、英文、泰语或马来语混排", prompt)
        self.assertNotIn("分层文字模式", prompt)

    def test_main_image_recipes_use_premium_commercial_photography_language(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "水润保湿精华",
            "category": "护肤精华",
            "core_selling_points": ["深层补水", "水润透亮"],
            "functions": ["补水保湿"],
            "ingredients": [{"name": "透明质酸钠", "benefit": "提升水润肤感"}],
            "usage_method": ["洁面后取适量涂抹"],
            "effect_claims": [{"claim": "肌肤含水量提升", "value": "92%", "source_type": "人体功效测试"}],
        }

        hero_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[1],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point"),
            module_index=2,
            total_modules=5,
        )
        ingredient_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[1],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "main_ingredient"),
            module_index=3,
            total_modules=5,
        )
        effect_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[1],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "main_effect"),
            module_index=4,
            total_modules=5,
        )
        usage_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[1],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "main_usage_scene"),
            module_index=5,
            total_modules=5,
        )

        self.assertIn("空间透视", hero_prompt)
        self.assertIn("质感陈列台", hero_prompt)
        self.assertIn("商业香水/护肤品级布光", hero_prompt)
        self.assertIn("强轮廓边缘光", hero_prompt)
        self.assertIn("体积感环境光", hero_prompt)
        self.assertIn("装饰元素控制在 2-4 个", hero_prompt)

        self.assertIn("极浅景深超微距摄影", ingredient_prompt)
        self.assertIn("晨露质感", ingredient_prompt)
        self.assertIn("发光精华液滴", ingredient_prompt)
        self.assertIn("清透高调色彩", ingredient_prompt)

        self.assertIn("未来科技感玻璃拟态卡片", effect_prompt)
        self.assertIn("极简几何细线", effect_prompt)
        self.assertIn("顶级美妆摄影光影", effect_prompt)
        self.assertIn("保留真实毛孔", effect_prompt)

        self.assertIn("极简奢华浴室或梳妆台", usage_prompt)
        self.assertIn("柔和自然窗光", usage_prompt)
        self.assertIn("丁达尔光晕", usage_prompt)
        self.assertIn("优雅手部姿态", usage_prompt)

    def test_detail_authority_and_pain_scene_use_editorial_mood_without_ui_or_ugly_skin(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "屏障修护精华",
            "functions": ["舒缓泛红", "补水保湿"],
            "target_users": ["换季泛红人群", "干燥紧绷人群"],
            "authority_assets": ["第三方检测报告", "现代研发中心"],
        }

        authority_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[0],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "authority"),
            module_index=2,
            total_modules=7,
        )
        pain_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[0],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "pain_scene"),
            module_index=3,
            total_modules=7,
        )

        self.assertIn("冷峻克制的高科技蓝色/银色调", authority_prompt)
        self.assertIn("极度整洁的现代研发中心", authority_prompt)
        self.assertIn("玻璃器皿的锐利高光", authority_prompt)
        self.assertIn("精密仪器金属质感", authority_prompt)
        self.assertIn("非对称高级画册构图", authority_prompt)
        self.assertIn("不要半透明 UI 卡片", authority_prompt)
        self.assertNotIn("未来科技感玻璃拟态卡片", authority_prompt)

        self.assertIn("情绪化电影灯光", pain_prompt)
        self.assertIn("冷色调或暗调背景", pain_prompt)
        self.assertIn("环境隐喻痛点", pain_prompt)
        self.assertIn("干燥开裂纹理", pain_prompt)
        self.assertIn("暗淡灯光隐喻肤色暗沉", pain_prompt)
        self.assertIn("不要把脸画丑", pain_prompt)


if __name__ == "__main__":
    unittest.main()
