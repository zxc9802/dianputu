from __future__ import annotations

import base64
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont


LANGUAGE_OPTIONS: dict[str, dict[str, str]] = {
    "zh-CN": {"label": "中文", "instruction": "简体中文"},
    "en": {"label": "English", "instruction": "natural concise ecommerce English"},
    "th": {"label": "ไทย", "instruction": "natural concise Thai for ecommerce"},
    "ms": {"label": "Malay", "instruction": "natural concise Bahasa Melayu for ecommerce"},
}

DEFAULT_LANGUAGE = "zh-CN"


def normalize_language(value: str | None) -> str:
    raw = (value or DEFAULT_LANGUAGE).strip()
    aliases = {
        "zh": "zh-CN",
        "zh_cn": "zh-CN",
        "zh-cn": "zh-CN",
        "cn": "zh-CN",
        "english": "en",
        "eng": "en",
        "thai": "th",
        "malay": "ms",
        "my": "ms",
        "ms-my": "ms",
    }
    normalized = aliases.get(raw.lower(), raw)
    return normalized if normalized in LANGUAGE_OPTIONS else DEFAULT_LANGUAGE


def language_label(language: str) -> str:
    return LANGUAGE_OPTIONS.get(normalize_language(language), LANGUAGE_OPTIONS[DEFAULT_LANGUAGE])["label"]


def _clean_text(value: Any, fallback: str = "") -> str:
    cleaned = str(value or "").strip()
    return cleaned or fallback


def _string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = " ".join(_clean_text(val) for val in item.values() if _clean_text(val))
            else:
                text = _clean_text(item)
            if text:
                items.append(text)
        return items
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in re.split(r"[/、,\n]", value) if item.strip()]
    return []


def _first(value: Any, fallback: str) -> str:
    return (_string_items(value) or [fallback])[0]


