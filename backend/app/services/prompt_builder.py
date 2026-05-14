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
    return _format_ingredient_items(_selected_ingredients(value))


FALLBACK_INGREDIENTS = [
    {"name": "核心植萃", "benefit": "辅助日常肌肤护理"},
    {"name": "保湿复配", "benefit": "提升水润肤感"},
    {"name": "舒缓因子", "benefit": "帮助维持肌肤舒适状态"},
]


PLACEHOLDER_INGREDIENT_BENEFITS = (
    "待确认",
    "待说明",
    "待补充",
    "作用待确认",
    "功效待确认",
    "效果待确认",
    "资料待确认",
    "资料不足",
    "未提供",
    "未知",
    "不详",
    "n/a",
)


def _is_placeholder_ingredient_benefit(value: str) -> bool:
    cleaned = value.strip().lower()
    return not cleaned or any(keyword in cleaned for keyword in PLACEHOLDER_INGREDIENT_BENEFITS)


def _ingredient_default_benefit(name: str) -> str:
    normalized = name.lower()
    if any(keyword in normalized for keyword in ("透明质酸", "玻尿酸", "hyaluronic")):
        return "帮助提升水润肤感"
    if any(keyword in normalized for keyword in ("烟酰胺", "niacinamide")):
        return "帮助提亮肤色观感"
    if any(keyword in normalized for keyword in ("积雪草", "cica", "centella")):
        return "帮助舒缓干燥不适"
    if any(keyword in normalized for keyword in ("神经酰胺", "ceramide", "泛醇", "panthenol")):
        return "帮助维持肌肤屏障舒适"
    if any(keyword in normalized for keyword in ("胶原", "胜肽", "肽", "玻色因", "pro-xylane")):
        return "帮助支撑紧致弹润肤感"
    if any(keyword in normalized for keyword in ("甘油", "角鲨烷", "squalane")):
        return "帮助提升滋润肤感"
    return "辅助日常肌肤护理"


def _safe_ingredient_benefit(name: str, value: Any) -> str:
    benefit = _text(value, "")
    return _ingredient_default_benefit(name) if _is_placeholder_ingredient_benefit(benefit) else benefit


def _ingredient_items(value: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = _text(item.get("name"), "")
                if name:
                    benefit = _safe_ingredient_benefit(name, item.get("benefit"))
                    items.append({"name": name, "benefit": benefit})
            else:
                name = str(item).strip()
                if name:
                    items.append({"name": name, "benefit": _ingredient_default_benefit(name)})

    seen = {item["name"] for item in items}
    for fallback in FALLBACK_INGREDIENTS:
        if len(items) >= 3:
            break
        if fallback["name"] not in seen:
            items.append(fallback)
            seen.add(fallback["name"])
    return items


def _selected_ingredients(value: Any, limit: int = 3) -> list[dict[str, str]]:
    return _ingredient_items(value)[:limit]


def _format_ingredient_items(items: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{index}. 成分：{item['name']}；作用：{item['benefit']}"
        for index, item in enumerate(items, start=1)
    )


def _single_ingredient_index(module_id: str) -> int | None:
    match = re.fullmatch(r"ingredient_([123])", module_id)
    return int(match.group(1)) - 1 if match else None


def _ingredient_visual_direction(ingredient: dict[str, str]) -> str:
    combined = f"{ingredient['name']} {ingredient['benefit']}"
    if any(keyword in combined for keyword in ("透明质酸", "玻尿酸", "水润", "补水", "保湿", "锁水", "甘油")):
        return "透明水滴、清透精华液、凝露质地和高光液滴微距"
    if any(keyword in combined for keyword in ("烟酰胺", "提亮", "亮肤", "VC", "维C", "光泽")):
        return "柔和透亮光感、细腻珍珠白光泽和清爽精华质地"
    if any(keyword in combined for keyword in ("积雪草", "CICA", "舒缓", "泛红", "干燥不适")):
        return "绿色植萃叶片、晨露微距和舒缓清透的植物原料质感"
    if any(keyword in combined for keyword in ("神经酰胺", "屏障", "修护", "强韧", "泛醇")):
        return "仿生脂质层、柔和保护膜、润泽膏霜切面和细腻包裹感"
    return "高级原料微距、晶莹液滴、原料切面和干净商业护肤摄影光影"


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
        f"{index}. 权威方向：{_authority_asset_label(item)}；画面表达：局部纸质资质、证书页、图表形状和泛化标签，编号细节模糊处理"
        for index, item in enumerate(items, start=1)
    )


def _user_priority_note() -> str:
    return "用户上传资料和手写信息优先；AI 只在资料缺失时做安全泛化补充，不覆盖用户已确认字段。"


def _format_brand_assets(info: dict[str, Any]) -> str:
    items = [*_string_items(info.get("material_highlights")), *_string_items(info.get("authority_assets"))]
    if not items:
        items = ["品牌背景", "产地来源", "官方渠道保障", "泛化权威认证"]
    return _numbered_lines(items[:5], "品牌背景与资质背书")


def _format_product_detail_items(info: dict[str, Any]) -> str:
    lines = [
        f"产品名称：{_text(info.get('product_name'), '当前护肤产品')}",
        f"品类：{_text(info.get('category'), '护肤品')}",
        f"规格：{_text(info.get('spec'), '常规规格')}",
        "核心功效：" + " / ".join(_string_items(info.get("functions"))[:3] or ["日常护肤护理"]),
        "核心成分：" + " / ".join(f"{item['name']}：{item['benefit']}" for item in _selected_ingredients(info.get("ingredients"))),
        "使用方法：" + " / ".join(_string_items(info.get("usage_method"))[:3] or ["洁面后取适量使用"]),
    ]
    highlights = _string_items(info.get("material_highlights"))[:4]
    if highlights:
        lines.extend(highlights)
    return "\n".join(f"{index}. {item}" for index, item in enumerate(lines, start=1))


DEFAULT_EFFECT_PERCENT_VALUES = ("89%", "86%", "83%", "80%", "78%")


def _fallback_effect_percent(index: int) -> str:
    return DEFAULT_EFFECT_PERCENT_VALUES[(index - 1) % len(DEFAULT_EFFECT_PERCENT_VALUES)]


