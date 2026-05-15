from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import json
import logging
from pathlib import Path
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

from app.core.config import ImageGenerationSettings, ModelSettings, get_model_settings
from app.demo_data import ALL_MODULES, DEFAULT_DETAIL_LAYOUT_ID, DEFAULT_MODULES, DEMO_IMAGE_URLS, DETAIL_LAYOUTS, STYLE_OPTIONS
from app.services.compliance_checker import ComplianceProvider, ModelComplianceProvider, check_image_items, check_text_items
from app.services.image_model import call_image_edit_model, call_image_model
from app.services.language_renderer import (
    DEFAULT_LANGUAGE,
    apply_translated_text,
    build_text_layers,
    build_translation_messages,
    language_label,
    normalize_language,
    render_text_layers_to_data_url,
)
from app.services.object_storage import upload_bytes_to_object_storage, upload_data_url_to_object_storage
from app.services.prompt_builder import build_module_image_prompt
from app.services.product_compositor import compose_fixed_product_image
from app.services.text_model import call_text_model


logger = logging.getLogger("detail_image_generation")
MODEL_GATEWAY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
WHITE_BACKGROUND_MODULE_IDS = {"main_white_bg", "campaign_white_bg"}
REFERENCE_GENERATE_MODE = "reference_generate"
FIXED_PRODUCT_COMPOSITE_MODE = "fixed_product_composite"
FIXED_PRODUCT_REFERENCE_REQUIRED_ERROR = "固定产品合成需要先上传产品图，系统会把上传图作为产品母版复用，避免模型反复重绘导致包装、Logo 或瓶身变形。"
MAX_MODEL_PRODUCT_REFERENCE_IMAGES = 2
MAX_MODEL_STYLE_REFERENCE_IMAGES = 1
STYLE_SAMPLE_IMAGE_SIZE = "1024x1024"
DETAIL_IMAGE_GENERATION_SIZE = "1152x2048"
GENERATION_JOBS: dict[str, dict[str, Any]] = {}
GENERATION_JOB_TTL_SECONDS = 3600  # 1 hour
EDIT_JOBS: dict[str, dict[str, Any]] = {}
EDIT_JOB_TTL_SECONDS = 3600  # 1 hour
COMPOSE_JOBS: dict[str, dict[str, Any]] = {}
COMPOSE_JOB_TTL_SECONDS = 600  # 10 minutes
WHITE_BACKGROUND_REFERENCE_REQUIRED_ERROR = "白底图需要先上传产品图，系统会直接复用上传图以避免模型重绘导致包装、Logo 或瓶身变形。"


def resolve_image_settings(settings: ModelSettings, image_model_id: str | None) -> ImageGenerationSettings:
    return settings.image_options.get(image_model_id or settings.default_image_option_id, settings.image)


def _image_setting_configured(settings: ImageGenerationSettings) -> bool:
    return bool(settings.api_key or any(alternate.api_key for alternate in settings.retry_alternates))


def _image_setting_label(settings: ImageGenerationSettings) -> str:
    return f"{settings.label} ({settings.model})"


def _focused_model_reference_images(
    reference_images: list[str] | None,
    style_reference_images: list[str] | None,
    *,
    fixed_product_mode: bool = False,
) -> list[str]:
    if fixed_product_mode:
        return list(style_reference_images or [])[:MAX_MODEL_STYLE_REFERENCE_IMAGES]
    return [
        *list(reference_images or [])[:MAX_MODEL_PRODUCT_REFERENCE_IMAGES],
        *list(style_reference_images or [])[:MAX_MODEL_STYLE_REFERENCE_IMAGES],
    ]


async def _call_image_model_with_retry_groups(
    settings: ImageGenerationSettings,
    prompt: str,
    *,
    image: list[str] | None = None,
    size: str | None = None,
) -> tuple[list[str], str]:
    channels = [settings, *settings.retry_alternates]
    retry_groups = max(1, settings.retry_groups if settings.retry_alternates else 1)
    last_error = ""

    for group_index in range(1, retry_groups + 1):
        for channel in channels:
            channel_label = _image_setting_label(channel)
            if not channel.api_key:
                last_error = f"{channel_label} is not configured"
                continue
            try:
                urls = await call_image_model(channel, prompt, image=image, size=size)
            except Exception as exc:
                last_error = f"{channel_label} failed: {exc}"
                logger.warning(
                    "image generation channel failed group=%s/%s model=%s error=%s",
                    group_index,
                    retry_groups,
                    channel.model,
                    exc,
                )
                continue
            if urls:
                return urls, ""
            last_error = f"{channel_label} returned empty content"

    if retry_groups > 1:
        return [], f"{_image_setting_label(settings)} failed after {retry_groups} retry groups; last error: {last_error or 'no configured channel'}"
    return [], last_error or f"{_image_setting_label(settings)} is not configured"


def _cleanup_expired_generation_jobs() -> None:
    """Remove generation jobs older than TTL to prevent memory leaks."""
    now = datetime.now(UTC)
    expired = [
        job_id
        for job_id, job in GENERATION_JOBS.items()
        if (now - datetime.fromisoformat(job.get("created_at", now.isoformat()))).total_seconds() > GENERATION_JOB_TTL_SECONDS
    ]
    for job_id in expired:
        GENERATION_JOBS.pop(job_id, None)


def _cleanup_expired_edit_jobs() -> None:
    """Remove edit jobs older than TTL to prevent memory leaks."""
    now = datetime.now(UTC)
    expired = [
        job_id
        for job_id, job in EDIT_JOBS.items()
        if (now - datetime.fromisoformat(job.get("created_at", now.isoformat()))).total_seconds() > EDIT_JOB_TTL_SECONDS
    ]
    for job_id in expired:
        EDIT_JOBS.pop(job_id, None)


def _cleanup_expired_compose_jobs() -> None:
    """Remove compose jobs older than TTL to prevent memory leaks."""
    now = datetime.now(UTC)
    expired = [
        job_id
        for job_id, job in COMPOSE_JOBS.items()
        if (now - datetime.fromisoformat(job.get("created_at", now.isoformat()))).total_seconds() > COMPOSE_JOB_TTL_SECONDS
    ]
    for job_id in expired:
        COMPOSE_JOBS.pop(job_id, None)


async def upload_image_url_if_configured(url: str, folder: str) -> str:
    if not url.startswith("data:"):
        return url
    try:
        uploaded_url = await upload_data_url_to_object_storage(url, folder=folder)
    except Exception as exc:
        logger.warning("object storage image upload failed folder=%s error=%s", folder, exc)
        return url
    return uploaded_url or url


async def upload_bytes_if_configured(content: bytes, *, content_type: str, folder: str, extension: str) -> str:
    try:
        return await upload_bytes_to_object_storage(
            content,
            content_type=content_type,
            folder=folder,
            extension=extension,
        )
    except Exception as exc:
        logger.warning("object storage bytes upload failed folder=%s error=%s", folder, exc)
        return ""


async def upload_material_image_if_configured(material: UploadedMaterial) -> str:
    data_url = _data_uri(material)
    return await upload_image_url_if_configured(data_url, "materials")


async def prepare_compose_image_urls(image_urls: list[str]) -> list[str]:
    prepared: list[str] = []
    for url in image_urls[:20]:
        prepared.append(await upload_image_url_if_configured(url, "compose-sources"))
    return prepared


TEXT_MODEL_RETRY_DELAYS = [1, 2, 4, 8, 16]


async def call_text_model_with_retry(settings: Any, messages: list[dict[str, Any]]) -> str:
    if settings.text.api_key:
        attempts = len(TEXT_MODEL_RETRY_DELAYS) + 1
        last_error: Exception | None = None
        for attempt_index in range(attempts):
            try:
                content = await call_text_model(settings.text, messages)
                if content:
                    return content
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "text model failed model=%s attempt=%s/%s error=%s",
                    settings.text.model,
                    attempt_index + 1,
                    attempts,
                    exc,
                )
            if attempt_index < len(TEXT_MODEL_RETRY_DELAYS):
                await asyncio.sleep(TEXT_MODEL_RETRY_DELAYS[attempt_index])
        if last_error:
            raise last_error
    return ""


@dataclass(frozen=True)
class UploadedMaterial:
    filename: str
    content_type: str
    data: bytes
    slot: str = "documents"
    text: str = ""
    data_url: str = ""
    material_id: str = ""


def _data_uri(material: UploadedMaterial) -> str:
    if material.data_url:
        return material.data_url
    encoded = base64.b64encode(material.data).decode("ascii")
    return f"data:{material.content_type};base64,{encoded}"


def _is_remote_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _material_image_url(material: UploadedMaterial) -> str:
    if material.data_url:
        return material.data_url
    return _data_uri(material)


def uploaded_material_from_payload(payload: Any) -> UploadedMaterial:
    content_type = payload.content_type or "application/octet-stream"
    data = b""
    if payload.data_url:
        if _is_remote_url(payload.data_url):
            data = b""
        else:
            header, _, encoded = payload.data_url.partition(",")
            if header.startswith("data:") and ";base64" in header:
                content_type = header.removeprefix("data:").split(";", 1)[0] or content_type
            data = base64.b64decode(encoded or payload.data_url, validate=False)
    elif payload.text:
        data = payload.text.encode("utf-8")

    return UploadedMaterial(
        filename=payload.filename or "uploaded-file",
        content_type=content_type,
        data=data[:8 * 1024 * 1024],
        slot=payload.slot or "documents",
        text=payload.text or "",
        data_url=payload.data_url or "",
        material_id=str(getattr(payload, "id", "") or ""),
    )