PLACEHOLDER_INGREDIENT_BENEFITS = (
    "待确认",
    "待说明",
    "待补充",
    "作用待确认",
    "功效待确认",
    "效果待确认",
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


def _safe_ingredient_benefit(name: str, benefit: str) -> str:
    return _ingredient_default_benefit(name) if _is_placeholder_ingredient_benefit(benefit) else benefit


def _ingredient_names(value: Any) -> list[str]:
    names: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = _clean_text(item.get("name"))
                benefit = _clean_text(item.get("benefit"))
                if name:
                    names.append(f"{name} {_safe_ingredient_benefit(name, benefit)}")
            elif _clean_text(item):
                name = _clean_text(item)
                names.append(f"{name} {_ingredient_default_benefit(name)}")
    return names[:3]


def _effect_claims(value: Any) -> list[str]:
    claims: list[str] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                claim = _clean_text(item.get("claim"))
                metric = _clean_text(item.get("value"))
                if claim and metric:
                    claims.append(f"{claim} {metric}")
                elif claim:
                    claims.append(claim)
            elif _clean_text(item):
                claims.append(_clean_text(item))
    return claims[:3]


def _layer(
    layer_id: str,
    role: str,
    text: str,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    font_size: float,
    color: str = "#17322A",
    align: str = "left",
    max_lines: int = 2,
    weight: str = "regular",
) -> dict[str, Any] | None:
    cleaned = _clean_text(text)
    if not cleaned:
        return None
    return {
        "id": layer_id,
        "role": role,
        "source_text": cleaned,
        "text": cleaned,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "font_size": font_size,
        "color": color,
        "align": align,
        "max_lines": max_lines,
        "weight": weight,
    }


def _main_layers(info: dict[str, Any], module_id: str, promotion_info: str | None) -> list[dict[str, Any]]:
    title = _first(info.get("core_selling_points"), _clean_text(info.get("product_name"), "核心卖点"))
    subtitle = " · ".join(_string_items(info.get("functions"))[:2]) or _clean_text(info.get("category"), "温和护理")
    if module_id.startswith("campaign_") and _clean_text(promotion_info):
        subtitle = _clean_text(promotion_info)

    layers = [
        _layer("title", "title", title, x=0.07, y=0.08, width=0.50, height=0.16, font_size=0.072, max_lines=2, weight="bold"),
        _layer("subtitle", "subtitle", subtitle, x=0.07, y=0.25, width=0.48, height=0.10, font_size=0.034, color="#31594D", max_lines=2),
    ]
    if module_id in {"main_ingredient", "campaign_ingredient"}:
        ingredient = (_ingredient_names(info.get("ingredients")) or ["核心成分"])[0]
        layers.append(_layer("tag1", "tag", ingredient, x=0.08, y=0.74, width=0.34, height=0.08, font_size=0.030, color="#1F6F52", max_lines=1, weight="bold"))
    if module_id in {"main_effect", "campaign_effect"}:
        effect = (_effect_claims(info.get("effect_claims")) or _string_items(info.get("functions")) or ["使用收益"])[0]
        layers.append(_layer("tag1", "tag", effect, x=0.08, y=0.74, width=0.42, height=0.08, font_size=0.030, color="#1F6F52", max_lines=1, weight="bold"))
    if module_id in {"main_usage_scene", "campaign_usage_scene"}:
        usage = (_string_items(info.get("usage_method")) or ["日常使用"])[0]
        layers.append(_layer("tag1", "tag", usage, x=0.08, y=0.74, width=0.42, height=0.08, font_size=0.030, color="#1F6F52", max_lines=1, weight="bold"))
    return [item for item in layers if item]


def _detail_layers(info: dict[str, Any], module_id: str) -> list[dict[str, Any]]:
    product_name = _clean_text(info.get("product_name"), "护肤产品")
    selling_points = _string_items(info.get("core_selling_points"))
    functions = _string_items(info.get("functions"))
    ingredients = _ingredient_names(info.get("ingredients"))
    effects = _effect_claims(info.get("effect_claims"))
    usage = _string_items(info.get("usage_method"))
    single_ingredient_match = re.fullmatch(r"ingredient_([123])", module_id)

    recipes: dict[str, tuple[str, str, list[str]]] = {
        "hero": (product_name, selling_points[0] if selling_points else _first(info.get("functions"), "核心护理"), selling_points[1:3] or functions[:2]),
        "authority": ("安心品质", "成分可信 · 品控流程", ["真实保障", "使用放心"]),
        "pain_scene": ("肌肤困扰", functions[0] if functions else "针对日常护理痛点", _string_items(info.get("target_users"))[:2]),
        "effect_comparison": ("效果看得见", effects[0] if effects else _first(info.get("functions"), "水润改善"), effects[1:3] or functions[:2]),
        "competitor_comparison": ("优势对比", selling_points[0] if selling_points else "本产品优势", ["普通同类", "本产品"]),
        "ingredient_overview": ("核心成分体系", "多重成分复配", ingredients[:3]),
        "usage": ("使用方法", usage[0] if usage else "洁面后使用", usage[1:3]),
    }
    if single_ingredient_match:
        ingredient_index = int(single_ingredient_match.group(1)) - 1
        ingredient = ingredients[ingredient_index] if ingredient_index < len(ingredients) else ["核心植萃", "保湿复配", "舒缓因子"][ingredient_index]
        title, subtitle, tags = ("核心成分", ingredient, [_clean_text(info.get("category"), "温和配方")])
    else:
        title, subtitle, tags = recipes.get(module_id, (_clean_text(info.get("category"), "商品详情"), _first(info.get("functions"), "核心卖点"), selling_points[:2]))
    layers = [
        _layer("title", "title", title, x=0.08, y=0.07, width=0.84, height=0.11, font_size=0.060, align="center", max_lines=2, weight="bold"),
        _layer("subtitle", "subtitle", subtitle, x=0.12, y=0.20, width=0.76, height=0.10, font_size=0.034, align="center", color="#31594D", max_lines=2),
    ]
    for index, tag in enumerate(tags[:3], start=1):
        layers.append(
            _layer(
                f"tag{index}",
                "tag",
                tag,
                x=0.14 + (index - 1) * 0.24,
                y=0.78,
                width=0.22,
                height=0.08,
                font_size=0.026,
                align="center",
                color="#1F6F52",
                max_lines=2,
                weight="bold",
            )
        )
    return [item for item in layers if item]


def build_text_layers(product_info: dict[str, Any] | None, module: dict[str, Any], promotion_info: str | None = None) -> list[dict[str, Any]]:
    info = product_info or {}
    module_id = str(module.get("id") or "")
    group = module.get("image_group") or "detail"
    if module_id in {"main_white_bg", "campaign_white_bg"}:
        return []
    if group in {"main", "campaign"}:
        return _main_layers(info, module_id, promotion_info)
    return _detail_layers(info, module_id)


def build_translation_messages(layers: list[dict[str, Any]], target_language: str) -> list[dict[str, Any]]:
    language = normalize_language(target_language)
    language_instruction = LANGUAGE_OPTIONS[language]["instruction"]
    source_items = [{"id": layer["id"], "text": _clean_text(layer.get("source_text") or layer.get("text"))} for layer in layers if _clean_text(layer.get("source_text") or layer.get("text"))]
    prompt = "\n".join(
        [
            "你是跨境电商图片文案翻译专家。请把图片中的短文案翻译为目标语言，并保持适合电商图片排版的短句。",
            f"目标语言：{language_instruction}",
            "要求：",
            "1. 只输出 JSON，不要解释。",
            "2. JSON 格式为 {\"items\":[{\"id\":\"...\",\"text\":\"...\"}]}。",
            "3. 保留原有 id；不要新增或删除项目。",
            "4. 翻译要自然、简短，优先适合图片标题和标签，不要写成长段句子。",
            "5. 不要夸大功效，不要新增医疗承诺、价格、折扣或未提供的信息。",
            f"待翻译 JSON：{json.dumps({'items': source_items}, ensure_ascii=False)}",
        ]
    )
    return [{"role": "user", "content": prompt}]


def apply_translated_text(layers: list[dict[str, Any]], raw: str) -> list[dict[str, Any]]:
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    data = json.loads(raw)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("translation response must contain items")
    by_id = {str(item.get("id")): _clean_text(item.get("text")) for item in items if isinstance(item, dict)}
    translated = []
    for layer in layers:
        text = by_id.get(str(layer.get("id"))) or _clean_text(layer.get("text"))
        translated.append({**layer, "text": text})
    return translated


def _hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    cleaned = value.strip().lstrip("#")
    if len(cleaned) == 3:
        cleaned = "".join(ch * 2 for ch in cleaned)
    if len(cleaned) != 6:
        return (23, 50, 42, alpha)
    try:
        return (int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16), alpha)
    except ValueError:
        return (23, 50, 42, alpha)