def _format_effect_claims(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return (
            "1. 指标：水润感；数值：89%；呈现：进度条或对比卡片视觉；表达：体验感导向，避免绝对化医疗表达"
        )

    lines: list[str] = []
    for index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            claim = _text(item.get("claim"), "")
            raw_value_text = _text(item.get("value"), "")
            value_text = raw_value_text or _fallback_effect_percent(index)
            source_type = str(item.get("source_type", "")).strip()
            if claim:
                source_label = f"；依据：{source_type}" if raw_value_text and source_type and source_type != "ai_generated" else ""
                lines.append(f"{index}. 指标：{claim}；数值：{value_text}{source_label}")
        else:
            claim = str(item).strip()
            if claim:
                lines.append(f"{index}. 指标：{claim}；数值：{_fallback_effect_percent(index)}")
    if not lines:
        return (
            "1. 指标：水润感；数值：89%；呈现：进度条或对比卡片视觉；表达：体验感导向，避免绝对化医疗表达"
        )
    return "\n".join(lines)


HYDRATION_EFFECT_KEYWORDS = ("水润", "补水", "保湿", "含水量", "水分", "锁水", "干燥")


def _is_hydration_effect_context(product_info: dict[str, Any] | None) -> bool:
    info = product_info or {}
    values: list[str] = []
    for key in ("product_name", "category", "spec"):
        values.append(_text(info.get(key), ""))
    for key in ("core_selling_points", "functions", "effect_claims"):
        values.extend(_string_items(info.get(key)))
    combined = " ".join(values)
    return any(keyword in combined for keyword in HYDRATION_EFFECT_KEYWORDS)


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
            "- 资料亮点摘要：",
            _numbered_lines(_string_items(info.get("material_highlights")), "资料显示产品具备可信的日常护理卖点"),
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
        "layout": "产品占画面约 45-55%，居中或居中偏左；用空间透视建立前景、中景、背景层次，产品放在质感陈列台上（水面、石材或亚克力镜面），上方或右侧放主标题，下方或次要位置放副标题；背景使用品牌主色深浅渐变铺满画面",
        "primary_visual": "品牌色渐变氛围背景 + 产品大图（带光影和微倒影）+ 质感陈列台 + 大号主标题 + 小号副标题 + 品类质感装饰元素（水珠/叶片/精华液滴/光泽纹理）+ 体积感环境光、流动丝绸质感或水波纹焦散",
        "product_role": "最大视觉主体，使用商业香水/护肤品级布光、强轮廓边缘光和克制镜面反射增强存在感；产品不是孤立放在空白上，而是嵌入有空间深度的场景中",
        "forbidden": "成分表、成分卡片、数据图表、使用步骤、人物使用场景、纯白或纯浅色大面积空白背景、产品孤零零放在空白画面中、扁平海报感背景、廉价贴纸光效",
    },
    "main_ingredient": {
        "layout": "左右分栏：左侧使用极浅景深超微距摄影呈现原料实物微距特写，右侧成分名与作用卡片；前景原料可轻微越界形成纵深",
        "primary_visual": "晶莹剔透的原料实物质感，例如叶片、透明液滴、原料切面或精华质地；带晨露质感、发光精华液滴和清透高调色彩",
        "product_role": "缩小放在右下角作为辅助，或完全不出现",
        "forbidden": "效果数据百分比、数据仪表盘、使用步骤、人物使用场景、产品居中环绕文字构图、浑浊廉价的植物堆叠、脏乱泥土背景",
    },
    "main_effect": {
        "layout": "上下分区：上方肌肤质感或体验感画面，下方使用未来科技感玻璃拟态卡片承载数据仪表盘、进度条或对比卡片；用极简几何细线连接指标",
        "primary_visual": "可信的数据可视化图表 + 顶级美妆摄影光影下的肌肤质感体验，肌肤无暇但保留真实毛孔和自然纹理",
        "product_role": "缩小放在角落作为辅助，不作为画面中心",
        "forbidden": "成分详情列表、原料微距主视觉、使用步骤、人物使用场景、产品居中环绕文字构图、枯燥 PPT 数据板、劣质医学对比图",
    },
    "main_usage_scene": {
        "layout": "场景化全幅构图，置于极简奢华浴室或梳妆台一角；人物手部、滴管、面部护理或梳妆台使用动作占主画面",
        "primary_visual": "真实使用动作与高级生活方式护理场景，柔和自然窗光穿过纱帘或百叶窗，带丁达尔光晕和轻微 bokeh，手部姿态优雅",
        "product_role": "嵌入场景中清晰可见，但不是孤立居中展示",
        "forbidden": "数据图表、成分列表、原料卡片、产品居中环绕文字构图、凌乱居家背景、随意自拍感、夸张摆拍表情",
    },
    "campaign_white_bg": {
        "layout": "只删除参考图背景并替换为纯白背景，产品居中完整展示，角落可加入小面积促销角标",
        "primary_visual": "参考图中的原始产品瓶身或包装 + 克制活动角标",
        "product_role": "最大主体；产品标签、文字、Logo、图案和包装细节必须保持原样，角标不能遮挡产品",
        "forbidden": "复杂场景、植物、水滴、光效、道具、人物、大面积活动背景、编造价格折扣日期",
    },
    "campaign_hero_selling_point": {
        "layout": "产品占画面约 45-55%，居中或居中偏左；用空间透视和质感陈列台建立高级活动场景，搭配促销角标、优惠券样式标签；上方或右侧放主标题，副标题放促销利益点；背景使用活动感品牌色渐变铺满画面",
        "primary_visual": "活动氛围渐变背景 + 产品大图（带光影和微倒影）+ 质感陈列台 + 大号主标题 + 促销标签 + 品类质感装饰元素 + 活动角标 + 体积感环境光",
        "product_role": "最大视觉主体，使用商业香水/护肤品级布光、强轮廓边缘光和克制光晕；必须压过活动装饰，产品不能孤立放在空白上",
        "forbidden": "成分表、成分卡片、数据图表、使用步骤、人物使用场景、纯白或纯浅色大面积空白背景、促销元素挤满画面",
    },
    "campaign_ingredient": {
        "layout": "成分卡片堆叠布局，背景用极浅景深超微距摄影呈现原料质感，角落加入轻量活动角标",
        "primary_visual": "成分卡片 + 晶莹剔透的原料微距 + 晨露质感 + 发光精华液滴 + 清透高调色彩 + 轻活动氛围",
        "product_role": "缩小放角落或不出现，不作为中心主体",
        "forbidden": "效果数据、数据仪表盘、使用场景人物、产品居中环绕文字构图、浑浊廉价的植物堆叠",
    },
    "campaign_effect": {
        "layout": "数据仪表盘或进度环构图，使用未来科技感玻璃拟态卡片和极简几何细线，搭配促销利益点标签",
        "primary_visual": "数据可视化图表 + 顶级美妆摄影光影下的肌肤质感体验 + 促销转化标签",
        "product_role": "缩小放角落作为辅助",
        "forbidden": "成分详情列表、原料微距主视觉、使用场景人物、产品居中环绕文字构图、枯燥 PPT 数据板、劣质医学对比图",
    },
    "campaign_usage_scene": {
        "layout": "活动场景图，置于极简奢华浴室或梳妆台一角，使用动作占主画面，并加入礼盒、优惠券或活动标签氛围",
        "primary_visual": "使用场景 + 礼盒或活动氛围元素 + 柔和自然窗光 + 丁达尔光晕 + 优雅手部姿态",
        "product_role": "嵌入场景中清晰可见",
        "forbidden": "数据图表、成分列表、原料卡片、产品居中环绕文字构图、凌乱居家背景、随意自拍感",
    },
    "brand_qualification": {
        "layout": "品牌与资质背书整屏：主体使用法式建筑、品牌门店或街景橱窗建立品牌来源感；下方可用少量产地、官方渠道、正品保障和认证图标收束",
        "primary_visual": "法式建筑立面 + 品牌门店橱窗 + 产地来源文字氛围 + 官方旗舰店/正品保障/权威认证小标识，像品牌官网和线下门店背书页",
        "product_role": "产品可小比例放在门店橱窗、柜台或角落作品牌商品提示，不作为画面中心",
        "forbidden": "实验室器械、显微镜、烧瓶、研发人员、效果对比、肌肤痛点、成分微距、使用步骤、虚假真实机构和可核验编号",
    },
    "research_strength": {
        "layout": "研发实力拼图：实验室主图 + 研发流程/真人测试小图 + 局部检测报告或印章纸张",
        "primary_visual": "实验室器械、烧瓶、试管、显微镜、科研人员、真人测试、报告文件和印章轮廓",
        "product_role": "产品可作为实验样本或配方来源小比例出现，不抢实验室和研发证据主视觉",
        "forbidden": "品牌门店、法式街景、竞品对比、产品大图海报、完整成分表、使用步骤、可核验编号",
    },
    "product_showcase": {
        "layout": "产品大图强化：产品瓶身作为最大主视觉，占画面 45%-60%；旁边展示质地液体、功效短标签和 0 添加图标",
        "primary_visual": "产品大图 + 功效 + 质地 + 0添加；可加入清透精华质地、水润液滴、柔和流线、0 酒精/0 色素/0 添加图标",
        "product_role": "最大视觉主体，瓶身包装清晰，使用商业护肤品棚拍光和克制倒影；质地与图标围绕产品服务",
        "forbidden": "品牌门店、实验室报告、痛点人脸、竞品表格、完整成分表、使用步骤、过密说明文字",
    },
    "ingredient_overview": {
        "layout": "成分体系总览：顶部短标题，中部用 3 个成分体系节点或原料浮岛建立配方逻辑，下方用一句复配总结收束",
        "primary_visual": "多重成分复配体系 + 原料微距浮岛 + 精华液流动纹理 + 清透商业摄影光影",
        "product_role": "产品缩小放角落作为配方来源提示，不作为主视觉中心",
        "forbidden": "完整成分表、超过 3 个成分卡片、长段说明文字、药品疗效、密集百科式排版、脏乱植物堆叠",
    },
    "product_info": {
        "layout": "产品信息页：米色纸质背景或浅色说明书版式，标题区 + 参数分组 + 成分/使用说明短段落，整体正式、干净、可阅读",
        "primary_visual": "产品名称、功效、规格、保质期、产地、成分、使用说明等参数信息；可配极少量产品线稿或小比例产品图",
        "product_role": "产品小比例辅助出现，重点是参数信息和说明书质感，不做大图海报",
        "forbidden": "功效夸张承诺、编造产地和保质期、品牌门店、实验室大场景、肌肤对比图、竞品攻击、促销贴纸",
    },
    "ingredient_1": {
        "layout": "单成分讲解图：一个核心成分占主视觉，成分名做大标题，作用只保留一句短标签，画面留出高级负空间",
        "primary_visual": "单一成分原料微距 + 晶莹液滴 + 精华质地 + 电商成分大片光影",
        "product_role": "产品只在右下角或画面边缘小比例出现，也可以不出现",
        "forbidden": "多个成分并列、完整成分表、效果数据百分比、使用步骤、药品疗效、长段说明文字",
    },
    "ingredient_2": {
        "layout": "单成分讲解图：一个核心成分占主视觉，成分名做大标题，作用只保留一句短标签，画面留出高级负空间",
        "primary_visual": "单一成分原料微距 + 晶莹液滴 + 精华质地 + 电商成分大片光影",
        "product_role": "产品只在右下角或画面边缘小比例出现，也可以不出现",
        "forbidden": "多个成分并列、完整成分表、效果数据百分比、使用步骤、药品疗效、长段说明文字",
    },
    "ingredient_3": {
        "layout": "单成分讲解图：一个核心成分占主视觉，成分名做大标题，作用只保留一句短标签，画面留出高级负空间",
        "primary_visual": "单一成分原料微距 + 晶莹液滴 + 精华质地 + 电商成分大片光影",
        "product_role": "产品只在右下角或画面边缘小比例出现，也可以不出现",
        "forbidden": "多个成分并列、完整成分表、效果数据百分比、使用步骤、药品疗效、长段说明文字",
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

    if module_id == "brand_qualification":
        return "\n".join(
            [
                *base_lines,
                f"- 品类：{_text(info.get('category'), '护肤品')}",
                "- 用户手写核心卖点优先作为品牌页辅助定位：",
                _limited_numbered_lines(info.get("core_selling_points"), "温和护理", 2),
                f"- 资料优先级：{_user_priority_note()}",
                "- 本图只使用品牌背景、产地来源、渠道保障和资质认证类信息：",
                _format_brand_assets(info),
            ]
        )

    if module_id in {"research_strength", "authority"}:
        return "\n".join(
            [
                *base_lines,
                f"- 品类：{_text(info.get('category'), '护肤品')}",
                f"- 资料优先级：{_user_priority_note()}",
                "- 本图只使用研发、实验、检测、报告、专利或测试类信息：",
                _format_authority_assets(info.get("authority_assets")),
            ]
        )

    if module_id == "product_showcase":
        return "\n".join(
            [
                *base_lines,
                f"- 品类：{_text(info.get('category'), '护肤品')}",
                "- 本图只使用核心卖点：",
                _limited_numbered_lines(info.get("core_selling_points"), "温和护理", 3),
                "- 本图只使用核心功效：",
                _limited_numbered_lines(info.get("functions"), "补水保湿", 3),
                "- 可用资料亮点：",
                _limited_numbered_lines(info.get("material_highlights"), "质地清透，配方温和", 4),
            ]
        )

    if module_id == "ingredient_overview":
        selected = _selected_ingredients(info.get("ingredients"))
        return "\n".join(
            [
                *base_lines,
                f"- 品类：{_text(info.get('category'), '护肤品')}",
                "- 本图只做成分体系总览，最多展示以下 3 个核心成分：",
                _format_ingredient_items(selected),
                "- 复配总结：多重成分复配体系，建立配方可信感，不在本图逐个展开长篇解释。",
            ]
        )

    single_index = _single_ingredient_index(module_id)
    if single_index is not None:
        ingredient = _selected_ingredients(info.get("ingredients"))[single_index]
        return "\n".join(
            [
                *base_lines,
                "- 本图只解释一个核心成分，不带入其他成分：",
                f"1. 成分：{ingredient['name']}；作用：{ingredient['benefit']}；视觉方向：{_ingredient_visual_direction(ingredient)}",
            ]
        )

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

    if module_id == "pain_scene":
        return "\n".join([*base_lines, "- 目标人群：", _limited_numbered_lines(info.get("target_users"), "日常护肤人群", 3), "- 解决方向（核心功效）：", _limited_numbered_lines(info.get("functions"), "补水保湿", 3)])

    if module_id == "competitor_comparison":
        return "\n".join([*base_lines, "- 核心卖点：", _limited_numbered_lines(info.get("core_selling_points"), "温和护理", 3), "- 核心功效：", _limited_numbered_lines(info.get("functions"), "补水保湿", 3)])

    if module_id == "usage":
        return "\n".join([*base_lines, "- 使用方法：", _limited_numbered_lines(info.get("usage_method"), "洁面后取适量涂抹", 4)])

    if module_id == "product_info":
        return "\n".join(
            [
                *base_lines,
                f"- 资料优先级：{_user_priority_note()}",
                "- 本图只使用已上传资料、手写确认信息和安全泛化字段，产品参数如下：",
                _format_product_detail_items(info),
            ]
        )

    # Fallback: inject comprehensive product context for detail modules
    return "\n".join(
        [
            "【当前模块精简 brief】",
            f"- 产品名称：{_text(info.get('product_name'), '当前护肤产品')}",
            f"- 品类：{_text(info.get('category'), '护肤品')}",
            "- 核心卖点：",
            _limited_numbered_lines(info.get("core_selling_points"), "温和护理", 3),
            "- 核心功效：",
            _limited_numbered_lines(info.get("functions"), "补水保湿", 3),
            "- 资料亮点摘要：",
            _limited_numbered_lines(info.get("material_highlights"), "可信护理卖点", 3),
        ]
    )


PDD_PLATFORM_IDS = {"pdd", "pinduoduo", "拼多多"}


def _is_pdd_platform(platform_id: str | None) -> bool:
    return str(platform_id or "").strip().lower() in PDD_PLATFORM_IDS


PROMPT_OPTIMIZATION_BRANCH = "prompt_optimization"


def _is_prompt_optimization_branch(prompt_branch: str | None) -> bool:
    return str(prompt_branch or "").strip() == PROMPT_OPTIMIZATION_BRANCH


def _module_visual_recipe(module_id: str, platform_id: str | None) -> dict[str, str] | None:
    recipe = MODULE_VISUAL_RECIPES.get(module_id)
    if not recipe:
        return None
    if not _is_pdd_platform(platform_id):
        return recipe
    if module_id in {"main_hero_selling_point", "campaign_hero_selling_point"}:
        return {
            **recipe,
            "layout": "产品占画面约 60%-70%，居中或居中偏左，用近景压迫感建立第一视觉焦点；标题和标签围绕产品服务，不抢产品主体；背景饱满但不能把商品淹没",
            "primary_visual": f"拼多多高点击货架图 + 产品超大近景（带光影和微倒影）+ 大号核心卖点 + 少量高对比利益标签 + {recipe['primary_visual']}",
            "product_role": "绝对最大视觉主体，商品识别优先级高于背景氛围、装饰和标签；产品包装关键信息完整可见，不能被促销贴纸或光效压住",
        }
    if module_id in {"main_white_bg", "campaign_white_bg"}:
        return {
            **recipe,
            "product_role": "唯一主体，占画面 70%-85%；产品标签、文字、Logo、图案和包装细节必须保持原样",
        }
    return recipe


def _module_visual_constraints(module: dict[str, Any], platform_id: str | None = None) -> str:
    module_id = str(module.get("id"))
    recipe = _module_visual_recipe(module_id, platform_id)
    if not recipe:
        return ""

    lines = [
        "【构图差异化约束】",
        f"- 构图模板：{recipe['layout']}。",
        f"- 主视觉元素：{recipe['primary_visual']}。",
        f"- 产品角色：{recipe['product_role']}。",
        f"- 禁止出现：{recipe['forbidden']}。",
    ]
    if module_id not in {"main_white_bg", "campaign_white_bg"}:
        lines.append("- 视觉密度：装饰元素控制在 2-4 个，保留干净负空间和明确视觉焦点，避免把画面堆成拥挤海报。")
    lines.append("- 不要把本图做成其他主图模块的模板；每张主图必须有独立视觉主体和版式。")
    return "\n".join(lines)


def _detail_text_guardrails(module: dict[str, Any]) -> str:
    module_id = str(module.get("id"))
    if module_id == "product_info":
        return "\n".join(
            [
                "【图片文字边界】",
                "- 产品信息页允许清晰参数表、短成分摘要和使用说明短段落，但必须像正式说明书/产品信息页，不像风险提示或免责声明。",
                "- 用户上传资料和手写信息优先；没有资料的字段可用泛化安全表达，不能出现信息缺失、核验提醒、补全提醒或半成品提示。",
                "- 不能编造产地、保质期、备案编号、检测编号、真实机构名称或绝对化功效承诺。",
            ]
        )
    lines = [
        "【图片文字边界】",
        "- 图片必须像可直接用于店铺上架的成品物料，只呈现标题、卖点标签、指标或步骤。",
        "- 隐藏 brief、模块职责、资料限制、合规提醒只作为生成依据，不能排版成图片里的说明框、段落、清单、脚注或底部文字区域。",
        "- 资料不足时减少文字密度，只保留确定卖点；不能出现信息缺失、核验提醒、补全提醒或半成品提示。",
    ]
    if module_id in {"research_strength", "authority"}:
        lines.append(
            "- 纸质资质只作为辅助物件；当报告出现时只能做成真实纸质材质，正文用不可读纹理、抽象线条或极短泛化标签。"
        )
    return "\n".join(lines)


def _people_realism_guardrails(module: dict[str, Any]) -> str:
    module_id = str(module.get("id"))
    people_relevant_modules = {
        "main_usage_scene",
        "campaign_usage_scene",
        "pain_scene",
        "usage",
        "authority",
    }
    if module_id not in people_relevant_modules:
        return ""

    return "\n".join(
        [
            "【人物真实感约束】",
            "- 如画面出现人物、面部、手部或使用动作，人物必须是真实自然的普通消费者或真实模特，不要像 AI 精修人像。",
            "- 保留自然肤质、毛孔、细纹、轻微肤色不均和真实表情；不要生成过度漂亮、网红脸、AI感强、磨皮严重、玻璃皮。",
            "- 人物只服务于产品使用场景和效果表达，不能喧宾夺主；优先使用手部、半身、局部面部或真实使用动作。",
        ]
    )


def _effect_comparison_layout_guardrails(module: dict[str, Any], product_info: dict[str, Any] | None) -> str:
    module_id = str(module.get("id"))
    if module_id not in {"main_effect", "campaign_effect", "effect_comparison"}:
        return ""

    if module_id == "effect_comparison":
        area_rule = "局部前后对比组件建议约 30%-45% 画面面积"
    else:
        area_rule = "局部前后对比组件建议约 20%-35% 画面面积"

    lines = [
        "【效果对比构图约束】",
        f"- 采用局部前后对比组件，{area_rule}，不要让左右对比占满整张画面。",
        "- 画面必须同时包含产品主体、标题、使用前/使用后局部对比卡片，以及功效说明或数据指标区。",
        "- 前后变化要明显但可信：使用前干燥、暗沉、粗糙或紧绷；使用后更水润、平滑、均匀，不能像换脸或医疗治愈。",
    ]
    metric_area_label = "水润数据指标区" if _is_hydration_effect_context(product_info) else "效果数据指标区"
    lines.extend(
        [
            f"- {metric_area_label}必须显示百分比数字，字号和进度条视觉权重接近，不需要超大；不要只画无数字进度条/圆环/仪表盘。",
            "- 优先使用已有百分比数据；没有具体数值时必须使用具体示意百分比数字；禁止写 XX%、X%、--%、占位、待补充。",
        ]
    )
    return "\n".join(lines)


def _main_image_conversion_rules(module: dict[str, Any], platform_id: str | None = None) -> str:
    module_id = str(module.get("id"))
    if module_id in {"main_white_bg", "campaign_white_bg"}:
        return ""
    is_pdd = _is_pdd_platform(platform_id)
    hero_product_ratio = "60%-70%" if is_pdd else "45%-55%"
    hero_label_count = "2-3 个" if is_pdd else "2-4 个"

    lines = [
        "【店铺主图点击率策略】",
        "- 主图核心公式：产品大 + 卖点狠 + 证据短 + 视觉亮 + 信息少。",
        "- 主图任务是在电商货架中抢点击；每张图只传递一个主要信息，不能像详情页一样完整讲解。",
        "- 5 张主图必须分工清晰：首图抢点击，成分图讲配方亮点，效果图证明收益，场景图建立代入感。",
        "- 避免多张主图都变成「产品居中 + 环绕文字 + 柔和背景」的同质化模板。",
    ]

    if module_id in {"main_hero_selling_point", "campaign_hero_selling_point"}:
        lines.extend(
            [
                "- 首图必须让用户 0.3 秒内知道核心卖点，画面目标不是文艺氛围，而是货架点击力。",
                f"- 产品占画面 {hero_product_ratio}，作为最抢眼主体；包装反光、轮廓光、体积感要清晰。",
                f"- 一个大标题打核心卖点，标题短、狠、直接；搭配 {hero_label_count}小标签补充利益点。",
                "- 背景要饱满，有商业摄影光影，不要大面积空白；只追求好看但看不出卖什么属于失败。",
            ]
        )
    elif module_id in {"main_ingredient", "campaign_ingredient"}:
        lines.extend(
            [
                "- 次图-成分不是详情页成分页，不能讲太细，只负责快速展示配方亮点。",
                "- 主视觉是核心成分微距和原料质感，不是产品大图；产品可缩小放角落辅助。",
                "- 最多展示 2-3 个核心成分，每个成分只写一句作用短标签。",
                "- 禁止完整成分表、效果数据百分比、使用步骤、人物使用场景和药品疗效表达。",
            ]
        )
    elif module_id in {"main_effect", "campaign_effect"}:
        lines.extend(
            [
                "- 次图-效果必须让用户看到使用收益和结果感。",
                "- 使用局部前后对比，面积建议占画面 25%-35%；对比区域不能占满整张图，必须同时出现产品和标题。",
                "- 有真实数据时放大数字；没有真实数据时使用体验型表达，不能编造百分比。",
                "- 禁止只有漂亮脸，没有变化证据；禁止医疗治疗式前后对比和夸张换脸效果。",
            ]
        )
    elif module_id in {"main_usage_scene", "campaign_usage_scene"}:
        lines.extend(
            [
                "- 次图-使用场景负责建立代入感，让用户想象自己在什么场景下会用这个产品。",
                "- 可表达晨间上妆前、换季干燥时、熬夜后护理、妆前打底更服帖等使用时机。",
                "- 场景真实自然，产品必须清楚出现；禁止人物遮挡产品、凌乱居家背景和随意自拍感。",
            ]
        )

    return "\n".join(lines)


def _platform_main_image_rules(module: dict[str, Any], platform_id: str | None) -> str:
    if not _is_pdd_platform(platform_id):
        return ""

    module_id = str(module.get("id"))
    lines = [
        "【拼多多主图强转化策略】",
        "- 当前目标平台：拼多多；画面按拼多多高点击货架图处理，低认知成本、高识别度、高点击转化。",
        "- 信息顺序：先看清产品和最大卖点，再看证据、优惠或利益标签，最后才是背景氛围。",
        "- 视觉要更直接、更饱满、更近景；避免高级氛围压过商品识别或卖点识别。",
    ]
    if module_id in {"main_white_bg", "campaign_white_bg"}:
        lines.extend(
            [
                "- 白底图产品尽量放大到画面 70%-85%，完整清晰、不裁切、不改包装。",
                "- 除产品本体和极克制角标外，不加入任何降低审核通过率的装饰。",
            ]
        )
    elif module_id in {"main_hero_selling_point", "campaign_hero_selling_point"}:
        lines.extend(
            [
                "- 首图产品占画面 60%-70%，商品主体要比通用平台更大，允许近景压迫感和轻微越界感，但不能裁掉包装关键信息。",
                "- 核心卖点使用大字块或高对比标签，文案短、硬、第一眼能懂；辅助标签控制在 2-3 个。",
                "- 背景、道具和光效只服务产品放大与卖点强化，不能做成只好看但不转化的氛围图。",
            ]
        )
    elif module_id in {"main_ingredient", "campaign_ingredient"}:
        lines.append("- 成分图保持原料微距为主，但产品角落必须清晰可识别，成分标签短促直给，不做长科普。")
    elif module_id in {"main_effect", "campaign_effect"}:
        lines.append("- 效果图突出变化证据和数字标签，产品必须同时出现；数字、标题和产品三者都要一眼可读。")
    elif module_id in {"main_usage_scene", "campaign_usage_scene"}:
        lines.append("- 使用场景图必须让产品清楚露出，场景服务购买代入，不让人物或道具压过商品。")
    return "\n".join(lines)


def _campaign_promotion_guardrails(module: dict[str, Any]) -> str:
    module_id = str(module.get("id"))
    if not module_id.startswith("campaign"):
        return ""
    return "\n".join(
        [
            "【活动主图促销约束】",
            "- 产品仍然是主体，促销元素不能压过产品。",
            "- 促销信息必须来自用户填写内容；不能编造价格、折扣、日期、赠品或满减门槛。",
            "- 促销标签建议控制在 1-3 个，可以使用优惠券样式标签、限时角标、买赠标签、满减标签或活动色块。",
            "- 活动氛围可以更强，但画面不能变成促销贴纸堆叠，也不能遮挡产品包装和核心卖点。",
        ]
    )


def _detail_product_visibility_rules(module: dict[str, Any]) -> str:
    module_id = str(module.get("id"))
    policies = {
        "hero": "产品露出策略：必须出现产品",
        "effect_comparison": "产品露出策略：产品只能辅助出现",
        "competitor_comparison": "产品露出策略：产品只能辅助出现",
        "product_showcase": "产品露出策略：必须出现产品",
        "ingredient_overview": "产品露出策略：产品可不出现，成分体系是主视觉。",
        "usage": "产品露出策略：必须出现产品",
        "brand_qualification": "产品露出策略：不要出现产品瓶身、包装、商品主图或产品陈列",
        "research_strength": "产品露出策略：不要出现产品瓶身、包装、商品主图或产品陈列",
        "pain_scene": "产品露出策略：不要出现产品瓶身、包装、商品主图或产品陈列",
        "product_info": "产品露出策略：不要出现产品瓶身、包装、商品主图或产品陈列",
    }
    policy = policies.get(module_id)
    if not policy:
        return ""
    return f"- {policy}"


def _detail_conversion_rules(module: dict[str, Any], prompt_branch: str | None = None) -> str:
    module_id = str(module.get("id"))
    optimized = _is_prompt_optimization_branch(prompt_branch)
    lines = [
        "【详情页销售型生成策略】",
        "- 当前详情页结构不变，但每个模块必须从说明型图片升级为销售型图片。",
        "- 每张图必须有一个视觉矛盾，例如问题 vs 解决、普通 vs 专业、使用前 vs 使用后、单一护理 vs 成分体系。",
        "- 每张图生成前都要明确页面任务、主视觉、用户看完要相信什么，以及禁止混入哪些其他模块内容。",
    ]

    module_rules = {
        "hero": [
            "- 详情首图任务是让用户第一眼知道产品解决什么问题，并愿意继续往下看。",
            "- 产品作为主视觉，占画面 35%-50%；主标题短、狠、直接，只打一个核心卖点。",
            "- 搭配 2-4 个卖点标签，背景使用商业摄影光影；不要做成只有品牌氛围的海报。",
        ],
        "brand_qualification": [
            "- 品牌与资质背书页任务是建立品牌可信度和来源感，不讲研发实验细节。",
            "- 主视觉参考示例图的法式建筑、品牌门店、街景橱窗、产地来源和认证小标识。",
            "- 用户上传资料和手写信息优先；AI 只在资料缺失时做安全泛化补充，不能编造真实机构、授权编号或门店地址。",
        ],
        "research_strength": [
            "- 研发实力页任务是证明研发流程、真人测试和科学配方依据；不编造真实机构或编号。",
        ],
        "authority": [
            "- 权威页任务是建立信任感；主视觉使用实验室、研究员、仪器、试管、检测台和研发记录。",
            "- 报告、证书、文件只能作为局部辅助物件；不能编造真实机构、专利数量、临床数据或检测编号。",
            (
                "- 光影使用冷白、柔灰、银色金属反光和玻璃反射，避免夸张蓝色科技光、红色大屏和医院广告感。"
                if optimized
                else "- 光影使用冷白、银色金属反光、蓝色科技光或少量红色数据屏，避免医院广告感。"
            ),
        ],
        "pain_scene": [
            "- 痛点页任务是让用户产生强烈代入感，觉得这就是我的问题。",
            (
                "- 人物可以有轻微困扰表情，可出现皱眉、照镜子、摸脸、上妆卡粉等动作，但不要崩溃、哭泣或丑化。"
                if optimized
                else "- 人物要有困扰表情，可出现皱眉、照镜子、摸脸、上妆卡粉等动作。"
            ),
            "- 痛点必须可视化，例如卡粉起皮、干到发紧、粗糙、紧绷、暗沉、泛红。",
            (
                "- 可增加局部放大镜、肌肤纹理特写或问题区域标注；标注用细线和低饱和强调色，不做红色警示贴纸。"
                if optimized
                else "- 增加局部放大镜、肌肤纹理特写或问题区域标注，并使用红色警示标签点名问题。"
            ),
            (
                "- 背景用镜前、梳妆台、浴室等问题现场，画面要有真实痛点但保持干净高级，不贩卖焦虑。"
                if optimized
                else "- 背景用镜前、梳妆台、浴室等问题现场，不要做成漂亮但无痛感的护肤氛围照。"
            ),
        ],
        "effect_comparison": [
            "- 效果页任务是让用户看到变化，并相信产品有使用收益。",
            "- 必须出现使用前/使用后局部对比，画面同时包含产品、标题、局部对比卡片和功效说明或数据标签。",
            "- 真实数据放大数字；无真实数据用具体示意百分比数字，不冒充测试。",
        ],
        "competitor_comparison": [
            "- 竞品对比页任务是让用户知道为什么选择本产品，而不是普通同类产品。",
            "- 左侧视觉偏灰、暗、干、粗糙，展示普通同类产品的常见不足。",
            "- 右侧视觉偏亮、润、干净，展示本产品的差异化优势。",
            "- 不指名真实竞品品牌，不恶意攻击竞品；对比维度控制在 3-5 个。",
        ],
        "product_showcase": [
            "- 产品大图强化页任务是再次把注意力拉回产品本身，强化功效、质地和温和安全感。",
            "- 画面必须是产品大图 + 功效 + 质地 + 0添加，不讲品牌门店、研发报告、竞品或使用步骤。",
            "- 产品瓶身作为最大主视觉，旁边用质地液体和 0 酒精、0 色素、0 添加图标承接卖点。",
        ],
        "ingredient_overview": [
            "- 成分总览只做体系介绍，不展开单个成分的长篇解释。",
            "- 最多展示 3 个核心成分，每个成分对应一个护理方向，例如补水 + 修护 + 舒缓。",
            "- 主视觉可使用成分浮岛、胶囊卡、分子线、精华液流动和微距原料。",
            "- 禁止完整成分表、长篇科普、多个成分作用混在一起和药品疗效表达。",
        ],
        "usage": [
            "- 使用方法页任务是降低使用门槛，让用户觉得简单、清楚、容易执行。",
            "- 控制在 3-4 步，每一步配真实动作，例如取量、点涂、推开、按摩吸收。",
            "- 场景使用干净浴室、梳妆台、自然窗光；产品必须清楚出现。",
        ],
        "product_info": [
            "- 产品信息页任务是收口，把产品名称、功效、规格、保质期、产地、成分和使用说明整理成正式说明书。",
            "- 版式参考示例图的米色纸质背景、参数分组、清晰横线和说明书式排版，图片元素少，文字信息完整。",
            "- 用户上传资料和手写信息优先；缺失字段只做安全泛化，不编造产地、保质期、真实备案或检测编号。",
        ],
    }
    if module_id.startswith("ingredient_") and module_id != "ingredient_overview":
        module_rules[module_id] = [
            "- 单成分页任务是逐个讲清楚单个成分为什么有用。",
            "- 一张图只出现一个成分，一个成分只对应一个主要作用。",
            "- 不出现其他成分名称，不出现完整成分表，不出现效果数据，不出现使用步骤。",
            "- 画面结构为成分名 + 一句消费者能理解的作用 + 对应痛点 + 成分微距或机制视觉。",
        ]

    lines.extend(module_rules.get(module_id, []))
    return "\n".join(lines)


LANGUAGE_LABELS = {
    "zh-CN": "中文",
    "en": "English",
    "th": "Thai",
    "ms": "Malay",
    "vi": "Tiếng Việt",
}


def _language_rules(target_language: str | None) -> str:
    if not target_language:
        return ""
    language = LANGUAGE_LABELS.get(str(target_language), str(target_language))
    return "\n".join(
        [
            "【图片语言】",
            f"- 本张图的目标语言是 {language}。",
            f"- 所有可见标题、标签、数字说明和角标文字都必须直接生成在图片里，并且必须使用 {language}。",
            "- 不要把中文、英文、泰语、马来语或越南语混排；除产品包装本身已有文字外，营销文案只使用目标语言。",
            "- 文字需要像真实电商设计一样融入画面：有清晰层级、合理留白、自然光影或底纹承托，不要像后期贴上去的字幕。",
        ]
    )


def _module_requirements(
    module: dict[str, Any],
    product_info: dict[str, Any] | None,
    platform_id: str | None = None,
    prompt_branch: str | None = None,
) -> str:
    module_id = module.get("id")
    info = product_info or {}
    is_pdd = _is_pdd_platform(platform_id)
    optimized = _is_prompt_optimization_branch(prompt_branch)
    authority_report = _format_authority_assets(info.get("authority_assets"))
    effect_report = _format_effect_claims(info.get("effect_claims"))
    ingredients_report = _format_ingredients(info.get("ingredients"))
    selected_ingredients = _selected_ingredients(info.get("ingredients"))
    selected_ingredients_report = _format_ingredient_items(selected_ingredients)

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
            (
                "背景：按拼多多高点击货架图处理，品牌色背景更饱满，但仍保持低饱和和清晰商品识别。"
                if is_pdd
                else (
                    "背景：暖白、象牙白、浅米色、柔灰或浅石材色，可加入一个低饱和品牌强调色；保留自然的大留白或低纹理文案区。"
                    if optimized
                    else "背景：使用品牌主色系的渐变铺满整个画面，避免大面积空白或纯白；可用径向渐变、光晕、深→浅过渡、体积感环境光、流动丝绸质感或水波纹焦散营造高级氛围。"
                )
            ),
            (
                "产品：作为最大视觉主体放在石材、磨砂亚克力、水面或镜面陈列台上，用空间透视、微投影和克制倒影增强立体感；包装细节必须清楚。"
                if optimized
                else "产品：作为最大视觉主体居中展示，放置在水面、石材或亚克力镜面的质感陈列台上，用空间透视、微投影和微倒影增强立体感；产品不能孤零零放在空白上。"
            ),
            (
                "光影：使用柔和棚拍光、真实接触阴影、克制高光和轻微反射，避免硬阴影、廉价发光和过度眩光。"
                if optimized
                else "光影：使用商业香水/护肤品级布光，主光柔和、强轮廓边缘光清晰，瓶身边缘从背景中跃出。"
            ),
            (
                "品类质感元素：根据产品品类和风格自然加入 1-2 个质感装饰（如水珠、植物影子、精华液滴、丝绸纹理），增加画面层次但不能抢过产品。"
                if optimized
                else "品类质感元素：根据产品品类和风格，在产品周围自然散布 2-4 个质感装饰（如水珠、植物叶片、精华液滴、丝绸纹理、光泽粒子），装饰元素控制在 2-4 个，增加画面丰富度但不能抢过产品。"
            ),
            "文字层级：主标题用核心卖点（字号大、醒目、放在视觉焦点区域），副标题用品类或功效关键词（字号小、作为辅助信息）。文字要有透视感或阴影，不能像贴纸一样平贴在画面上。",
            (
                "整体目标：像高端护肤品牌首图一样，清晰、高级、可信，同时具备货架点击力；不是廉价促销海报。"
                if optimized
                else "装饰光效：可添加光斑 bokeh、微粒漂浮、柔光光晕等元素，增加高级感和画面呼吸感。"
            ),
            (
                ""
                if optimized
                else "整体目标：像高点击货架爆款护肤品首图一样——饱满、直接、有冲击力，不是简约留白风。"
            ),
        ],
        "main_ingredient": [
            "画面只呈现成分次图，突出核心成分、原料质感和成分标签。",
            "镜头语言：使用极浅景深超微距摄影，原料边缘清晰、背景柔化，形成昂贵的商业成分大片感。",
            "材质质感：原料与液滴要晶莹剔透，带晨露质感、发光精华液滴和清透高调色彩，避免脏、浑、暗的植物堆叠。",
            "必须参考以下成分信息，选择 2-3 个重点成分呈现：",
            ingredients_report,
            "文案必须像可直接用于店铺上架的成品成分图，只写成分名、正向作用标签和短标题。",
            "如果成分资料较少，就减少卡片数量，用原料质感补足画面，不写信息缺失提示。",
            "成分作用表达要谨慎，不能写成药品疗效或治疗承诺。",
        ],
        "main_effect": [
            "画面只呈现效果次图，突出核心功效、使用收益和可信的效果表达。",
            "数据区域：采用未来科技感玻璃拟态卡片、极简几何细线、克制进度环或细线图表，避免枯燥 PPT 数据板。",
            "肌肤区域：如出现肌肤，使用顶级美妆摄影光影，肌肤可以无暇但必须保留真实毛孔、自然纹理和可信明暗变化，让画面表达变美体验而不是医疗治疗。",
            "优先参考以下效果数据；如果数据不完整，画面用体验型视觉和进度条表达：",
            effect_report,
            "避免绝对化承诺，不写治愈、根治、永久有效，不制造夸张前后对比。",
        ],
        "main_usage_scene": [
            "画面呈现使用场景次图，突出真实使用动作、目标人群体验和生活方式护理情绪。",
            "环境：使用极简奢华浴室或梳妆台一角，台面干净、材质高级，可出现镜面、石材、亚克力、干净毛巾或少量护肤道具。",
            "光照：使用透过纱帘或百叶窗的柔和自然窗光，可有丁达尔光晕和轻微 bokeh，营造慵懒高级的护肤情绪。",
            "人物：优先使用优雅手部姿态、滴管动作、轻拍或涂抹局部，弱化面部特征，避免凌乱居家背景和随意自拍感。",
            "产品必须清晰嵌入场景，不能被人物或道具遮挡。",
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
            (
                "背景：使用低饱和品牌色和活动色做层次，避免强饱和红黄蓝、廉价金色渐变和满屏贴纸；保留可承载活动文案的干净区域。"
                if optimized
                else "背景：使用带活动感的品牌色渐变铺满画面，可叠加节日/促销氛围光效、体积感环境光或水波纹焦散，避免大面积空白或纯白。"
            ),
            (
                "产品：作为最大视觉主体展示，放置在石材、亚克力或镜面陈列台上，用柔和光影和微投影/倒影增强立体感；必须压过活动装饰。"
                if optimized
                else "产品：作为最大视觉主体居中展示，放置在水面、石材或亚克力镜面的质感陈列台上，用空间透视、柔和光影和微投影/倒影增强立体感；必须压过活动装饰。"
            ),
            (
                "光影：使用商业护肤品级柔光、真实接触阴影和克制高光，活动光效只能作为辅助。"
                if optimized
                else "光影：使用商业香水/护肤品级布光，主光柔和、强轮廓边缘光清晰，活动光效只能作为辅助。"
            ),
            (
                "品类质感元素：根据产品品类在产品周围加入 1-2 个质感装饰（水珠、叶片、精华液滴等），增加画面丰富度但不堆元素。"
                if optimized
                else "品类质感元素：根据产品品类在产品周围散布 2-4 个质感装饰（水珠、叶片、精华液滴等），装饰元素控制在 2-4 个，增加画面丰富度。"
            ),
            "文字层级：主标题用核心卖点（字号大），副标题放促销利益点（优惠券、限时角标、满减标签），层级分明不混乱。",
            "促销表达需来自用户填写的活动信息，可使用优惠券、限时角标、满减标签、折扣贴纸等电商活动元素。",
            (
                "整体目标：像高点击电商大促护肤首图，但视觉仍克制、高级、可信，不做廉价促销贴纸堆叠。"
                if optimized
                else "装饰光效：可添加光斑、微粒、活动礼花等元素增加节日感。"
            ),
            (
                ""
                if optimized
                else "整体目标：像高点击电商大促护肤首图——饱满、有冲击力、有促销紧迫感。"
            ),
        ],
        "campaign_ingredient": [
            "画面呈现活动成分次图，展示核心成分与原料质感，同时加入活动氛围元素。",
            "镜头语言：使用极浅景深超微距摄影，原料边缘清晰、背景柔化，形成昂贵的商业成分大片感。",
            "材质质感：原料与液滴要晶莹剔透，带晨露质感、发光精华液滴和清透高调色彩；活动元素只做轻量角标。",
            "必须参考以下成分信息，选择 2-3 个重点成分呈现：",
            ingredients_report,
            "文案必须像可直接用于店铺上架的成品成分图，只写成分名、正向作用标签和短标题。",
            "如果成分资料较少，就减少卡片数量，用原料质感补足画面，不写信息缺失提示。",
            "促销元素作为辅助转化信息出现，不能压过成分可信表达，也不能写成药品疗效。",
        ],
        "campaign_effect": [
            "画面呈现活动效果次图，突出核心功效、使用收益和促销转化理由。",
            "数据区域：采用未来科技感玻璃拟态卡片、极简几何细线、克制进度环或细线图表，促销标签不能压过效果表达。",
            "肌肤区域：如出现肌肤，使用顶级美妆摄影光影，肌肤可以无暇但必须保留真实毛孔、自然纹理和可信明暗变化。",
            "优先参考以下效果数据；如果数据不完整，画面用体验型视觉和进度条表达：",
            effect_report,
            "可加入限时优惠、活动权益、购买利益点，但不能夸大效果或制造绝对承诺。",
        ],
        "campaign_usage_scene": [
            "画面呈现活动使用场景次图，结合目标人群、使用环境和活动购买氛围。",
            "环境：使用极简奢华浴室或梳妆台一角，台面干净、材质高级，可加入礼盒、优惠券或活动标签氛围。",
            "光照：使用透过纱帘或百叶窗的柔和自然窗光，可有丁达尔光晕和轻微 bokeh。",
            "人物：优先使用优雅手部姿态、滴管动作、轻拍或涂抹局部，弱化面部特征，避免凌乱居家背景和随意自拍感。",
            "可以加入礼盒、活动氛围、优惠券、限时购标签等元素，产品必须清晰可见。",
            "场景需围绕目标人群与使用方法展开，不编造用户未填写的具体价格、折扣或活动日期。",
        ],
        "hero": [
            "这是详情页首图——用户点进详情后看到的第一张沉浸式大图，宽高比偏纵向（不是 1:1），需要更大的氛围空间和更完整的信息承载。",
            "用产品大图作为视觉中心，放在质感陈列台上，用空间透视、商业香水/护肤品级布光、强轮廓边缘光、体积感环境光和克制倒影建立沉浸式品牌空间。",
            "突出产品名称、品类、规格和 2-3 个核心卖点；装饰元素控制在 2-4 个，留出高级负空间。",
            "与货架主图的差异：详情首图可以有更丰富的背景层次、更多文案信息和更强的品牌氛围感，不需要像主图那样在 0.3 秒抓注意力。",
            "不要塞入权威报告、效果对比表或使用步骤，这些属于其他模块。",
        ],
        "brand_qualification": [
            "画面只呈现品牌与资质背书，视觉重点是品牌背景、产地来源和权威认证，不进入研发实验室。",
            f"资料优先级：{_user_priority_note()}",
            "主体画面参考示例：法式建筑立面、品牌门店、街景橱窗、柜台陈列、官方旗舰店正品保障图标，形成真实品牌来源感。",
            "必须参考以下品牌/资质资料，但不要把原文完整搬进画面：",
            _format_brand_assets(info),
            "文字只保留品牌背景、源自某地、官方渠道、正品保障、权威认证等短标签；没有明确地名时用泛化产地来源，不编造具体地址或机构。",
            "版式建议：大标题为品牌背景与权威认证，主体是建筑/门店/橱窗照片感，下方 3-4 个小型认证或保障标识。",
            "禁止出现科学家实验画面为主体、显微镜、试管、烧瓶、真人测试、效果对比或完整成分表。",
        ],
        "research_strength": [
            "画面只呈现研发实力，科学家实验画面为主体：研究员在真实实验室中操作显微镜、滴管、试管、烧瓶或样本瓶。",
            f"资料优先级：{_user_priority_note()}",
            "色调与环境：冷峻克制的高科技蓝色/银色调，极度整洁的现代研发中心，不像医院或廉价摆拍实验室。",
            "玻璃器皿的锐利高光、精密仪器金属质感和克制实验室光线要真实可信。",
            "非对称高级画册构图：研发流程小图、真人测试画面、科学配方、纸质资质和仪器形成前中后景。",
            "纸质资质只占画面局部，不超过画面 25%；不要让纸质资质成为主视觉；纸张纤维和折痕要真实。",
            "文字必须小且虚化/泛化，不写具体报告编号、样本编号、机构编号或可核验编号。",
            "可见中文只用信任短词：安心品质、真实保障、成分可信、品控流程、使用放心。",
            "不要半透明 UI 卡片、悬浮数据面板、玻璃拟态卡片或电子屏幕式报告。",
            "参考以下权威资料方向，但不要把完整原文搬到画面上：",
            authority_report,
            "禁止出现品牌门店、法式街景、产地来源橱窗、竞品对比或产品大图海报。",
        ],
        "authority": [
            "画面只呈现权威资质展示，科学家实验画面为主体：研究员在明亮真实实验室中操作显微镜、滴管、试管或样本瓶。",
            "色调与环境：冷峻克制的高科技蓝色/银色调，极度整洁的现代研发中心，不像医院或廉价摆拍实验室。",
            "实验动作占主要视觉面积；实验台、玻璃器皿的锐利高光、精密仪器金属质感和克制实验室光线要真实可信。",
            "构图采用非对称高级画册构图，主体实验动作、纸质资质和仪器形成前中后景。",
            "纸质资质只占画面局部，不超过画面 25%，放在桌角、前景或研究员手边；不要让纸质资质成为主视觉。",
            "局部纸质资质需有纸张纤维、轻微折痕、装订线或文件夹边缘；可搭配印章轮廓、图表形状和证书边框。",
            "文字必须小且虚化/泛化，不写具体报告编号、样本编号、机构编号或可核验编号。",
            "可见中文只用信任短词：安心品质、真实保障、成分可信、品控流程、使用放心。",
            "不要出现内部提示词、抽象模块命名或生硬标题；不要半透明 UI 卡片、悬浮数据面板、玻璃拟态卡片或电子屏幕式报告。",
            "必须参考以下权威资料方向，但不要把完整原文搬到画面上：",
            authority_report,
            "版式建议：科学家实验室研究场景 + 画面一角局部纸质资质 + 简洁模块标题；不做底部说明区或风险提示类文字。",
        ],
        "pain_scene": [
            "画面只呈现目标人群的护肤痛点场景，突出皮肤困扰、情绪压力和已经尝试无效的经历。",
            "痛点表达优先使用情绪化电影灯光、冷色调或暗调背景、人物神态和环境隐喻痛点，不要把脸画丑，也不要生成红肿、破损或令人不适的皮肤特写。",
            "环境隐喻痛点：可用干燥开裂纹理隐喻缺水，用暗淡灯光隐喻肤色暗沉，用镜前犹豫或梳妆台冷光表现护理烦恼。",
            "必须参考以下目标人群来构建痛点场景：",
            _numbered_lines(_string_items(info.get("target_users")), "日常护肤人群"),
            "产品解决方向来自以下核心功效：",
            _numbered_lines(_string_items(info.get("functions")), "补水保湿"),
            "痛点要真实可信，不要夸大或编造极端皮肤问题。",
            "不要提前展示效果数据或权威报告，这些属于后续模块。",
        ],
        "effect_comparison": [
            "画面只呈现效果对比，必须像小报告一样写清楚每条效果数据。",
            "数据区域：采用未来科技感玻璃拟态卡片、极简几何细线、克制进度环或细线图表，避免枯燥 PPT 数据板。",
            "肌肤区域：如出现肌肤，使用顶级美妆摄影光影，肌肤可以无暇但必须保留真实毛孔、自然纹理和可信明暗变化，让效果看起来是变美体验而不是医疗治疗。",
            "必须完整带入以下效果数据：",
            effect_report,
            "数据不完整也用具体示意百分比数字+体验型视觉；避免绝对化医疗表达，不写治愈、根治、永久有效。",
        ],
        "competitor_comparison": [
            "画面只呈现竞品对比模块，展示本产品与普通同类产品的差异化优势，不能指名真实竞品品牌。",
            "对比维度按以下参考：质地、成分思路、效果、负面体验、使用体验和适合人群。",
            "必须参考以下产品信息来构建本产品的对比优势：",
            "核心卖点：" + _numbered_lines(_string_items(info.get("core_selling_points")), "温和护理"),
            "核心功效：" + _numbered_lines(_string_items(info.get("functions")), "补水保湿"),
            "左栏展示「普通同类产品」的常见痛点或不足，右栏展示本产品的差异化优势和卖点。",
        ],
        "product_showcase": [
            "画面只呈现产品大图强化，核心结构是产品大图 + 功效 + 质地 + 0添加。",
            "产品瓶身作为最大主视觉，使用商业护肤品棚拍光、强轮廓光、微倒影和高级陈列台，包装细节清楚。",
            "围绕产品展示质地液体，例如清透精华水、乳液延展、啫喱质感、水润液滴或流动质地，不做实验室报告。",
            "必须参考以下卖点和资料亮点：",
            "核心卖点：" + _numbered_lines(_string_items(info.get("core_selling_points")), "温和护理"),
            "核心功效：" + _numbered_lines(_string_items(info.get("functions")), "补水保湿"),
            "资料亮点：" + _numbered_lines(_string_items(info.get("material_highlights")), "质地清透，配方温和"),
            "可见图标可使用 0 酒精、0 色素、0 香精、0 添加图标等温和安全感表达；只有资料没有明确 0 添加时，用泛化温和配方图标，不编造绝对承诺。",
            "禁止品牌门店、研发实验室、痛点人脸、竞品表格、完整成分表和使用步骤。",
        ],
        "ingredient_overview": [
            "画面只呈现成分体系总览，先说明产品用了什么核心配方思路，不再拆成后续单成分讲解图。",
            "镜头语言：使用极浅景深超微距摄影，原料边缘清晰、背景柔化，形成昂贵的商业成分大片感。",
            "材质质感：原料与液滴要晶莹剔透，带晨露质感、发光精华液滴和清透高调色彩，避免脏、浑、暗的植物堆叠。",
            "本图最多展示以下 3 个核心成分，不展示完整成分表，也不要把其他成分挤进画面：",
            selected_ingredients_report,
            "可见文案应总结为多重成分复配体系，例如：核心成分协同护理、多重成分复配体系、层层水润舒缓。",
            "每个成分只做极短标签，不在总览图展开长篇作用解释。",
            "成分作用表达要谨慎，不能写成药品疗效或治疗承诺。",
        ],
        **{
            f"ingredient_{index}": [
                "画面只呈现单成分讲解图，只讲 1 个核心成分，不能把其他成分名称、作用或卡片带入画面。",
                "后续单成分讲解图会分别讲解其他核心成分，本图不要提前出现它们。",
                f"成分序号：{index}",
                f"成分名称：{ingredient['name']}",
                f"消费者可理解作用：{ingredient['benefit']}",
                f"建议视觉方向：{_ingredient_visual_direction(ingredient)}",
                "镜头语言：使用极浅景深超微距摄影，让该成分对应的原料、液滴、精华质地或抽象质感成为唯一主视觉。",
                "文案必须像可直接用于店铺上架的成品成分图，只写成分名、正向作用短标签和一句短标题。",
                "图片模型不得自行扩展新的功效，不得编造治疗、修复疾病、医学改善或绝对化承诺。",
                "如果该成分来自 AI 谨慎补全，仍然只用温和护理表达，不出现补全痕迹、占位提示或资料不足提示。",
            ]
            for index, ingredient in enumerate(selected_ingredients, start=1)
        },
        "usage": [
            "画面只呈现使用方法，用清晰步骤展示用量、顺序、手法和使用频率。",
            "环境：使用极简奢华浴室或梳妆台一角，台面干净、材质高级，避免凌乱居家背景。",
            "光照：使用透过纱帘或百叶窗的柔和自然窗光，可有丁达尔光晕和轻微 bokeh。",
            "人物：优先使用优雅手部姿态、滴管动作、轻拍或涂抹局部，弱化面部特征。",
            "必须参考以下使用步骤：",
            _numbered_lines(_string_items(info.get("usage_method")), "洁面后取适量涂抹"),
            "可以搭配手部涂抹、滴管、面部轻拍等示意画面。",
        ],
        "product_info": [
            "画面只呈现产品信息，作为详情页最后一屏收口，不做功效海报。",
            f"资料优先级：{_user_priority_note()}",
            "版式：米色纸质背景、正式说明书质感、清晰横线、分组参数表和少量说明文字，图片元素很少。",
            "必须整理产品名称、功效、规格、保质期、产地、成分、使用说明等信息；没有资料的字段可省略或用泛化安全表达。",
            "必须参考以下产品参数和资料：",
            _format_product_detail_items(info),
            "不能编造产地、保质期、备案编号、检测编号、真实机构名、药品疗效或绝对化功效承诺。",
        ],
    }
    return "\n".join(requirements.get(str(module_id), [f"画面只呈现当前模块内容：{_text(module.get('description'))}"]))