def _detail_layout_analysis_guide(detail_layout_id: str | None) -> str:
    layout_id = detail_layout_id or DEFAULT_DETAIL_LAYOUT_ID
    if layout_id == "detail_standard_conversion_10":
        return (
            "当前详情图排版结构：标准转化结构（10 屏）。"
            "请按 详情首图、品牌与资质背书、研发实力、痛点场景、效果对比、竞品对比、产品大图强化、成分总览、使用方法、产品信息 拆解资料。"
            "detail_layout_brief 需要输出 layout_id、screen_count、modules、missing_evidence。"
            "modules 必须是 10 个对象，顺序对应当前结构，每项包含 module_id、module_name、page_task、required_content；"
            "required_content 必须写成可直接用于该屏生成的 2-5 条中文信息。"
            "没有上传检测报告、说明书或真人反馈时，要基于产品主图和已识别信息做谨慎 AI 补全，不能留空，也不能编造真实机构、编号、头像昵称或绝对化医疗功效。"
        )
    return (
        "当前详情图排版结构：证据链长图结构（16 屏，默认）。"
        "请按以下模块拆解资料：1 首屏爆点、2 痛点放大、3 产品解决方案、4 差评与竞品对比、5 真人实测引入、"
        "6 效果对比验证、7 研发体系背书、8 核心成分一机制、9 核心成分一证明、10 核心成分二机制、"
        "11 辅助功效机制、12 辅助功效验证、13 真人反馈合集、14 质地与肤感展示、15 品牌感与情绪价值、16 使用方法。"
        "第 11、12 屏必须是通用辅助购买理由，不要固定写成任何预设单一功效；应从资料中挑选第二层最有转化力的功效或体验。"
        "detail_layout_brief 需要输出 layout_id、screen_count、modules、selected_auxiliary_effect、competitor_comparison、missing_evidence。"
        "modules 必须是 16 个对象，顺序对应当前结构，每项包含 module_id、module_name、page_task、required_content；"
        "module_id 顺序必须是：detail_ec_hero, detail_ec_pain_matrix, detail_ec_solution, detail_ec_competitor_comparison, detail_ec_real_trial, "
        "detail_ec_effect_validation, detail_ec_research_system, detail_ec_ingredient_1_mechanism, detail_ec_ingredient_1_proof, detail_ec_ingredient_2_mechanism, "
        "detail_ec_auxiliary_mechanism, detail_ec_auxiliary_validation, detail_ec_real_feedback, detail_ec_texture, detail_ec_brand_sensory, detail_ec_usage。"
        "required_content 必须写成可直接用于该屏生成的 2-5 条中文信息。"
        "没有上传检测报告、说明书或真人反馈时，要基于产品主图和已识别信息做谨慎 AI 补全，不能留空，也不能编造真实机构、编号、头像昵称或绝对化医疗功效。"
    )


def build_material_analysis_messages(materials: list[UploadedMaterial], detail_layout_id: str | None = None) -> list[dict[str, Any]]:
    from app.services.file_parser import parse_document

    file_lines = "\n".join(
        f"- [{material.slot}] {material.filename} ({material.content_type or 'unknown'}, {len(material.data)} bytes)"
        for material in materials
    )
    prompt = (
        "你是电商护肤详情页产品经理。请根据上传的产品主图和资料，提取商品详情页生成所需信息。"
        "如果资料很长，先在内部筛选最适合打动消费者、最可信、最适合上图表达的内容，再写入 JSON。"
        "必须优先提炼：1) 可作为购买理由的核心卖点；2) 有数据或实验依据的功效点；3) 可用于权威背书的报告/资质/实验室信息；"
        "4) 需要谨慎表达或不能直接宣传的内容。"
        "必须只输出 JSON，不要输出解释文字。字段包括：product_name, category, spec, "
        "core_selling_points, functions, ingredients, target_users, usage_method, authority_assets, effect_claims, material_highlights, cross_image_brief, detail_layout_brief。"
        f"{_detail_layout_analysis_guide(detail_layout_id)}"
        "cross_image_brief 用于把新分支拆解结果可同步影响主图/活动图，字段包括 main_image_selling_points、campaign_selling_points、visual_evidence、avoid_claims。"
        "All JSON string values must be written in Simplified Chinese. Translate Korean, Japanese, English, or any other source language into natural zh-CN e-commerce copy before returning JSON."
        "ingredients 必须是按详情页展示优先级排序的数组，每项形如 {\"name\":\"成分名\",\"benefit\":\"一句消费者能理解的温和作用\"}；"
        "优先选择最值得单独上图讲解的 3 个核心成分，benefit 不能写成药品疗效或治疗承诺。"
        "material_highlights 是 3-6 条面向消费者的资料亮点摘要，每条应短、可信、有转化力，并可直接辅助电商图片文案。"
        "如果图片或资料里无法确定，请基于护肤品详情页常识给出谨慎的 AI 补全，并避免绝对化医疗功效。"
        f"\n上传文件：\n{file_lines}"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for material in materials:
        if material.content_type.startswith("image/") and (material.data or material.data_url):
            content.append({"type": "image_url", "image_url": {"url": _material_image_url(material)}})
        elif material.content_type == "application/pdf" and material.data:
            # PDF: send as file to LLM API (native support), with PyMuPDF text as fallback context.
            content.append({"type": "file", "file": {"filename": material.filename, "file_data": _data_uri(material)}})
            result = parse_document(material.data, material.content_type, material.filename)
            for w in result.warnings:
                logger.warning("file parse warning file=%s warning=%s", material.filename, w)
            if result.text:
                content.append({"type": "text", "text": f"{material.filename} 文本提取备用：\n{result.text[:6000]}"})
        elif material.data:
            # Word, Excel, and other document formats: extract text via file_parser.
            result = parse_document(material.data, material.content_type, material.filename)
            for w in result.warnings:
                logger.warning("file parse warning file=%s warning=%s", material.filename, w)
            text = (material.text or result.text).strip()
            if text:
                content.append({"type": "text", "text": f"{material.filename} 内容摘录：\n{text}"})
            elif result.warnings:
                content.append({"type": "text", "text": f"{material.filename}：{'；'.join(result.warnings)}"})
    return [{"role": "user", "content": content}]



def _extract_json_object(raw: str) -> dict[str, Any] | None:
    cleaned = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in re.split(r"[/、,\n]", value) if item.strip()] or fallback
    return fallback


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, item in value.items():
        key_text = str(key).strip()
        item_text = str(item).strip()
        if key_text and item_text:
            normalized[key_text] = item_text
    return normalized


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


def _safe_ingredient_benefit(name: str, benefit: str) -> str:
    return _ingredient_default_benefit(name) if _is_placeholder_ingredient_benefit(benefit) else benefit


