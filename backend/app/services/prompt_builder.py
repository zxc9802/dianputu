from __future__ import annotations

import re
from typing import Any


def _text(value: Any, fallback: str = "待根据资料补全") -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = "；".join(f"{key}：{_text(val, '')}" for key, val in item.items() if _text(val, ""))
            else:
                text = str(item).strip()
            if text:
                items.append(text)
        return items
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in re.split(r"[/、,\n]", value) if item.strip()]
    return []


def _numbered_lines(items: list[str], fallback: str) -> str:
    values = items or [fallback]
    return "\n".join(f"{index}. {item}" for index, item in enumerate(values, start=1))


def _format_ingredients(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "1. 待根据品类补全核心成分；作用：围绕产品功效给出谨慎、非医疗化说明"

    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            name = _text(item.get("name"), "")
            benefit = _text(item.get("benefit"), "待说明作用")
            if name:
                lines.append(f"{index}. 成分：{name}；作用：{benefit}")
        else:
            name = str(item).strip()
            if name:
                lines.append(f"{index}. 成分：{name}；作用：待说明作用")
    return "\n".join(lines) if lines else "1. 待根据品类补全核心成分；作用：围绕产品功效给出谨慎、非医疗化说明"


def _authority_asset_label(item: str) -> str:
    label = re.split(r"[：:，,；;\n]", item, maxsplit=1)[0].strip()
    label = re.sub(r"报告编号\s*[:：]?\s*[A-Za-z0-9_-]+", "", label).strip()
    return label or "实验室检测报告"


def _format_authority_assets(value: Any) -> str:
    items = _string_items(value)
    if not items:
        return (
            "1. 资料项：实验室研发、检测报告轮廓或专研配方理念；"
            "来源类型：ai_generated；说明：仅作为详情页示意型权威背书，不编造真实机构编号"
        )
    return "\n".join(
        f"{index}. 资料项：{_authority_asset_label(item)}；来源类型：用户确认/AI 提炼字段 authority_assets；画面只呈现报告轮廓和泛化标签，不展示报告编号、样本量、机构编号等具体细节"
        for index, item in enumerate(items, start=1)
    )


def _format_effect_claims(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return (
            "1. 指标：根据产品功效补全一条谨慎的效果指标；数值：生成合理示意型百分比；"
            "来源类型：ai_generated；说明：示意型数据，避免绝对化医疗表达"
        )

    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            claim = _text(item.get("claim"), "")
            value_text = _text(item.get("value"), "待补全为合理示意数值")
            source_type = _text(item.get("source_type"), "ai_generated")
            if claim:
                lines.append(f"{index}. 指标：{claim}；数值：{value_text}；来源类型：{source_type}")
        else:
            claim = str(item).strip()
            if claim:
                lines.append(f"{index}. 指标：{claim}；数值：待补全为合理示意数值；来源类型：ai_generated")
    if not lines:
        return (
            "1. 指标：根据产品功效补全一条谨慎的效果指标；数值：生成合理示意型百分比；"
            "来源类型：ai_generated；说明：示意型数据，避免绝对化医疗表达"
        )
    return "\n".join(lines)


def build_product_generation_brief(product_info: dict[str, Any] | None) -> str:
    info = product_info or {}
    return "\n".join(
        [
            "【产品生成 brief】",
            f"- 产品名称：{_text(info.get('product_name'), '待确认产品')}",
            f"- 品类：{_text(info.get('category'), '护肤品')}",
            f"- 规格：{_text(info.get('spec'), '待确认规格')}",
            "- 核心卖点：",
            _numbered_lines(_string_items(info.get("core_selling_points")), "待根据 AI 提炼结果补全核心卖点"),
            "- 核心功效：",
            _numbered_lines(_string_items(info.get("functions")), "待根据品类补全温和功效"),
            "- 核心成分小报告：",
            _format_ingredients(info.get("ingredients")),
            "- 目标人群：",
            _numbered_lines(_string_items(info.get("target_users")), "待根据品类补全目标人群"),
            "- 使用方法：",
            _numbered_lines(_string_items(info.get("usage_method")), "待根据品类补全标准使用步骤"),
            "- 权威资料小报告：",
            _format_authority_assets(info.get("authority_assets")),
            "- 效果数据小报告：",
            _format_effect_claims(info.get("effect_claims")),
        ]
    )


MODULE_VISUAL_RECIPES: dict[str, dict[str, str]] = {
    "main_white_bg": {
        "layout": "只删除参考图背景并替换为纯白背景，产品居中完整展示，无任何装饰元素",
        "primary_visual": "参考图中的原始产品瓶身或包装本身",
        "product_role": "唯一主体，占画面主要面积；产品标签、文字、Logo、图案和包装细节必须保持原样",
        "forbidden": "重绘产品、改动瓶身标签、擦除包装文字、生成空白标签、所有额外文字、贴纸、道具、人物、植物、水滴、光效、场景、渐变、纹理、颜色氛围",
    },
    "main_hero_selling_point": {
        "layout": "产品占画面约 60%，居中偏左；右侧或上方只放一句核心卖点",
        "primary_visual": "产品大图 + 1 句核心卖点",
        "product_role": "最大主体，必须清晰醒目",
        "forbidden": "成分表、成分卡片、数据图表、使用步骤、人物使用场景",
    },
    "main_ingredient": {
        "layout": "左右分栏：左侧原料实物微距特写，右侧成分名与作用卡片",
        "primary_visual": "原料实物质感，例如叶片、透明液滴、原料切面或精华质地",
        "product_role": "缩小放在右下角作为辅助，或完全不出现",
        "forbidden": "效果数据百分比、数据仪表盘、使用步骤、人物使用场景、产品居中环绕文字构图",
    },
    "main_effect": {
        "layout": "上下分区：上方肌肤质感或体验感画面，下方数据仪表盘、进度条或对比卡片",
        "primary_visual": "可信的数据可视化图表 + 肌肤质感体验",
        "product_role": "缩小放在角落作为辅助，不作为画面中心",
        "forbidden": "成分详情列表、原料微距主视觉、使用步骤、人物使用场景、产品居中环绕文字构图",
    },
    "main_usage_scene": {
        "layout": "场景化全幅构图，人物手部、滴管、面部护理或梳妆台使用动作占主画面",
        "primary_visual": "真实使用动作与生活化护理场景",
        "product_role": "嵌入场景中清晰可见，但不是孤立居中展示",
        "forbidden": "数据图表、成分列表、原料卡片、产品居中环绕文字构图",
    },
    "campaign_white_bg": {
        "layout": "只删除参考图背景并替换为纯白背景，产品居中完整展示，角落可加入小面积促销角标",
        "primary_visual": "参考图中的原始产品瓶身或包装 + 克制活动角标",
        "product_role": "最大主体；产品标签、文字、Logo、图案和包装细节必须保持原样，角标不能遮挡产品",
        "forbidden": "复杂场景、植物、水滴、光效、道具、人物、大面积活动背景、编造价格折扣日期",
    },
    "campaign_hero_selling_point": {
        "layout": "产品居中作为最大主体，搭配促销角标、优惠券样式标签和一句核心卖点",
        "primary_visual": "产品大图 + 活动氛围装饰 + 促销利益点",
        "product_role": "最大主体，必须压过活动装饰",
        "forbidden": "成分表、成分卡片、数据图表、使用步骤、人物使用场景",
    },
    "campaign_ingredient": {
        "layout": "成分卡片堆叠布局，背景有原料质感，角落加入轻量活动角标",
        "primary_visual": "成分卡片 + 原料微距 + 轻活动氛围",
        "product_role": "缩小放角落或不出现，不作为中心主体",
        "forbidden": "效果数据、数据仪表盘、使用场景人物、产品居中环绕文字构图",
    },
    "campaign_effect": {
        "layout": "数据仪表盘或进度环构图，搭配促销利益点标签",
        "primary_visual": "数据可视化图表 + 促销转化标签",
        "product_role": "缩小放角落作为辅助",
        "forbidden": "成分详情列表、原料微距主视觉、使用场景人物、产品居中环绕文字构图",
    },
    "campaign_usage_scene": {
        "layout": "活动场景图，使用动作占主画面，并加入礼盒、优惠券或活动标签氛围",
        "primary_visual": "使用场景 + 礼盒或活动氛围元素",
        "product_role": "嵌入场景中清晰可见",
        "forbidden": "数据图表、成分列表、原料卡片、产品居中环绕文字构图",
    },
}


def _limited_numbered_lines(value: Any, fallback: str, limit: int) -> str:
    return _numbered_lines(_string_items(value)[:limit], fallback)


def build_module_specific_brief(product_info: dict[str, Any] | None, module: dict[str, Any]) -> str:
    info = product_info or {}
    module_id = str(module.get("id"))
    base_lines = [
        "【当前模块精简 brief】",
        f"- 产品名称：{_text(info.get('product_name'), '待确认产品')}",
    ]

    if module_id in {"main_white_bg", "campaign_white_bg"}:
        return "\n".join([*base_lines, f"- 规格：{_text(info.get('spec'), '待确认规格')}"])

    if module_id in {"main_hero_selling_point", "campaign_hero_selling_point"}:
        return "\n".join(
            [
                *base_lines,
                f"- 品类：{_text(info.get('category'), '护肤品')}",
                "- 本图只使用前 2 个核心卖点：",
                _limited_numbered_lines(info.get("core_selling_points"), "待根据 AI 提炼结果补全核心卖点", 2),
            ]
        )

    if module_id in {"main_ingredient", "campaign_ingredient"}:
        return "\n".join([*base_lines, "- 本图只使用核心成分信息：", _format_ingredients(info.get("ingredients"))])

    if module_id in {"main_effect", "campaign_effect"}:
        return "\n".join(
            [
                *base_lines,
                "- 本图只使用核心功效：",
                _limited_numbered_lines(info.get("functions"), "待根据品类补全温和功效", 3),
                "- 本图只使用效果数据：",
                _format_effect_claims(info.get("effect_claims")),
            ]
        )

    if module_id in {"main_usage_scene", "campaign_usage_scene"}:
        return "\n".join(
            [
                *base_lines,
                "- 本图只使用目标人群：",
                _limited_numbered_lines(info.get("target_users"), "待根据品类补全目标人群", 3),
                "- 本图只使用使用方法：",
                _limited_numbered_lines(info.get("usage_method"), "待根据品类补全标准使用步骤", 4),
            ]
        )

    return build_product_generation_brief(product_info)


def _module_visual_constraints(module: dict[str, Any]) -> str:
    module_id = str(module.get("id"))
    recipe = MODULE_VISUAL_RECIPES.get(module_id)
    if not recipe:
        return ""

    return "\n".join(
        [
            "【构图差异化约束】",
            f"- 构图模板：{recipe['layout']}。",
            f"- 主视觉元素：{recipe['primary_visual']}。",
            f"- 产品角色：{recipe['product_role']}。",
            f"- 禁止出现：{recipe['forbidden']}。",
            "- 不要把本图做成其他主图模块的模板；每张主图必须有独立视觉主体和版式。",
        ]
    )


def _module_requirements(module: dict[str, Any], product_info: dict[str, Any] | None) -> str:
    module_id = module.get("id")
    info = product_info or {}
    authority_report = _format_authority_assets(info.get("authority_assets"))
    effect_report = _format_effect_claims(info.get("effect_claims"))
    ingredients_report = _format_ingredients(info.get("ingredients"))

    requirements = {
        "main_white_bg": [
            "这张图不是重新设计产品图，而是基于用户上传的参考图做抠图换白底：只删除原背景并替换为纯白色（#FFFFFF）。",
            "必须完整保留产品本身的所有元素：瓶身比例、瓶身颜色、盖子/滴管、标签位置、标签文字、Logo、图案、包装纹理和边缘细节都不能改动。",
            "产品居中放置，主体完整清晰，边缘干净利落，无裁切。",
            "绝对不能出现任何新增文字、图标、标签、贴纸、道具、人物、植物、水滴、光效、场景、装饰元素。",
            "不能把产品标签抹成空白，不能重绘包装，不能替换成相似但不同的瓶子。",
            "不能有过重的阴影或复杂反光，只允许产品自身的自然投影（极淡）。",
            "这是电商平台标准白底主图，必须通过平台主图审核：画面中除了原始产品本身，其余区域全部为纯白色。",
            "不要应用任何视觉风格、主题色或风格关键词，白底图不需要风格化处理。",
        ],
        "main_hero_selling_point": [
            "画面只呈现店铺首图，产品图作为最大视觉主体，搭配一句话核心卖点。",
            "一句话核心卖点优先来自当前模块精简 brief，文案短、醒目、可信，不遮挡产品。",
            "可以使用风格化背景、光影和少量质感元素，但产品必须清晰、居中偏主视觉。",
        ],
        "main_ingredient": [
            "画面只呈现成分次图，突出核心成分、原料质感和成分标签。",
            "必须参考以下成分信息，选择 2-3 个重点成分呈现：",
            ingredients_report,
            "成分作用表达要谨慎，不能写成药品疗效或治疗承诺。",
        ],
        "main_effect": [
            "画面只呈现效果次图，突出核心功效、使用收益和可信的效果表达。",
            "优先参考以下效果数据；如为示意型数据，画面需弱化为体验感表达：",
            effect_report,
            "避免绝对化承诺，不写治愈、根治、永久有效，不制造夸张前后对比。",
        ],
        "campaign_white_bg": [
            "这张图不是重新设计产品图，而是基于用户上传的参考图做抠图换白底：只删除原背景并替换为纯白色（#FFFFFF）。",
            "必须完整保留产品本身的所有元素：瓶身比例、瓶身颜色、盖子/滴管、标签位置、标签文字、Logo、图案、包装纹理和边缘细节都不能改动。",
            "产品居中放置，主体完整清晰；可以在画面角落加入克制的促销角标或活动贴纸，但角标面积不超过画面 10%。",
            "促销元素不能遮挡产品主体，不能覆盖产品标签，不能把白底图做成复杂场景图；如果用户未填写具体优惠，不得编造折扣、价格或日期。",
            "除了原始产品和角标之外，不能出现任何植物、水滴、光效、道具、人物、场景等装饰元素。",
            "不能把产品标签抹成空白，不能重绘包装，不能替换成相似但不同的瓶子。",
            "不要应用视觉风格的主题色到背景上，白底图的背景必须保持纯白。",
        ],
        "campaign_hero_selling_point": [
            "画面呈现活动首图，产品图作为最大视觉主体，同时展示一句核心卖点和促销利益点。",
            "促销表达需来自用户填写的活动信息，可使用优惠券、限时角标、满减标签、折扣贴纸等电商活动元素。",
            "文字层级要清晰：产品卖点和促销利益点都短促有力，不能遮挡产品。",
        ],
        "campaign_ingredient": [
            "画面呈现活动成分次图，展示核心成分与原料质感，同时加入活动氛围元素。",
            "必须参考以下成分信息，选择 2-3 个重点成分呈现：",
            ingredients_report,
            "促销元素作为辅助转化信息出现，不能压过成分可信表达，也不能写成药品疗效。",
        ],
        "campaign_effect": [
            "画面呈现活动效果次图，突出核心功效、使用收益和促销转化理由。",
            "优先参考以下效果数据；如为示意型数据，画面需弱化为体验感表达：",
            effect_report,
            "可加入限时优惠、活动权益、购买利益点，但不能夸大效果或制造绝对承诺。",
        ],
        "campaign_usage_scene": [
            "画面呈现活动使用场景次图，结合目标人群、使用环境和活动购买氛围。",
            "可以加入礼盒、活动氛围、优惠券、限时购标签等元素，产品必须清晰可见。",
            "场景需围绕目标人群与使用方法展开，不编造用户未填写的具体价格、折扣或活动日期。",
        ],
        "hero": [
            "用产品大图作为视觉中心，突出产品名称、品类、规格和 2-3 个核心卖点。",
            "不要塞入权威报告、效果对比表或使用步骤，这些属于其他模块。",
        ],
        "authority": [
            "画面只呈现权威资质展示，核心视觉为科学家/研究员在干净明亮实验室做护肤品研究的背景画面。",
            "人物需穿实验服或科研防护服，可出现显微镜、试管、培养皿、实验台、柔和玻璃器皿等专业但真实的科研元素。",
            "报告只作为辅助视觉出现：用几张报告纸、图表轮廓、印章轮廓或证书卡片表达即可，文字要小且虚化/泛化，不写具体报告编号、样本编号、机构编号或可核验编号。",
            "必须参考以下权威资料方向，但不要把完整原文搬到画面上：",
            authority_report,
            "版式建议：实验室科学家背景 + 半透明报告轮廓卡片 + 1-2 句克制的权威背书短文案。",
        ],
        "pain_scene": [
            "画面只呈现目标人群的护肤痛点场景，突出困扰、情绪和产品解决方向。",
            "痛点来自目标人群与核心功效，不要提前展示效果数据或权威报告。",
        ],
        "effect_comparison": [
            "画面只呈现效果对比，必须像小报告一样写清楚每条效果数据。",
            "必须完整带入以下效果数据：",
            effect_report,
            "如果来源类型为 ai_generated 或资料缺失，画面按示意型数据处理；避免绝对化医疗表达，不写治愈、根治、永久有效。",
        ],
        "competitor_comparison": [
            "画面只呈现本产品与普通同类产品的对比，不指名真实竞品品牌。",
            "对比维度建议：成分思路、肤感、使用体验、适合人群、卖点完整度。",
        ],
        "ingredient": [
            "画面只呈现成分页，必须把核心成分和对应作用讲清楚。",
            "必须完整带入以下成分信息：",
            ingredients_report,
            "不要把成分作用写成药品疗效。",
        ],
        "usage": [
            "画面只呈现使用方法，用清晰步骤展示用量、顺序、手法和使用频率。",
            "可以搭配手部涂抹、滴管、面部轻拍等示意画面。",
        ],
    }
    return "\n".join(requirements.get(str(module_id), [f"画面只呈现当前模块内容：{_text(module.get('description'))}"]))


def build_module_image_prompt(
    *,
    product_info: dict[str, Any] | None,
    style: dict[str, Any],
    module: dict[str, Any],
    module_index: int,
    total_modules: int,
    promotion_info: str | None = None,
) -> str:
    style_keywords = " / ".join(_string_items(style.get("keywords"))) or "高级 / 干净 / 统一"
    group = module.get("image_group")
    is_main_image = group in {"main", "campaign"}
    is_campaign_image = group == "campaign"
    module_kind = "中文电商活动主图" if is_campaign_image else "中文电商商品主图" if is_main_image else "中文商品详情页单模块图片"
    structure_lines = [
        f"- 当前模块：{_text(module.get('name'))}",
        f"- 模块序号：第 {module_index}/{total_modules} 张",
        f"- 模块职责：{_text(module.get('description'))}",
    ]
    if is_main_image:
        structure_lines.extend(
            [
                "- 只生成当前主图，不要拼接成长图，不要加入详情页模块边框或长段说明。",
                "- 画面建议为 1:1 电商货架主图构图，产品主体清晰、可点击率高、信息聚焦。",
            ]
        )
        if is_campaign_image:
            structure_lines.append("- 必须加入促销、活动、优惠或购买利益点等营销元素，但不能遮挡产品主体。")
    else:
        structure_lines.extend(
            [
                "- 只生成当前模块，不能新增一级模块，不能把其他模块的内容混入当前画面。",
                "- 画面必须按模块结构组织：主标题区、核心视觉区、数据/说明区、底部补充区。",
            ]
        )
    # White background modules should NOT have style colors/keywords injected
    is_white_bg = str(module.get("id")) in {"main_white_bg", "campaign_white_bg"}

    if is_white_bg:
        style_section = [
            "【视觉要求】",
            "- 背景：只删除参考图背景并替换为纯白色（#FFFFFF），无渐变、无纹理、无氛围色。",
            "- 产品本体不重绘、不改字、不改 Logo、不改标签、不改包装图案，不能生成空白标签。",
            "- 产品外观如有参考图必须保持一致。",
            "- 不出现乱码、水印、品牌侵权标识。",
        ]
    else:
        style_section = [
            "【统一视觉风格】",
            f"- 风格名称：{_text(style.get('name'), '绿色修护风')}",
            f"- 主色：{_text(style.get('primary_color'), '根据风格选择主色')}",
            f"- 视觉关键词：{style_keywords}",
            "- 中文电商视觉，高级、干净、统一；产品外观如有参考图必须保持一致。",
            "- 字体层级清楚，标题短促有力，说明文字清晰可读，不出现乱码、水印、品牌侵权标识。",
            "- 所有效果、权威、成分表达必须谨慎，不使用医疗化、绝对化承诺。",
        ]

    visual_constraints = _module_visual_constraints(module)

    return "\n".join(
        [
            f"你是电商护肤详情页视觉生成模型。请根据以下隐藏提示词生成 1 张{module_kind}。",
            "",
            "【固定模块结构】",
            *structure_lines,
            "",
            build_module_specific_brief(product_info, module),
            "",
            *(
                [
                    "【活动促销信息】",
                    _text(promotion_info, "用户未填写具体促销方式；只能使用泛化活动氛围，不得编造折扣、价格、日期、赠品或满减门槛"),
                    "",
                ]
                if is_campaign_image
                else []
            ),
            "【当前模块内容要求】",
            _module_requirements(module, product_info),
            *(["", visual_constraints] if visual_constraints else []),
            "",
            *style_section,
        ]
    )