def _module_style_usage_key(module: dict[str, Any]) -> str:
    module_id = str(module.get("id", ""))
    module_name = _text(module.get("name"), "")
    if module_id.startswith("campaign") or "活动" in module_name:
        return "活动图"
    if "ingredient" in module_id or "成分" in module_name:
        return "成分图"
    if "effect" in module_id or "效果" in module_name:
        return "效果图"
    if "usage" in module_id or "使用" in module_name:
        return "使用场景"
    return "首图"


def _module_style_usage(style: dict[str, Any], module: dict[str, Any]) -> str:
    usage = style.get("module_usage")
    if not isinstance(usage, dict):
        return ""
    candidates = [_text(module.get("name"), ""), _module_style_usage_key(module), "首图"]
    for candidate in candidates:
        value = str(usage.get(candidate, "")).strip()
        if value:
            return value
    return ""


def _structured_style_system_lines(style: dict[str, Any], module: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    theme = _text(style.get("theme"), "")
    if theme:
        lines.append(f"- 风格主题：{theme}")
    best_for = " / ".join(_string_items(style.get("best_for")))
    if best_for:
        lines.append(f"- 适用品类：{best_for}")
    visual_elements = " / ".join(_string_items(style.get("visual_elements")))
    if visual_elements:
        lines.append(f"- 主题元素库：{visual_elements}")
    materials = " / ".join(_string_items(style.get("materials")))
    if materials:
        lines.append(f"- 材质系统：{materials}")
    lighting = " / ".join(_string_items(style.get("lighting")))
    if lighting:
        lines.append(f"- 光影系统：{lighting}")
    module_usage = _module_style_usage(style, module)
    if module_usage:
        lines.append(f"- 当前模块风格用法：{module_usage}")
    forbidden = " / ".join(_string_items(style.get("forbidden")))
    if forbidden:
        lines.append(f"- 风格禁止项：{forbidden}")
    return lines


def _premium_skincare_style_lines() -> list[str]:
    return [
        "- 高级护肤商业摄影基线：premium skincare commercial photography / luxury editorial product photography；克制构图、大留白、真实接触阴影、低饱和暖白/柔灰/香槟色，材质道具控制在 1-2 个。",
        "- 图片模型优先负责产品摄影感、场景氛围、光影、材质、留白和构图；文案、价格、百分比、专利号和报告编号优先由后期图层叠加。",
        "- 通用负向：cheap Taobao poster style, crowded layout, garbled/random Chinese text, fake logo/certification/patent/data, oversaturated/neon/fire/gold coins/explosive sale stickers, distorted packaging, watermark.",
    ]


def build_module_image_prompt(
    *,
    product_info: dict[str, Any] | None,
    style: dict[str, Any],
    module: dict[str, Any],
    module_index: int,
    total_modules: int,
    promotion_info: str | None = None,
    has_style_reference: bool = False,
    text_layer_mode: bool = False,
    target_language: str | None = None,
    platform_id: str | None = None,
    prompt_branch: str | None = None,
) -> str:
    optimized_prompt_branch = _is_prompt_optimization_branch(prompt_branch)
    style_keywords = " / ".join(_string_items(style.get("keywords"))) or "高级 / 干净 / 统一"
    group = module.get("image_group")
    is_main_image = group in {"main", "campaign"}
    is_campaign_image = group == "campaign"
    reference_product_style_rule = (
        "- 中文电商视觉，高级干净统一；有参考图时保持产品外观。"
        if is_main_image
        else "- 参考图只定产品身份，出产品服从上方露出策略。"
    )
    module_kind = "中文电商活动主图" if is_campaign_image else "中文电商商品主图" if is_main_image else "中文商品详情页单模块图片"
    readable_text_rule = (
        "- 字体层级清楚，标题短促有力，说明文字清晰可读，不出现乱码、水印、品牌侵权标识。"
        if is_main_image
        else "- 仅短标题、极短标签、必要数值或步骤编号需要清晰可读；不要生成说明文字、段落脚注、资料建议或风险提示类文案，不出现乱码、水印、品牌侵权标识。"
    )
    rendered_text_rule = "- 分层文字模式下不要生成可读文字，最终文案会由程序后期叠加。" if text_layer_mode else readable_text_rule
    text_layer_rules = (
        "\n".join(
            [
                "【分层文字模式】",
                "- 这张图将由程序后期叠加中文、英文、泰语和马来语文字图层；图片模型只负责生成无文字底图。",
                "- 画面中不要出现任何可读文字、标题、标签、数字文案、乱码、水印、UI 字幕或装饰性字母。",
                "- 保留适合后期叠字的干净留白或低纹理区域，但这些区域不能像空白模板，要自然融入电商视觉。",
                "- 产品、背景、道具、人物、图表形状和氛围可以正常生成；只有文字内容必须留给后期程序绘制。",
            ]
        )
        if text_layer_mode
        else ""
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
                "- 1:1 电商货架主图；产品清晰、可点击率高、信息聚焦。",
                f"- 同套 {total_modules} 张主图共享材质、字体层级、光影、装饰和图标；每张可按模块变色。",
            ]
        )
        if is_campaign_image:
            structure_lines.append("- 必须加入促销、活动、优惠或购买利益点等营销元素，但不能遮挡产品主体。")
    else:
        structure_lines.extend(
            [
                "- 只生成当前模块，不能新增一级模块，不能把其他模块的内容混入当前画面。",
                "- 画面以核心视觉为主，可搭配短标题和少量视觉标签；不要做成带大段文字的说明板。",
                f"- 第 {module_index}/{total_modules} 张详情模块；材质、光影、标题层级、装饰和图标风格与首图一致，色彩可按模块变化。",
                "- 画面构图按竖向详情页模块比例，信息从上到下纵向排布。",
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
            reference_style_lines: list[str] = []
            if style.get("id") == "style_reference":
                reference_style_lines = [
                    f"- Gemini 对标风格名称：{_text(style.get('name'), '图片对标风格')}",
                    f"- Gemini 对标参考色：{_text(style.get('primary_color'), '根据对标图提取')}，只作为局部点缀和色彩关系参考。",
                    f"- Gemini 对标关键词：{style_keywords}",
                    f"- Gemini 对标视觉方向：{_text(style.get('visual_direction'), '')}",
                    f"- Gemini 对标版式方向：{_text(style.get('layout_guidance'), '')}",
                    *_structured_style_system_lines(style, module),
                ]
            style_section = [
                "【统一视觉风格】",
                *(_premium_skincare_style_lines() if optimized_prompt_branch else []),
                "- 上传的风格参考图优先：只参考排版、色调、光影和氛围，不改变产品外观、包装和品牌信息。",
                *reference_style_lines,
                "- 不要混入预设风格名称、主色或关键词；风格只以已上传的风格参考图为准。",
                reference_product_style_rule,
                rendered_text_rule,
                "- 可见文字像店铺上架成品图文案，不写信息缺失、核验提醒、补全提醒或半成品提示。",
                "- 效果、权威、成分表达谨慎，不使用医疗化、绝对化承诺。",
            ]
        else:
            style_section = [
                "【统一视觉风格】",
                *(_premium_skincare_style_lines() if optimized_prompt_branch else []),
                f"- 风格名称：{_text(style.get('name'), '太空修护风')}",
                f"- 风格参考色：{_text(style.get('primary_color'), '根据风格选择参考色')}，只作为局部点缀和 UI 兼容参考，不是整套图片的强制背景色或统一主色。",
                f"- 视觉关键词：{style_keywords}",
                *(
                    [
                        f"- AI 规划视觉方向：{_text(style.get('visual_direction'), '')}",
                        f"- AI 规划版式方向：{_text(style.get('layout_guidance'), '')}",
                    ]
                    if style.get("id") == "ai_custom"
                    else []
                ),
                *_structured_style_system_lines(style, module),
                "- 每张图可以根据模块内容使用不同主色、背景色或辅助色，但材质、光影、版式、字体层级、装饰元素和图标语言必须一致。",
                reference_product_style_rule,
                rendered_text_rule,
                "- 可见文字像店铺上架成品图文案，不写信息缺失、核验提醒、补全提醒或半成品提示。",
                "- 效果、权威、成分表达谨慎，不使用医疗化、绝对化承诺。",
            ]

    visual_constraints = _module_visual_constraints(module, platform_id=platform_id)
    main_image_conversion_rules = _main_image_conversion_rules(module, platform_id=platform_id) if is_main_image else ""
    platform_main_image_rules = _platform_main_image_rules(module, platform_id) if is_main_image else ""
    campaign_promotion_guardrails = _campaign_promotion_guardrails(module) if is_campaign_image else ""
    detail_product_visibility_rules = _detail_product_visibility_rules(module) if not is_main_image else ""
    detail_conversion_rules = _detail_conversion_rules(module, prompt_branch=prompt_branch) if not is_main_image else ""
    effect_layout_guardrails = _effect_comparison_layout_guardrails(module, product_info)
    people_realism_guardrails = _people_realism_guardrails(module)
    detail_text_guardrails = _detail_text_guardrails(module) if not is_main_image else ""
    language_rules = _language_rules(target_language)

    return "\n".join(
        [
            f"你是电商护肤{'商品主图' if is_main_image else '详情页'}视觉生成模型。请根据以下隐藏提示词生成 1 张{module_kind}。",
            *(["", "【提示词分支】", "当前分支：提示词优化分支"] if optimized_prompt_branch else []),
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
            _module_requirements(module, product_info, platform_id=platform_id, prompt_branch=prompt_branch),
            *(["", detail_product_visibility_rules] if detail_product_visibility_rules else []),
            *(["", visual_constraints] if visual_constraints else []),
            *(["", main_image_conversion_rules] if main_image_conversion_rules else []),
            *(["", platform_main_image_rules] if platform_main_image_rules else []),
            *(["", campaign_promotion_guardrails] if campaign_promotion_guardrails else []),
            *(["", detail_conversion_rules] if detail_conversion_rules else []),
            *(["", effect_layout_guardrails] if effect_layout_guardrails else []),
            *(["", people_realism_guardrails] if people_realism_guardrails else []),
            *(["", detail_text_guardrails] if detail_text_guardrails else []),
            *(["", language_rules] if language_rules else []),
            *(["", text_layer_rules] if text_layer_rules else []),
            "",
            *style_section,
        ]
    )