def _ingredients(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                benefit = _safe_ingredient_benefit(name, str(item.get("benefit", "")).strip())
                normalized.append({"name": name, "benefit": benefit})
        elif str(item).strip():
            name = str(item).strip()
            normalized.append({"name": name, "benefit": _ingredient_default_benefit(name)})
    return normalized[:3]


def _effect_claims(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            claim = str(item.get("claim", "")).strip()
            value_text = str(item.get("value", "")).strip()
            source_type = str(item.get("source_type", "ai_generated")).strip() or "ai_generated"
            if claim:
                normalized.append({"claim": claim, "value": value_text, "source_type": source_type})
        elif str(item).strip():
            normalized.append({"claim": str(item).strip(), "value": "", "source_type": "ai_generated"})
    return normalized


def _dedupe_strings(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        deduped.append(text)
        seen.add(text)
    return deduped


def _loose_string_items(value: Any) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_loose_string_items(item))
        return _dedupe_strings(items)
    if isinstance(value, dict):
        preferred_keys = (
            "required_content",
            "manual_notes",
            "page_task",
            "headline_direction",
            "primary_visual",
            "focus",
            "content",
            "summary",
        )
        items: list[str] = []
        for key in preferred_keys:
            if key in value:
                items.extend(_loose_string_items(value.get(key)))
        if not items:
            items.extend(str(item).strip() for item in value.values() if isinstance(item, str) and item.strip())
        return _dedupe_strings(items)
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in re.split(r"[/、,\n]", value) if item.strip()]
    return []


def _detail_layout_modules_for(layout_id: str | None) -> list[dict[str, Any]]:
    normalized_layout_id = layout_id or DEFAULT_DETAIL_LAYOUT_ID
    for layout in DETAIL_LAYOUTS:
        if layout.get("id") == normalized_layout_id:
            return [dict(module) for module in layout.get("modules", [])]
    return [dict(module) for module in DETAIL_LAYOUTS[0].get("modules", [])]


def _detail_layout_id_for(raw_layout_id: Any, requested_layout_id: str | None) -> str:
    candidate = str(raw_layout_id or requested_layout_id or DEFAULT_DETAIL_LAYOUT_ID).strip()
    return candidate if any(layout.get("id") == candidate for layout in DETAIL_LAYOUTS) else DEFAULT_DETAIL_LAYOUT_ID


def _module_label(module: dict[str, Any]) -> str:
    return f"第 {module.get('order')} 屏：{module.get('name')}" if module.get("order") else str(module.get("name") or module.get("id"))


def _module_match(module: dict[str, Any], item: dict[str, Any]) -> bool:
    module_id = str(module.get("id", "")).strip()
    module_name = str(module.get("name", "")).strip()
    module_order = str(module.get("order", "")).strip()
    candidates = {
        str(item.get("module_id", "")).strip(),
        str(item.get("id", "")).strip(),
        str(item.get("module_name", "")).strip(),
        str(item.get("name", "")).strip(),
        str(item.get("screen", "")).strip(),
        str(item.get("order", "")).strip(),
    }
    return module_id in candidates or module_name in candidates or module_order in candidates or _module_label(module) in candidates


def _existing_module_for(brief: dict[str, Any], module: dict[str, Any]) -> dict[str, Any]:
    modules = brief.get("modules")
    if not isinstance(modules, list):
        return {}
    for item in modules:
        if isinstance(item, dict) and _module_match(module, item):
            return item
    return {}


def _module_focus_items(brief: dict[str, Any], module: dict[str, Any]) -> list[str]:
    focus = brief.get("module_focus")
    module_id = str(module.get("id", "")).strip()
    module_name = str(module.get("name", "")).strip()
    module_order = str(module.get("order", "")).strip()
    if isinstance(focus, dict):
        keys = [
            module_id,
            module_name,
            _module_label(module),
            module_order,
            f"第 {module_order} 屏",
            f"第{module_order}屏",
        ]
        for key in keys:
            if key in focus:
                return _loose_string_items(focus.get(key))
    if isinstance(focus, list):
        for item in focus:
            if isinstance(item, dict) and _module_match(module, item):
                return _loose_string_items(item)
        order = int(module.get("order") or 0)
        if 1 <= order <= len(focus):
            return _loose_string_items(focus[order - 1])
    return []


def _ingredient_lines(info: dict[str, Any]) -> list[str]:
    ingredients = info.get("ingredients") if isinstance(info.get("ingredients"), list) else []
    return [
        f"{item.get('name')}：{item.get('benefit')}"
        for item in ingredients
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]


def _effect_lines(info: dict[str, Any]) -> list[str]:
    claims = info.get("effect_claims") if isinstance(info.get("effect_claims"), list) else []
    lines: list[str] = []
    for item in claims:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()
        value = str(item.get("value", "")).strip()
        if claim:
            lines.append(f"{claim} {value}".strip())
    return lines


def _detail_module_fallback_items(info: dict[str, Any], module: dict[str, Any]) -> list[str]:
    module_id = str(module.get("id", ""))
    product_name = str(info.get("product_name") or "").strip()
    category = str(info.get("category") or "").strip()
    product_anchor = product_name or category or "当前护肤产品"
    selling = _string_list(info.get("core_selling_points"), []) or _string_list(info.get("functions"), []) or [f"{product_anchor} 的核心护理卖点"]
    functions = _string_list(info.get("functions"), []) or selling
    users = _string_list(info.get("target_users"), []) or ["日常护肤人群"]
    highlights = _string_list(info.get("material_highlights"), []) or selling
    authority = _string_list(info.get("authority_assets"), []) or ["没有上传检测报告时，仅做研发流程和配方可信感表达，不编造真实机构或编号"]
    ingredients = _ingredient_lines(info) or ["基于产品图和品类识别核心护理成分方向"]
    effects = _effect_lines(info) or ["使用体验型表达，不冒充真实测试数据"]
    usage = _string_list(info.get("usage_method"), []) or ["洁面后取适量使用", "轻拍或按摩至吸收"]
    brief = info.get("detail_layout_brief") if isinstance(info.get("detail_layout_brief"), dict) else {}
    auxiliary = str(brief.get("selected_auxiliary_effect") or "").strip() or (functions[1] if len(functions) > 1 else functions[0])
    competitor = str(brief.get("competitor_comparison") or "").strip() or "普通同类产品常见厚重、黏腻或说服力不足，本品突出更清爽、更贴合目标人群的方案"

    mapping: dict[str, list[str]] = {
        "hero": [product_anchor, *selling[:2], *highlights[:1]],
        "brand_qualification": [*highlights[:2], *authority[:2]],
        "research_strength": authority[:3],
        "pain_scene": [*users[:2], *functions[:2]],
        "effect_comparison": effects[:3],
        "competitor_comparison": [competitor, *selling[:2]],
        "product_showcase": [product_anchor, *selling[:2], *functions[:2]],
        "ingredient_overview": ingredients[:3],
        "usage": usage[:4],
        "product_info": [product_anchor, category or "护肤品", *usage[:2]],
        "detail_ec_hero": [product_anchor, *selling[:2], *highlights[:1]],
        "detail_ec_pain_matrix": [*users[:2], *functions[:2]],
        "detail_ec_solution": [*selling[:2], *functions[:2], *ingredients[:2]],
        "detail_ec_competitor_comparison": [competitor, *selling[:2]],
        "detail_ec_real_trial": [*users[:2], "没有真人素材时，用泛化真人使用场景表达，不编造具体身份"],
        "detail_ec_effect_validation": effects[:3],
        "detail_ec_research_system": authority[:3],
        "detail_ec_ingredient_1_mechanism": ingredients[:1],
        "detail_ec_ingredient_1_proof": [*(ingredients[:1]), *highlights[:2]],
        "detail_ec_ingredient_2_mechanism": (ingredients[1:2] or ingredients[:1]),
        "detail_ec_auxiliary_mechanism": [auxiliary, *functions[:2], *highlights[:1]],
        "detail_ec_auxiliary_validation": [auxiliary, *effects[:2], "没有真实数据时使用体验趋势，不冒充测试结论"],
        "detail_ec_real_feedback": [*effects[:2], "没有真人反馈时只写泛化使用感方向，不编造头像、昵称或日期"],
        "detail_ec_texture": [*highlights[:2], "根据产品图表达质地、延展、吸收或清爽度"],
        "detail_ec_brand_sensory": [*highlights[:2], "根据包装和产品调性补充品牌感与使用仪式感"],
        "detail_ec_usage": usage[:4],
    }
    return _dedupe_strings(mapping.get(module_id, [str(module.get("description") or ""), *selling[:2]]))[:6]


def _normalize_detail_layout_brief(value: Any, info: dict[str, Any], detail_layout_id: str | None) -> dict[str, Any]:
    brief = value if isinstance(value, dict) else {}
    layout_id = _detail_layout_id_for(brief.get("layout_id"), detail_layout_id)
    layout_modules = _detail_layout_modules_for(layout_id)
    modules: list[dict[str, Any]] = []
    for module in layout_modules:
        existing = _existing_module_for(brief, module)
        required_content = (
            _loose_string_items(existing.get("required_content"))
            or _module_focus_items(brief, module)
            or _detail_module_fallback_items({**info, "detail_layout_brief": brief}, module)
        )
        normalized_module = {
            "module_id": str(module.get("id")),
            "module_name": str(existing.get("module_name") or existing.get("name") or _module_label(module)),
            "page_task": str(existing.get("page_task") or module.get("description") or "").strip(),
            "required_content": required_content[:6],
        }
        for key in ("headline_direction", "primary_visual", "manual_notes", "forbidden_content", "data_source_note", "compliance_boundary"):
            if existing.get(key):
                normalized_module[key] = existing.get(key)
        modules.append(normalized_module)

    return {
        **brief,
        "layout_id": layout_id,
        "screen_count": len(layout_modules),
        "modules": modules,
    }


def normalize_product_info_from_model(raw: str, detail_layout_id: str | None = None) -> dict[str, Any]:
    data = _extract_json_object(raw) or {}
    info = {
        "product_name": str(data.get("product_name") or "").strip(),
        "category": str(data.get("category") or "").strip(),
        "spec": str(data.get("spec") or "").strip(),
        "core_selling_points": _string_list(data.get("core_selling_points"), []),
        "functions": _string_list(data.get("functions"), []),
        "ingredients": _ingredients(data.get("ingredients")),
        "target_users": _string_list(data.get("target_users"), []),
        "usage_method": _string_list(data.get("usage_method"), []),
        "authority_assets": _string_list(data.get("authority_assets"), []),
        "effect_claims": _effect_claims(data.get("effect_claims")),
        "material_highlights": _string_list(data.get("material_highlights"), [])[:6],
        "cross_image_brief": data.get("cross_image_brief") if isinstance(data.get("cross_image_brief"), dict) else {},
        "confirmation_status": "pending",
    }
    info["detail_layout_brief"] = _normalize_detail_layout_brief(data.get("detail_layout_brief"), info, detail_layout_id)
    return info


def normalize_style_plan_from_model(raw: str) -> dict[str, Any]:
    data = _extract_json_object(raw) or {}
    keywords = _string_list(data.get("keywords"), [])
    return {
        "id": "ai_custom",
        "seed_id": str(data.get("seed_id") or "").strip(),
        "name": str(data.get("name") or "AI 自定义风格").strip() or "AI 自定义风格",
        "theme": str(data.get("theme") or "").strip(),
        "primary_color": str(data.get("primary_color") or "#1F8C43").strip() or "#1F8C43",
        "keywords": keywords[:6] or ["产品定制", "电商高级", "统一视觉"],
        "asset": "",
        "best_for": _string_list(data.get("best_for"), [])[:6],
        "visual_elements": _string_list(data.get("visual_elements"), [])[:12],
        "materials": _string_list(data.get("materials"), [])[:10],
        "lighting": _string_list(data.get("lighting"), [])[:10],
        "module_usage": _string_map(data.get("module_usage")),
        "forbidden": _string_list(data.get("forbidden"), [])[:10],
        "visual_direction": str(data.get("visual_direction") or "根据产品定位生成统一视觉方向").strip(),
        "layout_guidance": str(data.get("layout_guidance") or "主图突出产品，详情页按模块建立统一版式系统").strip(),
        "reasoning": str(data.get("reasoning") or "基于产品信息、品类和包装色规划").strip(),
    }


def normalize_style_reference_plan_from_model(raw: str) -> dict[str, Any]:
    style = normalize_style_plan_from_model(raw)
    forbidden = _string_list(style.get("forbidden"), [])
    reference_forbidden = [
        "不要复刻参考图中的品牌",
        "不要复刻参考图中的 Logo、商标、具体产品包装或可读小字",
        "不要照搬参考图里的具体文案、人物肖像、机构背书或水印",
    ]
    return {
        **style,
        "id": "style_reference",
        "seed_id": style.get("seed_id") or "benchmark_image",
        "forbidden": [*forbidden, *[item for item in reference_forbidden if item not in forbidden]][:10],
        "reasoning": style.get("reasoning") or "基于用户上传的对标图片提取可复用风格指纹",
    }


def build_style_planning_messages(
    product_info: dict[str, Any] | None,
    category: str | None,
    product_images: list[UploadedMaterial] | None = None,
) -> list[dict[str, Any]]:
    info = product_info or {}
    category_line = (
        f"品类：{info['category']}"
        if str(info.get("category", "")).strip()
        else "请自行识别产品品类，不要套用任何前端默认类目。"
    )
    lines = [
            "你是资深电商美术指导。请基于产品资料和产品图，全权规划一个全新的电商视觉风格。",
            "不要从现有固定预设风格里选择，也不要只输出太空、深海、实验室这类模板名。",
            "不要依赖前置颜色提取；请直接观察产品图，综合质地、品类、价格感和卖点来规划风格元素系统。",
            "风格元素系统必须重点说明主题元素库、材质、光影、构图、字体层级、图标/装饰元素、摄影或渲染质感，并保证这些元素在整套图片里一致。",
            "每张图可以根据模块内容使用不同颜色；primary_color 只是参考色或局部点缀色，不是整套图片的强制背景色或统一主色。",
            "必须只输出 JSON，不要输出解释文字。",
            "JSON 字段：seed_id, name, theme, primary_color, keywords, best_for, visual_elements, materials, lighting, module_usage, forbidden, visual_direction, layout_guidance, reasoning。",
            "要求：name 是 6-12 个中文字符的风格名；primary_color 是十六进制参考色；keywords 是 3-6 个短词。",
            "visual_elements 是可见主题元素数组；materials 是材质数组；lighting 是光影数组；module_usage 是对象，至少包含首图、成分图、效果图、使用场景、活动图如何使用主题元素。",
            "forbidden 是禁止项数组，明确排除廉价、跑题、遮挡产品或违规表达；visual_direction 写清楚材质、光影、氛围、摄影或渲染质感；layout_guidance 写清楚主图和详情页如何保持风格元素一致但模块颜色和版式可差异化。",
            "避免医疗化、绝对化功效，不编造品牌授权或真实机构背书。",
    ]
    lines.extend([category_line, f"产品信息 JSON：{json.dumps(info, ensure_ascii=False)}"])
    prompt = "\n".join(lines)
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for material in (product_images or [])[:3]:
        if material.content_type.startswith("image/") and (material.data or material.data_url):
            content.append({"type": "image_url", "image_url": {"url": _material_image_url(material)}})
    return [{"role": "user", "content": content}]


def build_style_reference_analysis_messages(
    product_info: dict[str, Any] | None,
    style_reference_images: list[UploadedMaterial] | None = None,
) -> list[dict[str, Any]]:
    info = product_info or {}
    lines = [
        "你是资深电商美术指导和视觉风格分析师。请分析用户上传的对标图片，提取可复用到商品图生成中的风格指纹。",
        "不要描述成单张图片赏析，要转成一套可跨主图、活动图、详情模块复用的视觉系统。",
        "必须分析这些维度：主色、辅色、点缀色；光影；构图；背景与材质；产品摆放和主体占比；字体层级；信息密度；装饰元素；摄影或渲染质感；电商转化氛围。",
        "必须明确不要复刻哪些内容：品牌名、Logo、商标、具体产品包装、人物肖像、具体文案、小字、机构背书、水印和其他可能侵权元素。",
        "只输出 JSON，不要解释文字。",
        "JSON 字段：seed_id, name, theme, primary_color, keywords, best_for, visual_elements, materials, lighting, module_usage, forbidden, visual_direction, layout_guidance, reasoning。",
        "要求：name 是 6-12 个中文字符的风格名；primary_color 是十六进制参考色；keywords 是 3-6 个短词。",
        "visual_elements 写可迁移的元素，不写原图品牌/产品专属元素；materials 写背景、道具和表面质感；lighting 写明确光线方向与强弱；module_usage 至少包含首图、成分图、效果图、使用场景、活动图。",
        "layout_guidance 要说明如何在后续生成中参考对标图的构图与排版，但避免过度复刻原图。",
        f"当前产品信息 JSON：{json.dumps(info, ensure_ascii=False)}",
    ]
    content: list[dict[str, Any]] = [{"type": "text", "text": "\n".join(lines)}]
    for material in (style_reference_images or [])[:4]:
        if material.content_type.startswith("image/") and (material.data or material.data_url):
            content.append({"type": "image_url", "image_url": {"url": _material_image_url(material)}})
    return [{"role": "user", "content": content}]


def _plain_text(value: Any, fallback: str) -> str:
    cleaned = str(value or "").strip()
    return cleaned or fallback


def build_custom_style_sample_prompt(style: dict[str, Any], product_info: dict[str, Any] | None) -> str:
    info = product_info or {}
    keywords = " / ".join(_string_list(style.get("keywords"), [])) or "高级 / 干净 / 统一"
    visual_elements = " / ".join(_string_list(style.get("visual_elements"), []))
    materials = " / ".join(_string_list(style.get("materials"), []))
    lighting = " / ".join(_string_list(style.get("lighting"), []))
    forbidden = " / ".join(_string_list(style.get("forbidden"), []))
    return "\n".join(
        [
            "请生成 1 张中文电商护肤视觉风格样例图，用来预览 AI 规划的风格方向。",
            "这不是最终商品图，不需要完全复刻用户产品包装，也不要生成真实品牌 Logo、可识别商标或可读包装小字。",
            "画面可以使用无品牌护肤瓶/面霜罐/精华瓶作为通用占位产品，重点展示风格元素系统：材质、光影、氛围、版式、字体层级、图标/装饰元素和摄影或渲染质感。",
            f"- 参考产品：{_plain_text(info.get('product_name'), '护肤品')}",
            f"- 品类：{_plain_text(info.get('category'), '护肤品')}",
            f"- 风格名称：{_plain_text(style.get('name'), 'AI 自定义风格')}",
            *([f"- AI 主题：{_plain_text(style.get('theme'), '')}"] if _plain_text(style.get("theme"), "") else []),
            f"- 参考色：{_plain_text(style.get('primary_color'), '#F4F1EC')}（参考色只作为局部点缀，不要求整张样例统一成这个颜色）",
            f"- 视觉关键词：{keywords}",
            *([f"- 主题元素库：{visual_elements}"] if visual_elements else []),
            *([f"- 材质系统：{materials}"] if materials else []),
            *([f"- 光影系统：{lighting}"] if lighting else []),
            f"- 视觉方向：{_plain_text(style.get('visual_direction'), '高级、干净、统一')}",
            f"- 版式方向：{_plain_text(style.get('layout_guidance'), '主图突出产品，详情页模块化')}",
            *([f"- 禁止项：{forbidden}"] if forbidden else []),
            "构图要求：16:10 横向风格卡片封面，中央或偏左放通用护肤品占位，背景呈现规划风格的材质与光影，可用多种协调颜色展示风格延展性。",
            "文字要求：最多只放 2-4 个大的中文风格关键词，不能出现乱码、密集小字、水印或平台 UI。",
        ]
    )


def create_demo_project() -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": f"project_{uuid4().hex[:8]}",
        "name": "新建商品详情页",
        "product_category": "待 AI 解析",
        "style_id": "space_repair",
        "detail_layout_id": DEFAULT_DETAIL_LAYOUT_ID,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }


