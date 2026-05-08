from __future__ import annotations

import re
from typing import Any


def _text(value: Any, fallback: str = "产品信息") -> str:
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
        return "1. 成分：核心植萃；作用：辅助日常肌肤护理\n2. 成分：保湿复配；作用：提升水润肤感"

    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            name = _text(item.get("name"), "")
            benefit = _text(item.get("benefit"), "辅助日常肌肤护理")
            if name:
                lines.append(f"{index}. 成分：{name}；作用：{benefit}")
        else:
            name = str(item).strip()
            if name:
                lines.append(f"{index}. 成分：{name}；作用：辅助日常肌肤护理")
    return "\n".join(lines) if lines else "1. 成分：核心植萃；作用：辅助日常肌肤护理\n2. 成分：保湿复配；作用：提升水润肤感"


def _authority_asset_label(item: str) -> str:
    label = re.split(r"[：:，,；;\n]", item, maxsplit=1)[0].strip()
    label = re.sub(r"报告编号\s*[:：]?\s*[A-Za-z0-9_-]+", "", label).strip()
    return label or "实验室检测报告"


def _format_authority_assets(value: Any) -> str:
    items = _string_items(value)
    if not items:
        return (
            "1. 权威方向：实验室研发、配方研究、检测报告视觉；"
            "画面表达：科学家实验场景中的局部纸质资质、证书纸张和泛化标签，机构名称与编号保持模糊处理"
        )
    return "\n".join(
        f"{index}. 权威方向：{_authority_asset_label(item)}；画面表达：科学家实验场景中的局部纸质资质、证书页、纸张纹理、图表形状和泛化标签，编号、样本量、机构编号等细节保持模糊处理"
        for index, item in enumerate(items, start=1)
    )


