import unittest

from app.demo_data import DEFAULT_MODULES, STYLE_OPTIONS


def load_prompt_builder():
    try:
        from app.services.prompt_builder import build_module_image_prompt
    except (ModuleNotFoundError, ImportError) as exc:
        raise AssertionError("build_module_image_prompt should be implemented") from exc
    return build_module_image_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_brand_qualification_prompt_uses_brand_assets_and_user_materials_first(self):
        build_module_image_prompt = load_prompt_builder()
        brand_module = next(module for module in DEFAULT_MODULES if module["id"] == "brand_qualification")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "用户修改后的 CICA 精华",
                "category": "屏障修护精华",
                "core_selling_points": ["用户补充的强韧屏障卖点"],
                "material_highlights": [
                    "源自法国护肤研发体系",
                    "品牌线下旗舰店陈列",
                    "GMP 生产管理认证"
                ],
                "authority_assets": ["GMP 认证", "官方旗舰店正品保障"],
            },
            style=STYLE_OPTIONS[0],
            module=brand_module,
            module_index=2,
            total_modules=10,
        )

        self.assertIn("固定模块结构", prompt)
        self.assertIn("只生成当前模块", prompt)
        self.assertIn("不能新增一级模块", prompt)
        self.assertIn("当前模块：品牌与资质背书", prompt)
        self.assertIn("用户修改后的 CICA 精华", prompt)
        self.assertIn("用户补充的强韧屏障卖点", prompt)
        self.assertIn("源自法国护肤研发体系", prompt)
        self.assertIn("品牌线下旗舰店陈列", prompt)
        self.assertIn("GMP 生产管理认证", prompt)
        self.assertIn("官方旗舰店正品保障", prompt)
        self.assertIn("用户上传资料和手写信息优先", prompt)
        self.assertIn("AI 只在资料缺失时做安全泛化补充", prompt)
        self.assertIn("品牌与资质背书", prompt)
        self.assertIn("法式建筑", prompt)
        self.assertIn("品牌门店", prompt)
        self.assertIn("街景橱窗", prompt)
        self.assertIn("产地来源", prompt)
        self.assertIn("权威认证", prompt)
        self.assertIn("不能编造真实机构", prompt)
        self.assertIn("禁止出现科学家实验画面为主体", prompt)
        self.assertIn("显微镜", prompt)
        self.assertNotIn("SGS-CICA-2026-042", prompt)

    def test_research_strength_prompt_prefers_scientist_lab_scene_with_paper_report_support(self):
        build_module_image_prompt = load_prompt_builder()
        research_module = next(module for module in DEFAULT_MODULES if module["id"] == "research_strength")

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
            module=research_module,
            module_index=3,
            total_modules=10,
        )

        self.assertIn("当前模块：研发实力", prompt)
        self.assertIn("用户上传资料和手写信息优先", prompt)
        self.assertIn("SGS 第三方检测报告", prompt)
        self.assertIn("科学家实验画面为主体", prompt)
        self.assertIn("研究员", prompt)
        self.assertIn("实验室", prompt)
        self.assertIn("显微镜", prompt)
        self.assertIn("烧瓶", prompt)
        self.assertIn("真人测试", prompt)
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
        self.assertIn("禁止出现品牌门店", prompt)
        self.assertNotIn("研发资质感呈现", prompt)
        self.assertNotIn("核心视觉必须是真实纸质检测报告", prompt)
        self.assertNotIn("不要把实验室人物当作主视觉", prompt)
        self.assertNotIn("样本 32 人", prompt)
        self.assertNotIn("SGS-CICA-2026-042", prompt)

    def test_detail_prompts_keep_hidden_notes_out_of_visible_image_copy(self):
        build_module_image_prompt = load_prompt_builder()
        research_module = next(module for module in DEFAULT_MODULES if module["id"] == "research_strength")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "CICA 修护精华",
                "authority_assets": ["实验室研发", "实验报告", "专研配方理念"],
            },
            style=STYLE_OPTIONS[0],
            module=research_module,
            module_index=3,
            total_modules=10,
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
            total_modules=10,
        )

        self.assertIn("当前模块：效果对比", prompt)
        self.assertIn("肌肤含水量提升", prompt)
        self.assertIn("92%", prompt)
        self.assertIn("14 天人体功效测试", prompt)
        self.assertIn("细纹观感改善", prompt)
        self.assertIn("87%", prompt)
        self.assertIn("指标：细纹观感改善；数值：87%", prompt)
        self.assertNotIn("ai_generated", prompt)
        self.assertIn("体验型视觉", prompt)
        self.assertIn("避免绝对化医疗表达", prompt)
        self.assertIn("局部前后对比组件", prompt)
        self.assertIn("不要让左右对比占满整张画面", prompt)
        self.assertIn("产品主体、标题、使用前/使用后局部对比卡片", prompt)
        self.assertIn("功效说明或数据指标区", prompt)
        self.assertIn("约 30%-45%", prompt)
        self.assertNotIn("全屏左右分屏", prompt)

    def test_hydration_effect_prompt_uses_progress_sized_percent_metric(self):
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
            total_modules=10,
        )

        self.assertIn("水润数据指标区", prompt)
        self.assertIn("必须显示百分比数字", prompt)
        self.assertIn("字号和进度条视觉权重接近", prompt)
        self.assertIn("不需要超大", prompt)
        self.assertIn("优先使用已有百分比数据", prompt)

    def test_effect_prompt_uses_specific_percent_values_when_metrics_have_no_values(self):
        build_module_image_prompt = load_prompt_builder()
        effect_module = next(module for module in DEFAULT_MODULES if module["id"] == "effect_comparison")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "深层补水精华",
                "functions": ["深层补水", "舒缓锁水", "水油平衡"],
                "effect_claims": [
                    {"claim": "肌肤水润度提升", "value": "", "source_type": "ai_generated"},
                    {"claim": "肤感舒适度提升", "value": "", "source_type": "ai_generated"},
                ],
            },
            style=STYLE_OPTIONS[0],
            module=effect_module,
            module_index=4,
            total_modules=10,
        )

        self.assertIn("指标：肌肤水润度提升；数值：89%", prompt)
        self.assertIn("指标：肤感舒适度提升；数值：86%", prompt)
        self.assertIn("没有具体数值时必须使用具体示意百分比数字", prompt)
        self.assertIn("禁止写 XX%、X%、--%、占位、待补充", prompt)
        self.assertNotIn("示意型百分比占位", prompt)
        self.assertNotIn("数值：XX%", prompt)
        self.assertIn("不要只画无数字进度条", prompt)

    def test_prompt_optimization_branch_adds_premium_skincare_scheme_without_changing_default_branch(self):
        build_module_image_prompt = load_prompt_builder()
        module = next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point")
        product_info = {
            "product_name": "水润保湿精华",
            "category": "护肤精华",
            "core_selling_points": ["深层补水"],
            "functions": ["补水保湿"],
        }

        default_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[1],
            module=module,
            module_index=2,
            total_modules=5,
        )
        optimized_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[1],
            module=module,
            module_index=2,
            total_modules=5,
            prompt_branch="prompt_optimization",
        )

        self.assertNotIn("提示词优化分支", default_prompt)
        self.assertNotIn("premium skincare commercial photography", default_prompt)
        self.assertIn("提示词优化分支", optimized_prompt)
        self.assertIn("premium skincare commercial photography", optimized_prompt)
        self.assertIn("图片模型优先负责产品摄影感", optimized_prompt)
        self.assertIn("cheap Taobao poster style", optimized_prompt)
        self.assertIn("材质道具控制在 1-2 个", optimized_prompt)

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
            total_modules=10,
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
            total_modules=10,
            has_style_reference=True,
        )

        self.assertIn("上传的风格参考图优先", prompt)
        self.assertIn("只参考排版、色调、光影和氛围", prompt)
        self.assertIn("不要混入预设风格", prompt)
        self.assertNotIn("预设风格只作为兜底", prompt)
        self.assertNotIn("绿色修护风", prompt)

    def test_style_reference_prompt_injects_gemini_benchmark_brief(self):
        build_module_image_prompt = load_prompt_builder()
        hero_module = next(module for module in DEFAULT_MODULES if module["id"] == "hero")

        prompt = build_module_image_prompt(
            product_info={"product_name": "积雪草修护精华"},
            style={
                "id": "style_reference",
                "name": "冷萃晶透风",
                "primary_color": "#A8DDE8",
                "keywords": ["冷感", "晶透", "高级"],
                "visual_direction": "清透蓝绿色、柔光、玻璃材质",
                "layout_guidance": "中心产品、大留白、标题层级克制",
                "visual_elements": ["玻璃水波纹", "极细描边图标"],
            },
            module=hero_module,
            module_index=1,
            total_modules=7,
            has_style_reference=True,
        )

        self.assertIn("Gemini 对标风格名称：冷萃晶透风", prompt)
        self.assertIn("Gemini 对标参考色：#A8DDE8", prompt)
        self.assertIn("Gemini 对标视觉方向：清透蓝绿色、柔光、玻璃材质", prompt)
        self.assertIn("玻璃水波纹", prompt)
        self.assertIn("不要混入预设风格", prompt)

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
            total_modules=10,
        )

        self.assertIn("风格参考色", prompt)
        self.assertIn("只作为局部点缀和 UI 兼容参考", prompt)
        self.assertIn("每张图可以根据模块内容使用不同主色、背景色或辅助色", prompt)
        self.assertIn("材质、光影、版式、字体层级、装饰元素和图标语言必须一致", prompt)
        self.assertNotIn("共享统一的背景色调", prompt)
        self.assertNotIn("- 主色：#8ECFE6", prompt)

    def test_structured_preset_prompt_injects_element_system_and_module_usage(self):
        build_module_image_prompt = load_prompt_builder()
        prompt = build_module_image_prompt(
            product_info={
                "product_name": "黑松露紧致面霜",
                "category": "面霜乳液",
                "core_selling_points": ["紧致修护"],
                "functions": ["抗老", "紧致"],
            },
            style={
                "id": "black_gold_luxury",
                "name": "黑金奢华风",
                "primary_color": "#C8A24A",
                "keywords": ["黑金", "高奢", "抗老"],
                "theme": "黑金高奢护肤视觉",
                "visual_elements": ["黑色丝绒背景", "鎏金线条", "金箔粒子"],
                "materials": ["黑色丝绒", "拉丝金属"],
                "lighting": ["低调暗场光", "金色边缘光"],
                "module_usage": {"首图": "黑色高级背景 + 金色轮廓光"},
                "forbidden": ["土豪金大面积铺满", "廉价夜店风"],
            },
            module={"id": "main_hero_selling_point", "name": "首图", "description": "产品图 + 一句话核心卖点", "image_group": "main"},
            module_index=2,
            total_modules=5,
        )

        self.assertIn("风格主题：黑金高奢护肤视觉", prompt)
        self.assertIn("主题元素库：黑色丝绒背景 / 鎏金线条 / 金箔粒子", prompt)
        self.assertIn("材质系统：黑色丝绒 / 拉丝金属", prompt)
        self.assertIn("光影系统：低调暗场光 / 金色边缘光", prompt)
        self.assertIn("当前模块风格用法：黑色高级背景 + 金色轮廓光", prompt)
        self.assertIn("风格禁止项：土豪金大面积铺满 / 廉价夜店风", prompt)
        self.assertNotIn("AI 规划视觉方向", prompt)

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

    def test_product_showcase_prompt_reinforces_product_texture_effect_and_zero_additions(self):
        build_module_image_prompt = load_prompt_builder()
        showcase_module = next(module for module in DEFAULT_MODULES if module["id"] == "product_showcase")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿精华",
                "category": "护肤精华",
                "core_selling_points": ["双效补水提亮", "0 酒精温和配方"],
                "functions": ["补水保湿", "改善暗沉"],
                "material_highlights": ["清透精华水质地", "不添加酒精、色素、香精"],
            },
            style=STYLE_OPTIONS[1],
            module=showcase_module,
            module_index=7,
            total_modules=10,
        )

        self.assertIn("当前模块：产品大图强化", prompt)
        self.assertIn("产品大图 + 功效 + 质地 + 0添加", prompt)
        self.assertIn("双效补水提亮", prompt)
        self.assertIn("0 酒精温和配方", prompt)
        self.assertIn("清透精华水质地", prompt)
        self.assertIn("不添加酒精、色素、香精", prompt)
        self.assertIn("产品瓶身作为最大主视觉", prompt)
        self.assertIn("质地液体", prompt)
        self.assertIn("0 酒精", prompt)
        self.assertIn("0 色素", prompt)
        self.assertIn("0 添加图标", prompt)
        self.assertIn("禁止品牌门店", prompt)
        self.assertIn("不讲品牌门店、研发报告、竞品或使用步骤", prompt)

    def test_product_info_prompt_uses_uploaded_specs_before_ai_fallback(self):
        build_module_image_prompt = load_prompt_builder()
        info_module = next(module for module in DEFAULT_MODULES if module["id"] == "product_info")

        prompt = build_module_image_prompt(
            product_info={
                "product_name": "用户手写名称精华水",
                "category": "精华水",
                "spec": "360ml",
                "functions": ["补水保湿", "提亮肤色观感"],
                "ingredients": [{"name": "烟酰胺", "benefit": "帮助提亮肤色观感"}],
                "usage_method": ["洁面后取适量轻拍至吸收"],
                "material_highlights": ["产地：法国", "保质期：4 年", "适用肤质：敏感肌适用"],
            },
            style=STYLE_OPTIONS[0],
            module=info_module,
            module_index=10,
            total_modules=10,
        )

        self.assertIn("当前模块：产品信息", prompt)
        self.assertIn("用户上传资料和手写信息优先", prompt)
        self.assertIn("AI 只在资料缺失时做安全泛化补充", prompt)
        self.assertIn("用户手写名称精华水", prompt)
        self.assertIn("360ml", prompt)
        self.assertIn("产地：法国", prompt)
        self.assertIn("保质期：4 年", prompt)
        self.assertIn("适用肤质：敏感肌适用", prompt)
        self.assertIn("产品名称、功效、规格、保质期、产地、成分", prompt)
        self.assertIn("米色纸质背景", prompt)
        self.assertIn("正式说明书", prompt)
        self.assertIn("不能编造产地", prompt)

    def test_detail_prompts_define_product_visibility_by_page_role(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "水润保湿精华",
            "core_selling_points": ["深层补水"],
            "functions": ["补水保湿"],
            "ingredients": [{"name": "透明质酸", "benefit": "帮助提升水润肤感"}],
            "usage_method": ["洁面后取适量涂抹"],
        }

        prompts = {
            module["id"]: build_module_image_prompt(
                product_info=product_info,
                style=STYLE_OPTIONS[1],
                module=module,
                module_index=module["order"],
                total_modules=10,
            )
            for module in DEFAULT_MODULES
            if module.get("image_group") == "detail"
        }

        for module_id in ["hero", "product_showcase", "usage"]:
            self.assertIn("产品露出策略：必须出现产品", prompts[module_id])

        for module_id in ["effect_comparison", "competitor_comparison"]:
            self.assertIn("产品露出策略：产品只能辅助出现", prompts[module_id])

        self.assertIn("产品露出策略：产品可不出现", prompts["ingredient_overview"])

        for module_id in ["brand_qualification", "research_strength", "pain_scene", "product_info"]:
            self.assertIn("产品露出策略：不要出现产品瓶身、包装、商品主图或产品陈列", prompts[module_id])

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

    def test_single_ingredient_prompt_replaces_placeholder_benefits_with_safe_visual_effects(self):
        build_module_image_prompt = load_prompt_builder()
        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿面霜",
                "category": "面霜",
                "ingredients": [
                    {"name": "透明质酸钠", "benefit": "待确认"},
                    {"name": "烟酰胺", "benefit": ""},
                    {"name": "积雪草提取物", "benefit": "帮助舒缓干燥不适"},
                    {"name": "泛醇", "benefit": "辅助保湿维稳"},
                ],
            },
            style=STYLE_OPTIONS[0],
            module={
                "id": "ingredient_1",
                "name": "成分 1 讲解",
                "description": "第 1 个核心成分作用讲解",
                "image_group": "detail",
            },
            module_index=7,
            total_modules=10,
        )

        self.assertIn("透明质酸钠", prompt)
        self.assertIn("帮助提升水润肤感", prompt)
        self.assertIn("建议视觉方向：透明水滴", prompt)
        self.assertIn("后续单成分讲解图", prompt)
        self.assertNotIn("待确认", prompt)
        self.assertNotIn("泛醇", prompt)

    def test_target_language_prompt_asks_model_to_render_visible_text_directly(self):
        build_module_image_prompt = load_prompt_builder()
        hero_module = next(module for module in DEFAULT_MODULES if module["id"] == "hero")

        prompt = build_module_image_prompt(
            product_info={"product_name": "水润保湿精华", "core_selling_points": ["深层补水"]},
            style=STYLE_OPTIONS[1],
            module=hero_module,
            module_index=1,
            total_modules=10,
            target_language="en",
        )

        self.assertIn("【图片语言】", prompt)
        self.assertIn("English", prompt)
        self.assertIn("所有可见标题、标签、数字说明和角标文字都必须直接生成在图片里", prompt)
        self.assertIn("不要把中文、英文、泰语、马来语或越南语混排", prompt)
        self.assertNotIn("分层文字模式", prompt)

    def test_target_language_prompt_supports_vietnamese(self):
        build_module_image_prompt = load_prompt_builder()
        hero_module = next(module for module in DEFAULT_MODULES if module["id"] == "hero")

        prompt = build_module_image_prompt(
            product_info={"product_name": "水润保湿精华", "core_selling_points": ["深层补水"]},
            style=STYLE_OPTIONS[1],
            module=hero_module,
            module_index=1,
            total_modules=10,
            target_language="vi",
        )

        self.assertIn("Tiếng Việt", prompt)
        self.assertIn("不要把中文、英文、泰语、马来语或越南语混排", prompt)

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

    def test_detail_research_and_pain_scene_use_editorial_mood_without_ui_or_ugly_skin(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "屏障修护精华",
            "functions": ["舒缓泛红", "补水保湿"],
            "target_users": ["换季泛红人群", "干燥紧绷人群"],
            "authority_assets": ["第三方检测报告", "现代研发中心"],
        }

        research_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[0],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "research_strength"),
            module_index=3,
            total_modules=10,
        )
        pain_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[0],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "pain_scene"),
            module_index=4,
            total_modules=10,
        )

        self.assertIn("冷峻克制的高科技蓝色/银色调", research_prompt)
        self.assertIn("极度整洁的现代研发中心", research_prompt)
        self.assertIn("玻璃器皿的锐利高光", research_prompt)
        self.assertIn("精密仪器金属质感", research_prompt)
        self.assertIn("非对称高级画册构图", research_prompt)
        self.assertIn("不要半透明 UI 卡片", research_prompt)
        self.assertNotIn("未来科技感玻璃拟态卡片", research_prompt)

        self.assertIn("情绪化电影灯光", pain_prompt)
        self.assertIn("冷色调或暗调背景", pain_prompt)
        self.assertIn("环境隐喻痛点", pain_prompt)
        self.assertIn("干燥开裂纹理", pain_prompt)
        self.assertIn("暗淡灯光隐喻肤色暗沉", pain_prompt)
        self.assertIn("不要把脸画丑", pain_prompt)

    def test_main_image_prompts_include_click_rate_strategy_from_store_main_doc(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "水润保湿精华",
            "category": "护肤精华",
            "core_selling_points": ["干皮急救", "妆前服帖"],
            "functions": ["补水保湿", "改善干燥"],
            "ingredients": [{"name": "透明质酸钠", "benefit": "帮助提升水润肤感"}],
            "effect_claims": [{"claim": "水润感提升", "value": "92%", "source_type": "人体功效测试"}],
            "usage_method": ["洁面后取适量涂抹"],
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

        self.assertIn("产品大 + 卖点狠 + 证据短 + 视觉亮 + 信息少", hero_prompt)
        self.assertIn("在电商货架中抢点击", hero_prompt)
        self.assertIn("0.3 秒内知道核心卖点", hero_prompt)
        self.assertIn("产品占画面 45%-55%", hero_prompt)
        self.assertIn("一个大标题打核心卖点", hero_prompt)
        self.assertIn("2-4 个小标签", hero_prompt)

        self.assertIn("次图-成分不是详情页成分页", ingredient_prompt)
        self.assertIn("最多展示 2-3 个核心成分", ingredient_prompt)
        self.assertIn("每个成分只写一句作用短标签", ingredient_prompt)

        self.assertIn("局部前后对比，面积建议占画面 25%-35%", effect_prompt)
        self.assertIn("没有真实数据时使用体验型表达", effect_prompt)
        self.assertIn("只有漂亮脸，没有变化证据", effect_prompt)

        self.assertIn("建立代入感", usage_prompt)
        self.assertIn("晨间上妆前", usage_prompt)
        self.assertIn("人物遮挡产品", usage_prompt)

    def test_detail_prompts_include_sales_visual_contradiction_strategy(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "屏障修护精华",
            "core_selling_points": ["卡粉起皮先稳住屏障"],
            "functions": ["补水保湿", "屏障护理"],
            "target_users": ["干燥紧绷人群", "换季脆弱人群"],
            "ingredients": [
                {"name": "透明质酸钠", "benefit": "帮助提升水润肤感"},
                {"name": "神经酰胺", "benefit": "帮助维持屏障舒适"},
                {"name": "积雪草提取物", "benefit": "帮助舒缓干燥不适"},
            ],
        }

        hero_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "hero"),
            module_index=1,
            total_modules=10,
        )
        pain_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "pain_scene"),
            module_index=3,
            total_modules=10,
        )
        competitor_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "competitor_comparison"),
            module_index=5,
            total_modules=10,
        )
        overview_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "ingredient_overview"),
            module_index=6,
            total_modules=10,
        )
        showcase_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "product_showcase"),
            module_index=7,
            total_modules=10,
        )
        info_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "product_info"),
            module_index=10,
            total_modules=10,
        )

        self.assertIn("每张图必须有一个视觉矛盾", hero_prompt)
        self.assertIn("问题 vs 解决", hero_prompt)
        self.assertIn("说明型图片", hero_prompt)
        self.assertIn("销售型图片", hero_prompt)
        self.assertIn("产品作为主视觉，占画面 35%-50%", hero_prompt)

        self.assertIn("局部放大镜", pain_prompt)
        self.assertIn("红色警示标签", pain_prompt)
        self.assertIn("上妆卡粉", pain_prompt)
        self.assertIn("卡粉起皮", pain_prompt)
        self.assertIn("干到发紧", pain_prompt)

        self.assertIn("左侧视觉偏灰、暗、干、粗糙", competitor_prompt)
        self.assertIn("右侧视觉偏亮、润、干净", competitor_prompt)
        self.assertIn("普通同类产品", competitor_prompt)

        self.assertIn("成分总览只做体系介绍", overview_prompt)
        self.assertIn("补水 + 修护 + 舒缓", overview_prompt)
        self.assertIn("成分浮岛", overview_prompt)

        self.assertIn("产品大图强化", showcase_prompt)
        self.assertIn("功效 + 质地 + 0添加", showcase_prompt)
        self.assertIn("产品瓶身作为最大主视觉", showcase_prompt)

        self.assertIn("产品信息", info_prompt)
        self.assertIn("正式说明书", info_prompt)
        self.assertIn("产品名称、功效、规格、保质期、产地、成分", info_prompt)

    def test_detail_visual_reduction_rules_are_appended_without_replacing_module_strategy(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "水润保湿面霜",
            "category": "面霜",
            "core_selling_points": ["干皮急救", "妆前服帖"],
            "functions": ["补水保湿", "改善干燥"],
            "ingredients": [
                {"name": "透明质酸钠", "benefit": "帮助提升水润肤感"},
                {"name": "神经酰胺", "benefit": "帮助维持屏障舒适"},
                {"name": "积雪草提取物", "benefit": "帮助舒缓干燥不适"},
            ],
            "usage_method": ["洁面后取适量涂抹"],
        }

        hero_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "hero"),
            module_index=1,
            total_modules=10,
        )
        ingredient_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module={
                "id": "ingredient_1",
                "name": "成分 1 讲解",
                "description": "第 1 个核心成分作用讲解",
                "image_group": "detail",
            },
            module_index=7,
            total_modules=10,
        )
        product_info_prompt = build_module_image_prompt(
            product_info=product_info,
            style=STYLE_OPTIONS[2],
            module={
                "id": "product_info",
                "name": "产品信息",
                "description": "产品基础信息 / 参数 / 成分说明",
                "image_group": "detail",
            },
            module_index=10,
            total_modules=10,
        )

        for prompt in (hero_prompt, ingredient_prompt, product_info_prompt):
            self.assertIn("视觉减法补充规则", prompt)
            self.assertIn("不改变当前模块的页面任务", prompt)
            self.assertIn("留白必须保持干净", prompt)
            self.assertIn("不要为了让画面更丰富而添加任何无关装饰", prompt)

        self.assertIn("详情首图减法约束", hero_prompt)
        self.assertIn("不要添加与核心卖点无关的植物", hero_prompt)
        self.assertIn("产品作为主视觉，占画面 35%-50%", hero_prompt)

        self.assertIn("单成分页减法约束", ingredient_prompt)
        self.assertIn("只允许透明质酸钠相关的主视觉原料或机制视觉", ingredient_prompt)
        self.assertIn("只讲 1 个核心成分", ingredient_prompt)

        self.assertIn("产品信息页减法约束", product_info_prompt)
        self.assertIn("不要添加任何装饰背景", product_info_prompt)
        self.assertIn("产品基础信息 / 参数 / 成分说明", product_info_prompt)

    def test_campaign_prompts_keep_promotion_elements_secondary_and_user_provided(self):
        build_module_image_prompt = load_prompt_builder()
        prompt = build_module_image_prompt(
            product_info={
                "product_name": "水润保湿精华",
                "core_selling_points": ["干皮急救"],
                "functions": ["补水保湿"],
            },
            style=STYLE_OPTIONS[1],
            module=next(module for module in DEFAULT_MODULES if module["id"] == "campaign_hero_selling_point"),
            module_index=2,
            total_modules=5,
            promotion_info="618 限时 8 折，满 199 减 30",
        )

        self.assertIn("产品仍然是主体，促销元素不能压过产品", prompt)
        self.assertIn("促销信息必须来自用户填写内容", prompt)
        self.assertIn("促销标签建议控制在 1-3 个", prompt)
        self.assertIn("不能编造价格、折扣、日期、赠品或满减门槛", prompt)
        self.assertIn("618 限时 8 折，满 199 减 30", prompt)

    def test_all_module_prompts_stay_compact_without_losing_strategy_anchors(self):
        build_module_image_prompt = load_prompt_builder()
        product_info = {
            "product_name": "CICA 修护精华",
            "category": "护肤精华",
            "spec": "30ml",
            "core_selling_points": ["舒缓泛红不适", "补水锁水", "强韧肌肤屏障"],
            "functions": ["舒缓", "补水", "修护屏障"],
            "ingredients": [
                {"name": "积雪草", "benefit": "帮助舒缓泛红与脆弱不适"},
                {"name": "神经酰胺", "benefit": "帮助强韧肌肤屏障"},
                {"name": "透明质酸", "benefit": "补充水分，帮助锁水维稳"},
            ],
            "target_users": ["换季泛红人群", "干燥紧绷人群", "屏障脆弱人群"],
            "usage_method": ["洁面后使用", "取 2-3 滴于掌心", "均匀涂抹全脸", "轻拍至吸收"],
            "authority_assets": ["实验室研发", "实验报告", "专研配方理念"],
            "effect_claims": [{"claim": "肌肤更水润", "value": "92%", "source_type": "ai_generated"}],
        }

        prompts = [
            build_module_image_prompt(
                product_info=product_info,
                style=STYLE_OPTIONS[2],
                module=module,
                module_index=module.get("order", index),
                total_modules=10 if module.get("image_group") == "detail" else 5,
                promotion_info="618 限时 8 折，满 199 减 30",
            )
            for index, module in enumerate(DEFAULT_MODULES, start=1)
        ]

        self.assertLessEqual(max(len(prompt) for prompt in prompts), 2650)
        self.assertLessEqual(sum(len(prompt) for prompt in prompts), 41500)
        self.assertTrue(any("产品大 + 卖点狠 + 证据短 + 视觉亮 + 信息少" in prompt for prompt in prompts))
        self.assertTrue(any("每张图必须有一个视觉矛盾" in prompt for prompt in prompts))
        self.assertTrue(any("品牌与资质背书" in prompt for prompt in prompts))
        self.assertTrue(any("产品大图 + 功效 + 质地 + 0添加" in prompt for prompt in prompts))
        self.assertTrue(any("产品名称、功效、规格、保质期、产地、成分" in prompt for prompt in prompts))


if __name__ == "__main__":
    unittest.main()