async def analyze_product_materials(raw_text: str | None = None) -> dict[str, Any]:
    settings = get_model_settings()
    if settings.text.api_key and raw_text:
        prompt = (
            "你是电商护肤详情页产品经理。请从资料中提炼商品信息，"
            "输出 JSON 字段：product_name, category, core_selling_points, functions, "
            "ingredients, target_users, usage_method, authority_assets, effect_claims, material_highlights。"
            "ingredients 必须按适合详情页展示的优先级排序，每项包含 name 和 benefit；"
            "benefit 写成一句消费者能理解、可上图但不医疗化的成分作用。"
            "material_highlights 写 3-6 条最能吸引消费者且有资料依据的短亮点。"
            f"\n资料：{raw_text}"
        )
        content = await call_text_model_with_retry(settings, [{"role": "user", "content": prompt}])
        if content:
            return {"source": "model", "raw": content, "product_info": normalize_product_info_from_model(content)}
    return {"source": "error", "error": "text model is not configured or no raw text was provided"}


async def analyze_uploaded_materials(materials: list[UploadedMaterial], detail_layout_id: str | None = None) -> dict[str, Any]:
    settings = get_model_settings()
    if not materials:
        return {"source": "error", "error": "no materials were uploaded"}
    if not settings.text.api_key:
        return {"source": "error", "error": "text model is not configured"}

    try:
        model_materials: list[UploadedMaterial] = []
        uploaded_materials: list[dict[str, str]] = []
        for material in materials:
            if material.content_type.startswith("image/") and (material.data or material.data_url):
                image_url = material.data_url if _is_remote_url(material.data_url) else await upload_material_image_if_configured(material)
                model_materials.append(
                    UploadedMaterial(
                        filename=material.filename,
                        content_type=material.content_type,
                        data=material.data,
                        slot=material.slot,
                        text=material.text,
                        data_url=image_url,
                        material_id=material.material_id,
                    )
                )
                if _is_remote_url(image_url):
                    uploaded_materials.append(
                        {
                            "id": material.material_id,
                            "slot": material.slot,
                            "filename": material.filename,
                            "content_type": material.content_type,
                            "url": image_url,
                        }
                    )
            else:
                model_materials.append(material)
        content = await call_text_model_with_retry(settings, build_material_analysis_messages(model_materials, detail_layout_id=detail_layout_id))
    except Exception as exc:
        return {"source": "error", "error": str(exc)}
    if not content:
        return {"source": "error", "error": "text model returned empty content"}

    return {"source": "model", "product_info": normalize_product_info_from_model(content, detail_layout_id=detail_layout_id), "raw": content, "uploaded_materials": uploaded_materials}