def _format_effect_claims(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return (
            "1. 指标：水润感；呈现：进度条或对比卡片视觉；表达：体验感导向，避免绝对化医疗表达"
        )

    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            claim = _text(item.get("claim"), "")
            value_text = _text(item.get("value"), "柔和进度视觉")
            source_type = str(item.get("source_type", "")).strip()
            if claim:
                source_label = f"；依据：{source_type}" if source_type and source_type != "ai_generated" else ""
                lines.append(f"{index}. 指标：{claim}；数值：{value_text}{source_label}")
        else:
            claim = str(item).strip()
            if claim:
                lines.append(f"{index}. 指标：{claim}；数值：柔和进度视觉")
    if not lines:
        return (
            "1. 指标：水润感；呈现：进度条或对比卡片视觉；表达：体验感导向，避免绝对化医疗表达"
        )
    return "\n".join(lines)


def build_product_generation_brief(product_info: dict[str, Any] | None) -> str:
    info = product_info or {}
    return "\n".join(
        [
            "【产品生成 brief】",
            f"- 产品名称：{_text(info.get('product_name'), '当前护肤产品')}",
            f"- 品类：{_text(info.get('category'), '护肤品')}",
            f"- 规格：{_text(info.get('spec'), '常规规格')}",
            "- 核心卖点：",
            _numbered_lines(_string_items(info.get("core_selling_points")), "温和护理"),
            "- 核心功效：",
            _numbered_lines(_string_items(info.get("functions")), "补水保湿"),
            "- 核心成分小报告：",
            _format_ingredients(info.get("ingredients")),
            "- 目标人群：",
            _numbered_lines(_string_items(info.get("target_users")), "日常护肤人群"),
            "- 使用方法：",
            _numbered_lines(_string_items(info.get("usage_method")), "洁面后取适量涂抹"),
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
        "layout": "产品占画面约 45-55%，居中或居中偏左；上方或右侧放主标题（核心卖点，字号大、醒目），下方或次要位置放副标题（品类/功效关键词，字号小）；背景使用品牌主色深浅渐变铺满画面",
        "primary_visual": "品牌色渐变氛围背景 + 产品大图（带光影和微倒影）+ 大号主标题 + 小号副标题 + 品类质感装饰元素（水珠/叶片/精华液滴/光泽纹理）",
        "product_role": "最大视觉主体，带柔光、边缘光或光晕增强存在感；产品不是孤立放在空白上，而是嵌入有氛围的场景中",
        "forbidden": "成分表、成分卡片、数据图表、使用步骤、人物使用场景、纯白或纯浅色大面积空白背景、产品孤零零放在空白画面中",
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
        "layout": "产品占画面约 45-55%，居中或居中偏左；搭配促销角标、优惠券样式标签；上方或右侧放主标题（核心卖点，字号大），副标题放促销利益点；背景使用活动感品牌色渐变铺满画面",
        "primary_visual": "活动氛围渐变背景 + 产品大图（带光影和微倒影）+ 大号主标题 + 促销标签 + 品类质感装饰元素 + 活动角标",
        "product_role": "最大视觉主体，带柔光和光晕；必须压过活动装饰，产品不能孤立放在空白上",
        "forbidden": "成分表、成分卡片、数据图表、使用步骤、人物使用场景、纯白或纯浅色大面积空白背景",
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
        f"- 产品名称：{_text(info.get('product_name'), '当前护肤产品')}",
    ]

    if module_id in {"main_white_bg", "campaign_white_bg"}:
        return "\n".join([*base_lines, f"- 规格：{_text(info.get('spec'), '常规规格')}"])

    if module_id in {"main_hero_selling_point", "campaign_hero_selling_point"}:
        return "\n".join(
            [
                *base_lines,
                f"- 品类：{_text(info.get('category'), '护肤品')}",
                "- 主标题使用前 2 个核心卖点（字号大、醒目）：",
                _limited_numbered_lines(info.get("core_selling_points"), "温和护理", 2),
                "- 副标题可使用前 2 个核心功效关键词（字号小、辅助信息）：",
                _limited_numbered_lines(info.get("functions"), "补水保湿", 2),
            ]
        )

    if module_id in {"main_ingredient", "campaign_ingredient"}:
        return "\n".join([*base_lines, "- 本图只使用核心成分信息：", _format_ingredients(info.get("ingredients"))])

    if module_id in {"main_effect", "campaign_effect"}:
        return "\n".join(
            [
                *base_lines,
                "- 本图只使用核心功效：",
                _limited_numbered_lines(info.get("functions"), "补水保湿", 3),
                "- 本图只使用效果数据：",
                _format_effect_claims(info.get("effect_claims")),
            ]
        )

    if module_id in {"main_usage_scene", "campaign_usage_scene"}:
        return "\n".join(
            [
                *base_lines,
                "- 本图只使用目标人群：",
                _limited_numbered_lines(info.get("target_users"), "日常护肤人群", 3),
                "- 本图只使用使用方法：",
                _limited_numbered_lines(info.get("usage_method"), "洁面后取适量涂抹", 4),
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


def _detail_text_guardrails() -> str:
    return "\n".join(
        [
            "【图片文字边界】",
            "- 图片必须像可直接用于店铺上架的成品物料，只呈现消费者会看到的标题、卖点标签、指标或步骤。",
            "- 隐藏 brief、模块职责、资料限制、合规提醒只作为生成依据，不能排版成图片里的说明框、段落、清单、脚注或底部文字区域。",
            "- 资料不足时减少文字密度和卡片数量，只保留确定的正向卖点；不能出现信息缺失、核验提醒、补全提醒或以外部资料为准的半成品提示。",
            "- 纸质资质只作为辅助物件；当报告出现时只能做成真实纸质材质：纸张、证书页、装订报告册、桌面文件夹或盖章文件；正文必须是不可读纹理、抽象线条或极短泛化标签，不能生成可阅读的长句说明。",
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
            "画面呈现店铺首图，这是用户在电商货架上看到的第一张图，必须在 0.3 秒内抓住注意力。",
            "背景：使用品牌主色系的渐变铺满整个画面，避免大面积空白或纯白；可用径向渐变、光晕、深→浅过渡营造高级氛围。",
            "产品：作为最大视觉主体居中展示，带柔和光影和微投影/倒影增强立体感；产品不能孤零零放在空白上。",
            "品类质感元素：根据产品品类和风格，在产品周围自然散布 2-4 个质感装饰（如水珠、植物叶片、精华液滴、丝绸纹理、光泽粒子），增加画面丰富度但不能抢过产品。",
            "文字层级：主标题用核心卖点（字号大、醒目、放在视觉焦点区域），副标题用品类或功效关键词（字号小、作为辅助信息）。文字要有透视感或阴影，不能像贴纸一样平贴在画面上。",
            "装饰光效：可添加光斑 bokeh、微粒漂浮、柔光光晕等元素，增加高级感和画面呼吸感。",
            "整体目标：像天猫爆款护肤品首图一样——饱满、高级、有冲击力，不是简约留白风。",
        ],
        "main_ingredient": [
            "画面只呈现成分次图，突出核心成分、原料质感和成分标签。",
            "必须参考以下成分信息，选择 2-3 个重点成分呈现：",
            ingredients_report,
            "文案必须像可直接用于店铺上架的成品成分图，只写成分名、正向作用标签和短标题。",
            "如果成分资料较少，就减少卡片数量，用原料质感补足画面，不写信息缺失提示。",
            "成分作用表达要谨慎，不能写成药品疗效或治疗承诺。",
        ],
        "main_effect": [
            "画面只呈现效果次图，突出核心功效、使用收益和可信的效果表达。",
            "优先参考以下效果数据；如果数据不完整，画面用体验型视觉和进度条表达：",
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
            "画面呈现活动首图，这是活动期间用户在货架看到的第一张图，必须同时传递产品价值和促销刺激。",
            "背景：使用带活动感的品牌色渐变铺满画面，可叠加节日/促销氛围光效，避免大面积空白或纯白。",
            "产品：作为最大视觉主体居中展示，带柔和光影和微投影/倒影增强立体感；必须压过活动装饰。",
            "品类质感元素：根据产品品类在产品周围散布 2-4 个质感装饰（水珠、叶片、精华液滴等），增加画面丰富度。",
            "文字层级：主标题用核心卖点（字号大），副标题放促销利益点（优惠券、限时角标、满减标签），层级分明不混乱。",
            "促销表达需来自用户填写的活动信息，可使用优惠券、限时角标、满减标签、折扣贴纸等电商活动元素。",
            "装饰光效：可添加光斑、微粒、活动礼花等元素增加节日感。",
            "整体目标：像天猫大促护肤首图——饱满、有冲击力、有促销紧迫感。",
        ],
        "campaign_ingredient": [
            "画面呈现活动成分次图，展示核心成分与原料质感，同时加入活动氛围元素。",
            "必须参考以下成分信息，选择 2-3 个重点成分呈现：",
            ingredients_report,
            "文案必须像可直接用于店铺上架的成品成分图，只写成分名、正向作用标签和短标题。",
            "如果成分资料较少，就减少卡片数量，用原料质感补足画面，不写信息缺失提示。",
            "促销元素作为辅助转化信息出现，不能压过成分可信表达，也不能写成药品疗效。",
        ],
        "campaign_effect": [
            "画面呈现活动效果次图，突出核心功效、使用收益和促销转化理由。",
            "优先参考以下效果数据；如果数据不完整，画面用体验型视觉和进度条表达：",
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
            "画面只呈现权威资质展示，科学家实验画面为主体：研究员穿实验服在明亮真实实验室中操作显微镜、滴管、试管、样本瓶或护肤配方实验器具。",
            "人物和实验动作占画面主要视觉面积，呈现正在研究、观察、记录或调配的专业过程；实验台、玻璃器皿、柔和实验室光线要真实可信。",
            "纸质资质只占画面局部，不超过画面 25%，可出现在前景一角、桌面边缘或研究员手边，作为辅助证明物件。",
            "局部纸质资质要有可触摸材质：纸张纤维、轻微折痕、页脚厚度、装订线或文件夹边缘；只能露出一部分，不要让纸质资质成为主视觉。",
            "纸质资质可搭配印章轮廓、图表形状、证书边框和少量标签；文字必须小且虚化/泛化，不写具体报告编号、样本编号、机构编号或可核验编号。",
            "不要半透明 UI 卡片、悬浮数据面板、玻璃拟态卡片或电子屏幕式报告；报告如果出现，必须像真实拍摄中的纸张文件局部。",
            "必须参考以下权威资料方向，但不要把完整原文搬到画面上：",
            authority_report,
            "版式建议：科学家实验室研究场景 + 画面一角局部纸质资质 + 简洁模块标题；不做底部说明区、资料建议区或风险提示类文字。",
        ],
        "pain_scene": [
            "画面只呈现目标人群的护肤痛点场景，突出困扰、情绪和产品解决方向。",
            "痛点来自目标人群与核心功效，不要提前展示效果数据或权威报告。",
        ],
        "effect_comparison": [
            "画面只呈现效果对比，必须像小报告一样写清楚每条效果数据。",
            "必须完整带入以下效果数据：",
            effect_report,
            "如果数据不完整，画面用体验型视觉和进度条表达；避免绝对化医疗表达，不写治愈、根治、永久有效。",
        ],
        "competitor_comparison": [
            "画面只呈现本产品与普通同类产品的对比，不指名真实竞品品牌。",
            "对比维度建议：成分思路、肤感、使用体验、适合人群、卖点完整度。",
        ],
        "ingredient": [
            "画面只呈现成分页，必须把核心成分和对应作用讲清楚。",
            "必须完整带入以下成分信息：",
            ingredients_report,
            "文案必须像可直接用于店铺上架的成品成分图，只写成分名、正向作用标签和短标题。",
            "如果成分资料较少，就减少卡片数量，用原料质感补足画面，不写信息缺失提示。",
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
    has_style_reference: bool = False,
) -> str:
    style_keywords = " / ".join(_string_items(style.get("keywords"))) or "高级 / 干净 / 统一"
    group = module.get("image_group")
    is_main_image = group in {"main", "campaign"}
    is_campaign_image = group == "campaign"
    module_kind = "中文电商活动主图" if is_campaign_image else "中文电商商品主图" if is_main_image else "中文商品详情页单模块图片"
    readable_text_rule = (
        "- 字体层级清楚，标题短促有力，说明文字清晰可读，不出现乱码、水印、品牌侵权标识。"
        if is_main_image
        else "- 仅短标题、极短标签、必要数值或步骤编号需要清晰可读；不要生成说明文字、段落脚注、资料建议或风险提示类文案，不出现乱码、水印、品牌侵权标识。"
    )
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
                "- 画面以核心视觉为主，可搭配短标题和少量视觉标签；不要做成带大段文字的说明板。",
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
            "- 所有可见文字必须像可直接用于店铺上架的成品图文案，不写信息缺失或核验提醒。",
        ]
    else:
        if has_style_reference:
            style_section = [
                "【统一视觉风格】",
                "- 上传的风格参考图优先：只参考排版、色调、光影和氛围，不改变产品外观、包装和品牌信息。",
                "- 不要混入预设风格名称、主色或关键词；风格只以已上传的风格参考图为准。",
                "- 中文电商视觉，高级、干净、统一；产品外观如有产品参考图必须保持一致。",
                readable_text_rule,
                "- 所有可见文字必须像可直接用于店铺上架的成品图文案，不写信息缺失、核验提醒、补全提醒或半成品提示。",
                "- 所有效果、权威、成分表达必须谨慎，不使用医疗化、绝对化承诺。",
            ]
        else:
            style_section = [
                "【统一视觉风格】",
                f"- 风格名称：{_text(style.get('name'), '绿色修护风')}",
                f"- 主色：{_text(style.get('primary_color'), '根据风格选择主色')}",
                f"- 视觉关键词：{style_keywords}",
                *(
                    [
                        f"- AI 规划视觉方向：{_text(style.get('visual_direction'), '')}",
                        f"- AI 规划版式方向：{_text(style.get('layout_guidance'), '')}",
                    ]
                    if style.get("id") == "ai_custom"
                    else []
                ),
                "- 中文电商视觉，高级、干净、统一；产品外观如有参考图必须保持一致。",
                readable_text_rule,
                "- 所有可见文字必须像可直接用于店铺上架的成品图文案，不写信息缺失、核验提醒、补全提醒或半成品提示。",
                "- 所有效果、权威、成分表达必须谨慎，不使用医疗化、绝对化承诺。",
            ]

    visual_constraints = _module_visual_constraints(module)
    detail_text_guardrails = _detail_text_guardrails() if not is_main_image else ""

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
            *(["", detail_text_guardrails] if detail_text_guardrails else []),
            "",
            *style_section,
        ]
    )