def _font_candidates(language: str, weight: str) -> list[str]:
    bold = weight == "bold"
    if language == "th":
        return [
            "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    if language == "zh-CN":
        return [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        ]
    return [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]


def _load_font(size: int, language: str, weight: str) -> ImageFont.ImageFont:
    for candidate in _font_candidates(language, weight):
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _line_width(draw: ImageDraw.ImageDraw, line: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), line, font=font)
    return max(0, bbox[2] - bbox[0])


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    tokens = cleaned.split(" ") if " " in cleaned else list(cleaned)
    lines: list[str] = []
    current = ""
    separator = " " if " " in cleaned else ""
    for token in tokens:
        candidate = token if not current else f"{current}{separator}{token}"
        if _line_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = token
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines:
        lines[-1] = _truncate_to_width(draw, lines[-1], font, max_width)
    return lines


def _truncate_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if _line_width(draw, text, font) <= max_width:
        return text
    suffix = "..."
    candidate = text
    while candidate and _line_width(draw, candidate + suffix, font) > max_width:
        candidate = candidate[:-1]
    return (candidate + suffix) if candidate else text[:1]


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box_width: int,
    box_height: int,
    max_size: int,
    min_size: int,
    max_lines: int,
    language: str,
    weight: str,
) -> tuple[ImageFont.ImageFont, list[str], int]:
    for size in range(max_size, min_size - 1, -2):
        font = _load_font(size, language, weight)
        lines = _wrap_text(draw, text, font, box_width, max_lines)
        if not lines:
            return font, [], size
        line_height = max(1, draw.textbbox((0, 0), "Ag", font=font)[3] - draw.textbbox((0, 0), "Ag", font=font)[1])
        total_height = line_height * len(lines) + round(size * 0.18) * max(0, len(lines) - 1)
        if total_height <= box_height and all(_line_width(draw, line, font) <= box_width for line in lines):
            return font, lines, size
    font = _load_font(min_size, language, weight)
    return font, _wrap_text(draw, text, font, box_width, max_lines), min_size


def render_text_layers_to_data_url(image_bytes: bytes, layers: list[dict[str, Any]], language: str = DEFAULT_LANGUAGE) -> tuple[str, list[str]]:
    normalized_language = normalize_language(language)
    warnings: list[str] = []
    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGBA")
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    base_size = min(width, height)

    for layer in layers:
        text = _clean_text(layer.get("text"))
        if not text:
            continue
        left = round(float(layer.get("x", 0.08)) * width)
        top = round(float(layer.get("y", 0.08)) * height)
        box_width = max(20, round(float(layer.get("width", 0.5)) * width))
        box_height = max(20, round(float(layer.get("height", 0.12)) * height))
        max_size = max(12, round(float(layer.get("font_size", 0.04)) * base_size))
        min_size = max(10, round(max_size * 0.52))
        max_lines = max(1, int(layer.get("max_lines", 2)))
        weight = "bold" if layer.get("weight") == "bold" else "regular"
        font, lines, size = _fit_text(draw, text, box_width, box_height, max_size, min_size, max_lines, normalized_language, weight)
        if size <= min_size and len(text) > 10:
            warnings.append(f"{layer.get('id', 'text')}: text was auto-fitted at minimum size")
        if not lines:
            continue
        spacing = round(size * 0.18)
        rendered = "\n".join(lines)
        bbox = draw.multiline_textbbox((0, 0), rendered, font=font, spacing=spacing, align=str(layer.get("align", "left")))
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        align = str(layer.get("align", "left"))
        if align == "center":
            text_left = left + max(0, (box_width - text_width) // 2)
        elif align == "right":
            text_left = left + max(0, box_width - text_width)
        else:
            text_left = left
        text_top = top + max(0, (box_height - text_height) // 2)
        color = _hex_to_rgba(str(layer.get("color", "#17322A")))
        shadow = (255, 255, 255, 180) if sum(color[:3]) < 360 else (0, 0, 0, 120)
        shadow_offset = max(1, round(size * 0.045))
        draw.multiline_text((text_left + shadow_offset, text_top + shadow_offset), rendered, font=font, fill=shadow, spacing=spacing, align=align)
        draw.multiline_text((text_left, text_top), rendered, font=font, fill=color, spacing=spacing, align=align)

    image.alpha_composite(overlay)
    output = BytesIO()
    image.convert("RGB").save(output, format="PNG", optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}", warnings