async def plan_custom_style(
    product_info: dict[str, Any] | None,
    category: str | None = None,
    product_images: list[UploadedMaterial] | None = None,
) -> dict[str, Any]:
    settings = get_model_settings()
    if not settings.text.api_key:
        return {"source": "error", "error": "text model is not configured"}

    try:
        model_images: list[UploadedMaterial] = []
        for material in product_images or []:
            if material.content_type.startswith("image/") and (material.data or material.data_url):
                image_url = material.data_url if _is_remote_url(material.data_url) else await upload_material_image_if_configured(material)
                model_images.append(
                    UploadedMaterial(
                        filename=material.filename,
                        content_type=material.content_type,
                        data=material.data,
                        slot=material.slot,
                        text=material.text,
                        data_url=image_url,
                        material_id=material.material_id,
                    )
                )
        content = await call_text_model_with_retry(settings, build_style_planning_messages(product_info, category, model_images))
    except Exception as exc:
        return {"source": "error", "error": str(exc)}
    if not content:
        return {"source": "error", "error": "text model returned empty content"}

    style = normalize_style_plan_from_model(content)
    return {"source": "model", "style": style, "raw": content, "warnings": []}


async def analyze_style_reference(
    product_info: dict[str, Any] | None,
    style_reference_images: list[UploadedMaterial] | None = None,
) -> dict[str, Any]:
    settings = get_model_settings()
    if not style_reference_images:
        return {"source": "error", "error": "no style reference images were uploaded"}
    if not settings.text.api_key:
        return {"source": "error", "error": "text model is not configured"}

    try:
        model_images: list[UploadedMaterial] = []
        uploaded_references: list[dict[str, str]] = []
        for material in style_reference_images[:4]:
            if material.content_type.startswith("image/") and (material.data or material.data_url):
                image_url = material.data_url if _is_remote_url(material.data_url) else await upload_material_image_if_configured(material)
                model_images.append(
                    UploadedMaterial(
                        filename=material.filename,
                        content_type=material.content_type,
                        data=material.data,
                        slot=material.slot,
                        text=material.text,
                        data_url=image_url,
                        material_id=material.material_id,
                    )
                )
                if _is_remote_url(image_url):
                    uploaded_references.append(
                        {
                            "id": material.material_id,
                            "slot": material.slot,
                            "filename": material.filename,
                            "content_type": material.content_type,
                            "url": image_url,
                        }
                    )
        if not model_images:
            return {"source": "error", "error": "no valid style reference images were uploaded"}
        content = await call_text_model_with_retry(settings, build_style_reference_analysis_messages(product_info, model_images))
    except Exception as exc:
        return {"source": "error", "error": str(exc)}
    if not content:
        return {"source": "error", "error": "text model returned empty content"}

    style = normalize_style_reference_plan_from_model(content)
    return {"source": "model", "style": style, "raw": content, "uploaded_style_references": uploaded_references, "warnings": []}


async def generate_custom_style_sample(style: dict[str, Any], product_info: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = get_model_settings()
    warnings: list[str] = []
    if not settings.image.api_key:
        return {"source": "error", "error": "image model is not configured", "warnings": ["image model is not configured"]}

    try:
        sample_urls = await call_image_model(
            settings.image,
            build_custom_style_sample_prompt(style, product_info),
            size=STYLE_SAMPLE_IMAGE_SIZE,
        )
        if sample_urls:
            updated_style = {**style, "asset": sample_urls[0]}
            return {"source": "model", "style": updated_style, "warnings": warnings}
    except Exception as exc:
        return {"source": "error", "error": str(exc), "warnings": [f"style sample generation failed: {exc}"]}

    return {"source": "error", "error": "image model returned empty content", "warnings": warnings}


async def translate_text_layers(layers: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    normalized_language = normalize_language(language)
    if normalized_language == DEFAULT_LANGUAGE or not layers:
        return [{**layer, "text": str(layer.get("source_text") or layer.get("text") or "").strip()} for layer in layers]

    settings = get_model_settings()
    if not settings.text.api_key:
        raise RuntimeError("text model is not configured")
    raw = await call_text_model_with_retry(settings, build_translation_messages(layers, normalized_language))
    if not raw:
        raise RuntimeError("text model returned empty translation")
    return apply_translated_text(layers, raw)


async def render_layered_language_version(
    *,
    base_url: str,
    layers: list[dict[str, Any]],
    language: str,
    folder: str = "translated",
    module_id: str = "",
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_language = normalize_language(language)
    translated_layers = await translate_text_layers(layers, normalized_language)
    image_bytes = await _read_image_bytes(base_url)
    data_url, warnings = render_text_layers_to_data_url(image_bytes, translated_layers, language=normalized_language)
    uploaded_url = await upload_image_url_if_configured(data_url, f"{folder}/{normalized_language}")
    compliance = await check_project_text_compliance(
        text_layers_to_compliance_items(translated_layers, module_id=module_id, language=normalized_language),
        platform_id=platform_id,
        product_info=product_info,
    )
    return {
        "language": normalized_language,
        "language_label": language_label(normalized_language),
        "url": uploaded_url,
        "layers": translated_layers,
        "warnings": warnings,
        "compliance": compliance,
    }


def text_layers_to_compliance_items(
    layers: list[dict[str, Any]],
    *,
    module_id: str = "",
    language: str = DEFAULT_LANGUAGE,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for layer in layers:
        text = str(layer.get("text") or layer.get("source_text") or "").strip()
        if not text:
            continue
        items.append(
            {
                "text": text,
                "location": {
                    "source_type": "text_layer",
                    "module_id": module_id,
                    "field": str(layer.get("role") or layer.get("id") or "text"),
                    "language": language,
                },
            }
        )
    return items


async def check_project_text_compliance(
    items: list[dict[str, Any]],
    *,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    compliance_provider: ComplianceProvider | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    return await check_text_items(
        items,
        compliance_provider=compliance_provider or create_default_compliance_provider(),
        platform_id=platform_id,
        product_info=product_info,
        debug=debug,
    )


def create_default_compliance_provider() -> ComplianceProvider:
    return ModelComplianceProvider(get_model_settings().text)


async def check_project_image_compliance(
    image_urls: list[str],
    *,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    compliance_provider: ComplianceProvider | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    images: list[dict[str, Any]] = []
    for image_index, image_url in enumerate(image_urls[:20]):
        image: dict[str, Any] = {"url": image_url, "field": "image", "image_index": image_index}
        try:
            image["bytes"] = await _read_image_bytes(image_url)
        except Exception as exc:
            image["bytes"] = b""
            image["read_error"] = str(exc)
        images.append(image)
    return await check_image_items(
        images,
        compliance_provider=compliance_provider or create_default_compliance_provider(),
        platform_id=platform_id,
        product_info=product_info,
        debug=debug,
    )


async def build_layered_generated_image(
    *,
    module: dict[str, Any],
    product_info: dict[str, Any] | None,
    base_url: str,
    promotion_info: str | None = None,
    platform_id: str | None = None,
) -> dict[str, Any]:
    module_id = str(module.get("id"))
    layers = build_text_layers(product_info, module, promotion_info=promotion_info)
    if not layers:
        compliance = await check_project_text_compliance([], platform_id=platform_id, product_info=product_info)
        return {
            "module_id": module_id,
            "url": base_url,
            "base_url": base_url,
            "text_layers": [],
            "language_versions": {},
            "compliance": compliance,
        }

    default_version = await render_layered_language_version(
        base_url=base_url,
        layers=layers,
        language=DEFAULT_LANGUAGE,
        folder=f"generated/{module_id}/languages",
        module_id=module_id,
        platform_id=platform_id,
        product_info=product_info,
    )
    return {
        "module_id": module_id,
        "url": default_version["url"],
        "base_url": base_url,
        "text_layers": layers,
        "language_versions": {DEFAULT_LANGUAGE: default_version},
        "compliance": default_version["compliance"],
    }


def build_fixed_product_composite_prompt(module: dict[str, Any], background_url: str | None = None) -> str:
    background_line = f"参考已生成的背景/版式方向：{background_url}" if background_url else "按当前模块提示词中的背景、版式和文案方向完成画面。"
    return "\n".join(
        [
            "请基于用户上传的产品图制作电商商品图，采用固定产品主体合成模式。",
            "固定产品主体：必须保持产品瓶型、包装颜色、Logo、标签位置、标签文字、图案和比例，不要重绘成另一个相似产品。",
            "可以生成或融合背景、文案区域、氛围装饰、自然投影、接触阴影、环境反光和轻微色温匹配，让产品与画面协调。",
            "不要让背景元素遮挡产品标签，不要生成乱码、水印、虚假品牌或不可读密集小字。",
            f"当前模块：{module.get('name') or module.get('id')}",
            background_line,
        ]
    )


def build_fixed_product_background_prompt(module_prompt: str, module: dict[str, Any]) -> str:
    return "\n".join(
        [
            "【固定产品合成：背景层生成】",
            "本次只生成背景层、场景层、氛围层、道具层和非产品信息图形。",
            "不要生成任何产品瓶身、包装盒、商品实物、Logo、标签文字、品牌字样或相似 SKU。",
            "为后续程序贴入同一个上传产品母版预留自然落位，并准备柔和接触阴影、反光和环境光区域。",
            "画面可以包含电商文案留白、抽象图表、原料、人物、实验室或使用场景，但产品本体必须完全留给程序后期合成。",
            f"当前模块：{module.get('name') or module.get('id')}",
            "",
            module_prompt,
        ]
    )


def _png_data_url(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def _compose_fixed_product_image_url(*, module_id: str, background_url: str, product_url: str, platform_id: str | None = None) -> str:
    background_bytes = await _read_image_bytes(background_url)
    product_bytes = await _read_image_bytes(product_url)
    composed_bytes = compose_fixed_product_image(background_bytes, product_bytes, module_id=module_id, platform_id=platform_id)
    data_url = _png_data_url(composed_bytes)
    return await upload_image_url_if_configured(data_url, f"generated/{module_id}")


async def _generate_module_image(
    *,
    settings: Any,
    product_info: dict[str, Any] | None,
    reference_images: list[str] | None,
    style_reference_images: list[str] | None,
    promotion_info: str | None,
    style: dict[str, Any],
    custom_style: dict[str, Any] | None,
    module: dict[str, Any],
    module_index: int,
    total_modules: int,
    platform_size: str | None = None,
    platform_id: str | None = None,
    image_model_id: str | None = None,
    generation_mode: str = REFERENCE_GENERATE_MODE,
    layered_text: bool = False,
    target_language: str | None = None,
    prompt_branch: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    logger.info("detail image generation start %s/%s module=%s", module_index, total_modules, module["id"])
    module_id = str(module["id"])
    request_size = DETAIL_IMAGE_GENERATION_SIZE if module.get("image_group") == "detail" else platform_size
    if module_id in WHITE_BACKGROUND_MODULE_IDS and reference_images:
        return {"module_id": module_id, "url": reference_images[0]}, None
    fixed_product_mode = generation_mode == FIXED_PRODUCT_COMPOSITE_MODE and bool(reference_images)

    prompt = build_module_image_prompt(
        product_info=product_info,
        style=custom_style or style,
        module=module,
        module_index=module_index,
        total_modules=total_modules,
        promotion_info=promotion_info,
        has_style_reference=bool(style_reference_images),
        text_layer_mode=layered_text,
        target_language=target_language,
        platform_id=platform_id,
        prompt_branch=prompt_branch,
    )
    generation_prompt = build_fixed_product_background_prompt(prompt, module) if fixed_product_mode else prompt
    model_reference_images = _focused_model_reference_images(
        reference_images,
        style_reference_images,
        fixed_product_mode=fixed_product_mode,
    )
    image_settings = resolve_image_settings(settings, image_model_id)
    urls, primary_error = await _call_image_model_with_retry_groups(
        image_settings,
        generation_prompt,
        image=model_reference_images or None,
        size=request_size,
    )

    async def build_generated_image(urls: list[str]) -> dict[str, Any]:
        if fixed_product_mode:
            image_url = await _compose_fixed_product_image_url(
                module_id=module_id,
                background_url=urls[0],
                product_url=reference_images[0],
                platform_id=platform_id,
            )
        else:
            image_url = await upload_image_url_if_configured(urls[0], f"generated/{module_id}")
        if layered_text:
            return await build_layered_generated_image(
                module=module,
                product_info=product_info,
                base_url=image_url,
                promotion_info=promotion_info,
                platform_id=platform_id,
            )
        return {"module_id": module["id"], "url": image_url}

    if urls:
        try:
            image = await build_generated_image(urls)
        except Exception as composite_exc:
            logger.warning("fixed product composite failed %s/%s module=%s error=%s", module_index, total_modules, module["id"], composite_exc)
            return None, f"{module['id']}: fixed product composite failed: {composite_exc}"
        logger.info("detail image generation done %s/%s module=%s", module_index, total_modules, module["id"])
        return image, None

    if image_settings.id == settings.image.id and _image_setting_configured(settings.fallback_image):
        fallback_urls, fallback_error = await _call_image_model_with_retry_groups(
            settings.fallback_image,
            generation_prompt,
            image=model_reference_images or None,
            size=request_size,
        )
        if fallback_urls:
            try:
                image = await build_generated_image(fallback_urls)
            except Exception as composite_exc:
                return None, f"{module['id']}: primary {primary_error}; fallback fixed product composite failed: {composite_exc}"
            logger.info("detail image generation done %s/%s module=%s source=fallback", module_index, total_modules, module["id"])
            return image, None
        return None, f"{module['id']}: primary {primary_error}; fallback {fallback_error}"

    return None, f"{module['id']}: {primary_error}"


async def generate_detail_images(
    module_ids: list[str],
    style_id: str,
    product_info: dict[str, Any] | None = None,
    reference_images: list[str] | None = None,
    style_reference_images: list[str] | None = None,
    custom_style: dict[str, Any] | None = None,
    promotion_info: str | None = None,
    platform_size: str | None = None,
    platform_id: str | None = None,
    image_model_id: str | None = None,
    generation_mode: str | None = REFERENCE_GENERATE_MODE,
    layered_text: bool = False,
    target_language: str | None = None,
    prompt_branch: str | None = None,
    detail_layout_id: str | None = None,
) -> dict[str, Any]:
    settings = get_model_settings()
    image_settings = resolve_image_settings(settings, image_model_id)
    enabled_modules = [module for module in ALL_MODULES if module["id"] in module_ids]
    style = next((item for item in STYLE_OPTIONS if item["id"] == style_id), STYLE_OPTIONS[0])
    normalized_generation_mode = generation_mode or REFERENCE_GENERATE_MODE
    missing_white_background_reference = [
        module for module in enabled_modules if str(module["id"]) in WHITE_BACKGROUND_MODULE_IDS and not reference_images
    ]
    if missing_white_background_reference:
        return {
            "source": "error",
            "images": [],
            "errors": [f"{module['id']}: {WHITE_BACKGROUND_REFERENCE_REQUIRED_ERROR}" for module in missing_white_background_reference],
        }
    if normalized_generation_mode == FIXED_PRODUCT_COMPOSITE_MODE and enabled_modules and not reference_images:
        return {
            "source": "error",
            "images": [],
            "errors": [f"{module['id']}: {FIXED_PRODUCT_REFERENCE_REQUIRED_ERROR}" for module in enabled_modules],
        }

    generated_images: list[dict[str, Any]] = []
    errors: list[str] = []
    if not _image_setting_configured(image_settings) and not _image_setting_configured(settings.fallback_image):
        errors.extend(
            f"{module['id']}: {image_settings.label} ({image_settings.model}) is not configured"
            for module in enabled_modules
            if str(module["id"]) not in WHITE_BACKGROUND_MODULE_IDS
        )
    if _image_setting_configured(image_settings) or _image_setting_configured(settings.fallback_image) or (reference_images and any(str(module["id"]) in WHITE_BACKGROUND_MODULE_IDS for module in enabled_modules)):
        total_modules = len(enabled_modules)
        results = await asyncio.gather(
            *(
                _generate_module_image(
                    settings=settings,
                    product_info=product_info,
                    reference_images=reference_images,
                    style_reference_images=style_reference_images,
                    promotion_info=promotion_info,
                    style=style,
                    custom_style=custom_style,
                    module=module,
                    module_index=index,
                    total_modules=total_modules,
                    platform_size=platform_size,
                    platform_id=platform_id,
                    image_model_id=image_model_id,
                    generation_mode=normalized_generation_mode,
                    layered_text=layered_text,
                    target_language=target_language,
                    prompt_branch=prompt_branch,
                )
                for index, module in enumerate(enabled_modules, start=1)
            )
        )
        for image, error in results:
            if image:
                generated_images.append(image)
            if error:
                errors.append(error)

    if len(generated_images) == len(enabled_modules):
        return {"source": "model", "images": generated_images, "errors": errors}
    if generated_images:
        return {"source": "mixed", "images": generated_images, "errors": errors}

    return {
        "source": "error",
        "images": [],
        "errors": errors or ["image model returned empty content"],
    }


def build_image_edit_prompt(instruction: str) -> str:
    return "\n".join(
        [
            "你是电商商品图后期微调模型。请基于用户提供的原图做局部编辑。",
            "必须尽量保持产品外观、包装文字、Logo、主体比例和整体构图稳定，只修改用户明确提出的细节。",
            "不要新增医疗化功效、虚假品牌、乱码文字或水印。",
            f"用户微调指令：{instruction.strip()}",
        ]
    )


async def edit_generated_image(
    image_url: str,
    instruction: str,
    platform_size: str | None = None,
    image_model_id: str | None = None,
    platform_id: str | None = None,
) -> dict[str, Any]:
    cleaned_instruction = instruction.strip()
    if not image_url:
        return {"source": "error", "error": "image_url is required"}
    if not cleaned_instruction:
        return {"source": "error", "error": "instruction is required"}
    compliance = await check_project_text_compliance(
        [
            {
                "text": cleaned_instruction,
                "location": {"source_type": "edit_instruction", "field": "instruction"},
            }
        ],
        platform_id=platform_id,
    )

    settings = get_model_settings()
    image_settings = resolve_image_settings(settings, image_model_id)
    if not image_settings.api_key and not settings.fallback_image.api_key:
        return {"source": "error", "error": "image model is not configured"}

    prompt = build_image_edit_prompt(cleaned_instruction)

    # Download the source image so we can upload it as a file to the edits endpoint
    try:
        image_bytes = await _read_image_bytes(image_url)
    except Exception as exc:
        return {"source": "error", "error": f"failed to download source image: {exc}"}

    try:
        urls = await call_image_edit_model(image_settings, prompt, image_bytes, size=platform_size)
    except Exception as primary_exc:
        logger.warning("primary image edit failed error=%s", primary_exc)
        if image_settings.id != settings.image.id or not settings.fallback_image.api_key:
            return {"source": "error", "error": str(primary_exc)}
        try:
            urls = await call_image_edit_model(settings.fallback_image, prompt, image_bytes, size=platform_size)
        except Exception as fallback_exc:
            return {"source": "error", "error": f"primary failed: {primary_exc}; fallback failed: {fallback_exc}"}

    if not urls:
        return {"source": "error", "error": "image model returned empty content"}
    url = await upload_image_url_if_configured(urls[0], "edited")
    return {"source": "model", "url": url, "compliance": compliance}


async def _read_image_bytes(url: str) -> bytes:
    if url.startswith("data:"):
        _, _, payload = url.partition(",")
        return base64.b64decode(payload, validate=False)

    if url.startswith(("http://", "https://")):
        import httpx

        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": MODEL_GATEWAY_USER_AGENT})
            response.raise_for_status()
            return response.content

    if url.startswith("/"):
        public_dir = (Path(__file__).resolve().parents[3] / "frontend" / "public").resolve()
        target = (public_dir / url.lstrip("/")).resolve()
        if public_dir not in target.parents and target != public_dir:
            raise ValueError("image path must stay inside frontend public assets")
        return target.read_bytes()

    raise ValueError("unsupported image URL")


def _safe_attachment_filename(filename: str | None, fallback: str) -> str:
    candidate = Path(filename or "").name.strip() or fallback
    candidate = re.sub(r'[\r\n"/\\]+', "_", candidate).strip(" .") or fallback
    return candidate[:180] or fallback


def _attachment_headers(filename: str) -> dict[str, str]:
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii") or "download"
    encoded_filename = quote(filename)
    return {"Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'}


def _image_media_type(content: bytes, filename: str = "") -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"

    extension = Path(filename).suffix.lower()
    if extension in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if extension == ".png":
        return "image/png"
    if extension == ".webp":
        return "image/webp"
    if extension == ".gif":
        return "image/gif"
    return "application/octet-stream"


async def build_image_download_response(url: str, filename: str) -> Response:
    content = await _read_image_bytes(url)
    safe_filename = _safe_attachment_filename(filename, "generated-image.png")
    return Response(
        content=content,
        media_type=_image_media_type(content, safe_filename),
        headers=_attachment_headers(safe_filename),
    )


async def compose_long_jpeg(
    image_urls: list[str],
    target_width: int = 750,
    quality: int = 92,
    on_progress: Callable[[int, int], None] | None = None,
) -> bytes:
    if not image_urls:
        raise ValueError("at least one image is required")

    from PIL import Image

    rendered_images = []
    total = min(len(image_urls), 20)
    for index, url in enumerate(image_urls[:20], start=1):
        if on_progress:
            on_progress(index, total)
        raw = await _read_image_bytes(url)
        with Image.open(BytesIO(raw)) as source:
            image = source.convert("RGB")
            width, height = image.size
            if width <= 0 or height <= 0:
                raise ValueError("image has invalid dimensions")
            next_height = max(1, round(height * (target_width / width)))
            rendered_images.append(image.resize((target_width, next_height), Image.Resampling.LANCZOS))

    total_height = sum(image.height for image in rendered_images)
    canvas = Image.new("RGB", (target_width, total_height), "white")
    top = 0
    for image in rendered_images:
        canvas.paste(image, (0, top))
        top += image.height

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=quality, optimize=True)
    return output.getvalue()


try:
    from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
    from pydantic import BaseModel, Field

    from app.dependencies.auth import require_app_user

    router = APIRouter(prefix="/api/projects", tags=["projects"], dependencies=[Depends(require_app_user)])

    class AnalyzeRequest(BaseModel):
        raw_text: str | None = None

    class MaterialPayload(BaseModel):
        id: str | None = None
        slot: str = "documents"
        filename: str
        content_type: str = "application/octet-stream"
        data_url: str | None = None
        text: str | None = None

    class AnalyzeMaterialsRequest(BaseModel):
        materials: list[MaterialPayload] = Field(default_factory=list)
        detail_layout_id: str | None = DEFAULT_DETAIL_LAYOUT_ID

    class GenerateRequest(BaseModel):
        module_ids: list[str] = Field(default_factory=lambda: [module["id"] for module in DEFAULT_MODULES])
        style_id: str = "space_repair"
        product_info: dict[str, Any] | None = None
        reference_images: list[str] = Field(default_factory=list)
        style_reference_images: list[str] = Field(default_factory=list)
        custom_style: dict[str, Any] | None = None
        promotion_info: str | None = None
        platform_size: str | None = None
        platform_id: str | None = None
        image_model_id: str | None = None
        generation_mode: str | None = REFERENCE_GENERATE_MODE
        layered_text: bool = False
        target_language: str | None = None
        prompt_branch: str | None = None
        detail_layout_id: str | None = DEFAULT_DETAIL_LAYOUT_ID

    class EditImageRequest(BaseModel):
        image_url: str
        instruction: str
        platform_size: str | None = None
        image_model_id: str | None = None
        platform_id: str | None = None

    def _generation_payload_from_request(request: GenerateRequest) -> dict[str, Any]:
        return {
            "module_ids": list(request.module_ids),
            "style_id": request.style_id,
            "product_info": request.product_info,
            "reference_images": list(request.reference_images),
            "style_reference_images": list(request.style_reference_images),
            "custom_style": request.custom_style,
            "promotion_info": request.promotion_info,
            "platform_size": request.platform_size,
            "platform_id": request.platform_id,
            "image_model_id": request.image_model_id,
            "generation_mode": request.generation_mode,
            "layered_text": request.layered_text,
            "target_language": request.target_language,
            "prompt_branch": request.prompt_branch,
            "detail_layout_id": request.detail_layout_id,
        }

    def _edit_payload_from_request(request: EditImageRequest) -> dict[str, Any]:
        return {
            "image_url": request.image_url,
            "instruction": request.instruction,
            "platform_size": request.platform_size,
            "image_model_id": request.image_model_id,
            "platform_id": request.platform_id,
        }

    async def run_generation_job(job_id: str, payload: dict[str, Any]) -> None:
        job = GENERATION_JOBS.get(job_id)
        if not job:
            return
        module_ids = list(payload.get("module_ids") or [])
        total = len(module_ids)
        try:
            job.update(
                {
                    "status": "running",
                    "stage": "generating",
                    "current": 0,
                    "total": total,
                    "message": "正在生成图片",
                }
            )
            result = await generate_detail_images(
                module_ids,
                payload.get("style_id") or "space_repair",
                product_info=payload.get("product_info"),
                reference_images=payload.get("reference_images") or [],
                style_reference_images=payload.get("style_reference_images") or [],
                custom_style=payload.get("custom_style"),
                promotion_info=payload.get("promotion_info"),
                platform_size=payload.get("platform_size"),
                platform_id=payload.get("platform_id"),
                image_model_id=payload.get("image_model_id"),
                generation_mode=payload.get("generation_mode") or REFERENCE_GENERATE_MODE,
                layered_text=bool(payload.get("layered_text")),
                target_language=payload.get("target_language"),
                prompt_branch=payload.get("prompt_branch"),
                detail_layout_id=payload.get("detail_layout_id"),
            )
            job.update(
                {
                    "status": "done",
                    "stage": "done",
                    "current": total,
                    "total": total,
                    "message": "图片生成完成",
                    "result": result,
                }
            )
        except Exception as exc:
            job.update({"status": "error", "stage": "error", "message": str(exc), "error": str(exc)})

    async def run_edit_job(job_id: str, payload: dict[str, Any]) -> None:
        job = EDIT_JOBS.get(job_id)
        if not job:
            return
        try:
            job.update(
                {
                    "status": "running",
                    "stage": "editing",
                    "current": 0,
                    "total": 1,
                    "message": "正在微调图片",
                }
            )
            result = await edit_generated_image(
                payload.get("image_url") or "",
                payload.get("instruction") or "",
                platform_size=payload.get("platform_size"),
                image_model_id=payload.get("image_model_id"),
                platform_id=payload.get("platform_id"),
            )
            job.update(
                {
                    "status": "done",
                    "stage": "done",
                    "current": 1,
                    "total": 1,
                    "message": "图片微调完成",
                    "result": result,
                }
            )
        except Exception as exc:
            job.update({"status": "error", "stage": "error", "message": str(exc), "error": str(exc)})

    class PlanStyleRequest(BaseModel):
        product_info: dict[str, Any] | None = None
        product_images: list[MaterialPayload] = Field(default_factory=list)

    class AnalyzeStyleReferenceRequest(BaseModel):
        product_info: dict[str, Any] | None = None
        style_reference_images: list[MaterialPayload] = Field(default_factory=list)

    class PlanStyleSampleRequest(BaseModel):
        style: dict[str, Any]
        product_info: dict[str, Any] | None = None

    class RenderLanguageRequest(BaseModel):
        base_url: str
        text_layers: list[dict[str, Any]] = Field(default_factory=list)
        language: str = DEFAULT_LANGUAGE
        platform_id: str | None = None
        product_info: dict[str, Any] | None = None

    class DownloadImageRequest(BaseModel):
        url: str
        filename: str = "generated-image.png"

    class ComplianceLocationPayload(BaseModel):
        source_type: str = "field"
        module_id: str = ""
        field: str = ""
        language: str = DEFAULT_LANGUAGE

    class ComplianceTextItemPayload(BaseModel):
        text: str = ""
        location: ComplianceLocationPayload = Field(default_factory=ComplianceLocationPayload)

    class ComplianceCheckTextRequest(BaseModel):
        items: list[ComplianceTextItemPayload] = Field(default_factory=list)
        platform_id: str | None = None
        product_info: dict[str, Any] | None = None
        debug: bool = False

    class ComplianceCheckImagesRequest(BaseModel):
        image_urls: list[str] = Field(default_factory=list)
        platform_id: str | None = None
        product_info: dict[str, Any] | None = None
        debug: bool = False

    class ComposeImageItem(BaseModel):
        module_id: str
        module_name: str = ""
        url: str

    class ComposeLongImageRequest(BaseModel):
        images: list[ComposeImageItem] = Field(default_factory=list)

    class PrepareComposeImagesRequest(BaseModel):
        images: list[ComposeImageItem] = Field(default_factory=list)

    @router.post("")
    async def create_project() -> dict[str, Any]:
        return {
            "project": create_demo_project(),
            "styles": STYLE_OPTIONS,
            "modules": DEFAULT_MODULES,
            "detail_layouts": DETAIL_LAYOUTS,
            "default_detail_layout_id": DEFAULT_DETAIL_LAYOUT_ID,
        }

    @router.get("/defaults")
    async def get_project_defaults() -> dict[str, Any]:
        return {"styles": STYLE_OPTIONS, "modules": DEFAULT_MODULES, "detail_layouts": DETAIL_LAYOUTS, "default_detail_layout_id": DEFAULT_DETAIL_LAYOUT_ID}

    @router.post("/analyze")
    async def analyze_project(request: AnalyzeRequest) -> dict[str, Any]:
        return await analyze_product_materials(request.raw_text)

    @router.post("/analyze-materials")
    async def analyze_project_materials(request: AnalyzeMaterialsRequest) -> dict[str, Any]:
        materials = [uploaded_material_from_payload(payload) for payload in request.materials[:8]]
        return await analyze_uploaded_materials(materials, detail_layout_id=request.detail_layout_id)

    @router.post("/plan-style")
    async def plan_project_style(request: PlanStyleRequest) -> dict[str, Any]:
        product_images = [uploaded_material_from_payload(payload) for payload in request.product_images[:3]]
        return await plan_custom_style(request.product_info, product_images=product_images)

    @router.post("/analyze-style-reference")
    async def analyze_project_style_reference(request: AnalyzeStyleReferenceRequest) -> dict[str, Any]:
        style_reference_images = [uploaded_material_from_payload(payload) for payload in request.style_reference_images[:4]]
        return await analyze_style_reference(request.product_info, style_reference_images)

    @router.post("/plan-style-sample")
    async def plan_project_style_sample(request: PlanStyleSampleRequest) -> dict[str, Any]:
        return await generate_custom_style_sample(request.style, request.product_info)

    @router.post("/generate")
    async def generate_project(request: GenerateRequest) -> dict[str, Any]:
        return await generate_detail_images(
            request.module_ids,
            request.style_id,
            product_info=request.product_info,
            reference_images=request.reference_images,
            style_reference_images=request.style_reference_images,
            custom_style=request.custom_style,
            promotion_info=request.promotion_info,
            platform_size=request.platform_size,
            platform_id=request.platform_id,
            image_model_id=request.image_model_id,
            generation_mode=request.generation_mode,
            layered_text=request.layered_text,
            target_language=request.target_language,
            prompt_branch=request.prompt_branch,
            detail_layout_id=request.detail_layout_id,
        )

    @router.post("/generate/jobs")
    async def create_generate_project_job(request: GenerateRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
        _cleanup_expired_generation_jobs()
        payload = _generation_payload_from_request(request)
        job_id = f"generate_{uuid4().hex}"
        GENERATION_JOBS[job_id] = {
            "status": "pending",
            "stage": "pending",
            "current": 0,
            "total": len(payload["module_ids"]),
            "message": "等待开始生成",
            "created_at": datetime.now(UTC).isoformat(),
        }
        background_tasks.add_task(run_generation_job, job_id, payload)
        return {"job_id": job_id}

    @router.get("/generate/jobs/{job_id}")
    async def get_generate_project_job(job_id: str) -> dict[str, Any]:
        job = GENERATION_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="generation job not found")
        return job

    @router.post("/edit-image")
    async def edit_project_image(request: EditImageRequest) -> dict[str, Any]:
        return await edit_generated_image(
            request.image_url,
            request.instruction,
            platform_size=request.platform_size,
            image_model_id=request.image_model_id,
            platform_id=request.platform_id,
        )

    @router.post("/edit-image/jobs")
    async def create_edit_project_image_job(request: EditImageRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
        _cleanup_expired_edit_jobs()
        payload = _edit_payload_from_request(request)
        job_id = f"edit_{uuid4().hex}"
        EDIT_JOBS[job_id] = {
            "status": "pending",
            "stage": "pending",
            "current": 0,
            "total": 1,
            "message": "等待开始微调",
            "created_at": datetime.now(UTC).isoformat(),
        }
        background_tasks.add_task(run_edit_job, job_id, payload)
        return {"job_id": job_id}

    @router.get("/edit-image/jobs/{job_id}")
    async def get_edit_project_image_job(job_id: str) -> dict[str, Any]:
        job = EDIT_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="edit job not found")
        return job

    @router.post("/render-language")
    async def render_project_language(request: RenderLanguageRequest) -> dict[str, Any]:
        if not request.base_url:
            return {"source": "error", "error": "base_url is required"}
        if not request.text_layers:
            return {"source": "error", "error": "text_layers is required"}
        try:
            version = await render_layered_language_version(
                base_url=request.base_url,
                layers=request.text_layers,
                language=request.language,
                platform_id=request.platform_id,
                product_info=request.product_info,
            )
        except Exception as exc:
            return {"source": "error", "error": str(exc)}
        return {"source": "model", **version}

    @router.post("/compliance/check-text")
    async def check_project_text_compliance_endpoint(request: ComplianceCheckTextRequest) -> dict[str, Any]:
        items = [{"text": item.text, "location": item.location.model_dump()} for item in request.items]
        return await check_project_text_compliance(
            items,
            platform_id=request.platform_id,
            product_info=request.product_info,
            debug=request.debug,
        )

    @router.post("/compliance/check-images")
    async def check_project_image_compliance_endpoint(request: ComplianceCheckImagesRequest) -> dict[str, Any]:
        return await check_project_image_compliance(
            request.image_urls,
            platform_id=request.platform_id,
            product_info=request.product_info,
            debug=request.debug,
        )

    @router.post("/download-image")
    async def download_project_image(request: DownloadImageRequest) -> Response:
        try:
            return await build_image_download_response(request.url, request.filename)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/compose-long-image")
    async def compose_project_long_image(request: ComposeLongImageRequest) -> Response:
        try:
            jpeg = await compose_long_jpeg([image.url for image in request.images])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers=_attachment_headers("full-detail.jpg"),
        )

    @router.post("/compose-long-image/prepare")
    async def prepare_compose_project_images(request: PrepareComposeImagesRequest) -> dict[str, list[dict[str, str]]]:
        try:
            prepared_urls = await prepare_compose_image_urls([image.url for image in request.images])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "images": [
                {"module_id": image.module_id, "module_name": image.module_name, "url": prepared_urls[index]}
                for index, image in enumerate(request.images[:20])
            ]
        }

    async def run_compose_job(job_id: str, image_urls: list[str]) -> None:
        def update_progress(current: int, total: int) -> None:
            COMPOSE_JOBS[job_id].update(
                {
                    "status": "running",
                    "stage": "downloading",
                    "current": current,
                    "total": total,
                    "message": f"正在下载第 {current}/{total} 张",
                }
            )

        try:
            COMPOSE_JOBS[job_id].update({"status": "running", "stage": "starting", "message": "正在准备合成"})
            jpeg = await compose_long_jpeg(image_urls, on_progress=update_progress)
            uploaded_url = await upload_bytes_if_configured(
                jpeg,
                content_type="image/jpeg",
                folder="composed",
                extension="jpg",
            )
            COMPOSE_JOBS[job_id].update(
                {
                    "status": "done",
                    "stage": "done",
                    "current": len(image_urls[:20]),
                    "total": len(image_urls[:20]),
                    "message": "合成完成，正在下载",
                    "content": b"" if uploaded_url else jpeg,
                    "url": uploaded_url,
                }
            )
        except Exception as exc:
            COMPOSE_JOBS[job_id].update({"status": "error", "stage": "error", "message": str(exc), "error": str(exc)})

    @router.post("/compose-long-image/jobs")
    async def create_compose_project_long_image_job(request: ComposeLongImageRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
        raw_image_urls = [image.url for image in request.images]
        if not raw_image_urls:
            raise HTTPException(status_code=400, detail="at least one image is required")
        _cleanup_expired_compose_jobs()
        try:
            image_urls = await prepare_compose_image_urls(raw_image_urls)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job_id = f"compose_{uuid4().hex}"
        COMPOSE_JOBS[job_id] = {
            "status": "pending",
            "stage": "pending",
            "current": 0,
            "total": min(len(image_urls), 20),
            "message": "等待开始合成",
            "content": b"",
            "created_at": datetime.now(UTC).isoformat(),
        }
        background_tasks.add_task(run_compose_job, job_id, image_urls[:20])
        return {"job_id": job_id}

    @router.get("/compose-long-image/jobs/{job_id}")
    async def get_compose_project_long_image_job(job_id: str) -> dict[str, Any]:
        job = COMPOSE_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="compose job not found")
        return {key: value for key, value in job.items() if key != "content"}

    @router.get("/compose-long-image/jobs/{job_id}/download", response_model=None)
    async def download_compose_project_long_image_job(job_id: str) -> Response | dict[str, str]:
        job = COMPOSE_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="compose job not found")
        if job.get("status") != "done" or (not job.get("content") and not job.get("url")):
            raise HTTPException(status_code=409, detail="compose job is not ready")
        if job.get("url"):
            return await build_image_download_response(str(job["url"]), "full-detail.jpg")
        content = job["content"]
        # Free the binary content from memory after download
        job["content"] = b""
        return Response(
            content=content,
            media_type="image/jpeg",
            headers=_attachment_headers("full-detail.jpg"),
        )

except ModuleNotFoundError:
    router = None
