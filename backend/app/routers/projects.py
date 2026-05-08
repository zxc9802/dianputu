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

from app.core.config import get_model_settings
from app.demo_data import DEFAULT_MODULES, DEMO_IMAGE_URLS, STYLE_OPTIONS
from app.services.image_model import call_image_edit_model, call_image_model
from app.services.object_storage import upload_bytes_to_object_storage, upload_data_url_to_object_storage
from app.services.prompt_builder import build_module_image_prompt
from app.services.text_model import call_text_model


logger = logging.getLogger("detail_image_generation")
MODEL_GATEWAY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
WHITE_BACKGROUND_MODULE_IDS = {"main_white_bg", "campaign_white_bg"}
STYLE_SAMPLE_IMAGE_SIZE = "1024x1024"
GENERATION_JOBS: dict[str, dict[str, Any]] = {}
GENERATION_JOB_TTL_SECONDS = 3600  # 1 hour
COMPOSE_JOBS: dict[str, dict[str, Any]] = {}
COMPOSE_JOB_TTL_SECONDS = 600  # 10 minutes
WHITE_BACKGROUND_REFERENCE_REQUIRED_ERROR = "白底图需要先上传产品图，系统会直接复用上传图以避免模型重绘导致包装、Logo 或瓶身变形。"


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


def _data_uri(material: UploadedMaterial) -> str:
    if material.data_url:
        return material.data_url
    encoded = base64.b64encode(material.data).decode("ascii")
    return f"data:{material.content_type};base64,{encoded}"


def uploaded_material_from_payload(payload: Any) -> UploadedMaterial:
    content_type = payload.content_type or "application/octet-stream"
    data = b""
    if payload.data_url:
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
    )


def build_material_analysis_messages(materials: list[UploadedMaterial]) -> list[dict[str, Any]]:
    file_lines = "\n".join(
        f"- [{material.slot}] {material.filename} ({material.content_type or 'unknown'}, {len(material.data)} bytes)"
        for material in materials
    )
    prompt = (
        "你是电商护肤详情页产品经理。请根据上传的产品主图和资料，提取商品详情页生成所需信息。"
        "必须只输出 JSON，不要输出解释文字。字段包括：product_name, category, spec, "
        "core_selling_points, functions, ingredients, target_users, usage_method, authority_assets, effect_claims。"
        "如果图片或资料里无法确定，请基于护肤品详情页常识给出谨慎的 AI 补全，并避免绝对化医疗功效。"
        f"\n上传文件：\n{file_lines}"
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for material in materials:
        if material.content_type.startswith("image/") and material.data:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(material)}})
        elif material.content_type == "application/pdf" and material.data:
            content.append({"type": "file", "file": {"filename": material.filename, "file_data": _data_uri(material)}})
        elif material.data:
            text = (material.text or material.data[:12000].decode("utf-8", errors="ignore")).strip()
            if text:
                content.append({"type": "text", "text": f"{material.filename} 内容摘录：\n{text}"})
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


def _ingredients(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            benefit = str(item.get("benefit", "")).strip() or "辅助日常肌肤护理"
            if name:
                normalized.append({"name": name, "benefit": benefit})
        elif str(item).strip():
            normalized.append({"name": str(item).strip(), "benefit": "辅助日常肌肤护理"})
    return normalized


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


def normalize_product_info_from_model(raw: str) -> dict[str, Any]:
    data = _extract_json_object(raw) or {}
    return {
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
        "confirmation_status": "pending",
    }


def normalize_style_plan_from_model(raw: str) -> dict[str, Any]:
    data = _extract_json_object(raw) or {}
    keywords = _string_list(data.get("keywords"), [])
    return {
        "id": "ai_custom",
        "name": str(data.get("name") or "AI 自定义风格").strip() or "AI 自定义风格",
        "primary_color": str(data.get("primary_color") or "#1F8C43").strip() or "#1F8C43",
        "keywords": keywords[:6] or ["产品定制", "电商高级", "统一视觉"],
        "asset": "",
        "visual_direction": str(data.get("visual_direction") or "根据产品定位生成统一视觉方向").strip(),
        "layout_guidance": str(data.get("layout_guidance") or "主图突出产品，详情页按模块建立统一版式系统").strip(),
        "reasoning": str(data.get("reasoning") or "基于产品信息、品类和包装色规划").strip(),
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
    prompt = "\n".join(
        [
            "你是资深电商美术指导。请基于产品资料和产品图，全权规划一个全新的电商视觉风格。",
            "不要从现有三套预设风格里选择，也不要只输出绿色修护、蓝色补水、金色抗老这类模板名。",
            "不要依赖前置颜色提取；请直接观察产品图，综合包装、质地、品类、价格感和卖点来决定主色、辅助气质和视觉语言。",
            "必须只输出 JSON，不要输出解释文字。",
            "JSON 字段：name, primary_color, keywords, visual_direction, layout_guidance, reasoning。",
            "要求：name 是 6-12 个中文字符的风格名；primary_color 是十六进制颜色；keywords 是 3-6 个短词。",
            "visual_direction 写清楚色调、材质、光影、氛围；layout_guidance 写清楚主图和详情页如何保持统一但模块差异化。",
            "避免医疗化、绝对化功效，不编造品牌授权或真实机构背书。",
            category_line,
            f"产品信息 JSON：{json.dumps(info, ensure_ascii=False)}",
        ]
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for material in (product_images or [])[:3]:
        if material.content_type.startswith("image/") and material.data:
            content.append({"type": "image_url", "image_url": {"url": _data_uri(material)}})
    return [{"role": "user", "content": content}]


def _plain_text(value: Any, fallback: str) -> str:
    cleaned = str(value or "").strip()
    return cleaned or fallback


def build_custom_style_sample_prompt(style: dict[str, Any], product_info: dict[str, Any] | None) -> str:
    info = product_info or {}
    keywords = " / ".join(_string_list(style.get("keywords"), [])) or "高级 / 干净 / 统一"
    return "\n".join(
        [
            "请生成 1 张中文电商护肤视觉风格样例图，用来预览 AI 规划的风格方向。",
            "这不是最终商品图，不需要完全复刻用户产品包装，也不要生成真实品牌 Logo、可识别商标或可读包装小字。",
            "画面可以使用无品牌护肤瓶/面霜罐/精华瓶作为通用占位产品，重点展示色调、材质、光影、氛围和版式。",
            f"- 参考产品：{_plain_text(info.get('product_name'), '护肤品')}",
            f"- 品类：{_plain_text(info.get('category'), '护肤品')}",
            f"- 风格名称：{_plain_text(style.get('name'), 'AI 自定义风格')}",
            f"- 主色：{_plain_text(style.get('primary_color'), '#F4F1EC')}",
            f"- 视觉关键词：{keywords}",
            f"- 视觉方向：{_plain_text(style.get('visual_direction'), '高级、干净、统一')}",
            f"- 版式方向：{_plain_text(style.get('layout_guidance'), '主图突出产品，详情页模块化')}",
            "构图要求：16:10 横向风格卡片封面，中央或偏左放通用护肤品占位，背景呈现规划风格的材质与光影。",
            "文字要求：最多只放 2-4 个大的中文风格关键词，不能出现乱码、密集小字、水印或平台 UI。",
        ]
    )


def create_demo_project() -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "id": f"project_{uuid4().hex[:8]}",
        "name": "新建商品详情页",
        "product_category": "待 AI 解析",
        "style_id": "green_repair",
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
            "ingredients, target_users, usage_method, authority_assets, effect_claims。"
            f"\n资料：{raw_text}"
        )
        content = await call_text_model_with_retry(settings, [{"role": "user", "content": prompt}])
        if content:
            return {"source": "model", "raw": content, "product_info": normalize_product_info_from_model(content)}
    return {"source": "error", "error": "text model is not configured or no raw text was provided"}


async def analyze_uploaded_materials(materials: list[UploadedMaterial]) -> dict[str, Any]:
    settings = get_model_settings()
    if not materials:
        return {"source": "error", "error": "no materials were uploaded"}
    if not settings.text.api_key:
        return {"source": "error", "error": "text model is not configured"}

    try:
        model_materials: list[UploadedMaterial] = []
        for material in materials:
            if material.content_type.startswith("image/") and material.data:
                image_url = await upload_material_image_if_configured(material)
                model_materials.append(
                    UploadedMaterial(
                        filename=material.filename,
                        content_type=material.content_type,
                        data=material.data,
                        slot=material.slot,
                        text=material.text,
                        data_url=image_url,
                    )
                )
            else:
                model_materials.append(material)
        content = await call_text_model_with_retry(settings, build_material_analysis_messages(model_materials))
    except Exception as exc:
        return {"source": "error", "error": str(exc)}
    if not content:
        return {"source": "error", "error": "text model returned empty content"}

    return {"source": "model", "product_info": normalize_product_info_from_model(content), "raw": content}


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
            if material.content_type.startswith("image/") and material.data:
                image_url = await upload_material_image_if_configured(material)
                model_images.append(
                    UploadedMaterial(
                        filename=material.filename,
                        content_type=material.content_type,
                        data=material.data,
                        slot=material.slot,
                        text=material.text,
                        data_url=image_url,
                    )
                )
        content = await call_text_model_with_retry(settings, build_style_planning_messages(product_info, category, model_images))
    except Exception as exc:
        return {"source": "error", "error": str(exc)}
    if not content:
        return {"source": "error", "error": "text model returned empty content"}

    style = normalize_style_plan_from_model(content)
    return {"source": "model", "style": style, "raw": content, "warnings": []}


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
    image_model_id: str | None = None,
) -> tuple[dict[str, str] | None, str | None]:
    logger.info("detail image generation start %s/%s module=%s", module_index, total_modules, module["id"])
    module_id = str(module["id"])
    if module_id in WHITE_BACKGROUND_MODULE_IDS and reference_images:
        return {"module_id": module_id, "url": reference_images[0]}, None
    model_reference_images = [
        *(reference_images or []),
        *(style_reference_images or []),
    ]

    prompt = build_module_image_prompt(
        product_info=product_info,
        style=custom_style or style,
        module=module,
        module_index=module_index,
        total_modules=total_modules,
        promotion_info=promotion_info,
        has_style_reference=bool(style_reference_images),
    )
    image_settings = settings.image_options.get(image_model_id or settings.image.id, settings.image)
    try:
        urls = await call_image_model(image_settings, prompt, image=model_reference_images or None, size=platform_size)
    except Exception as primary_exc:
        logger.warning("primary image generation failed %s/%s module=%s error=%s", module_index, total_modules, module["id"], primary_exc)
        if image_settings.id != settings.image.id or not settings.fallback_image.api_key:
            return None, f"{module['id']}: {primary_exc}"
        try:
            urls = await call_image_model(settings.fallback_image, prompt, image=model_reference_images or None, size=platform_size)
        except Exception as fallback_exc:
            logger.warning("fallback image generation failed %s/%s module=%s error=%s", module_index, total_modules, module["id"], fallback_exc)
            return None, f"{module['id']}: primary failed: {primary_exc}; fallback failed: {fallback_exc}"

    if urls:
        image_url = await upload_image_url_if_configured(urls[0], f"generated/{module_id}")
        logger.info("detail image generation done %s/%s module=%s", module_index, total_modules, module["id"])
        return {"module_id": module["id"], "url": image_url}, None
    return None, None


async def generate_detail_images(
    module_ids: list[str],
    style_id: str,
    product_info: dict[str, Any] | None = None,
    reference_images: list[str] | None = None,
    style_reference_images: list[str] | None = None,
    custom_style: dict[str, Any] | None = None,
    promotion_info: str | None = None,
    platform_size: str | None = None,
    image_model_id: str | None = None,
) -> dict[str, Any]:
    settings = get_model_settings()
    image_settings = settings.image_options.get(image_model_id or settings.image.id, settings.image)
    enabled_modules = [module for module in DEFAULT_MODULES if module["id"] in module_ids]
    style = next((item for item in STYLE_OPTIONS if item["id"] == style_id), STYLE_OPTIONS[0])
    missing_white_background_reference = [
        module for module in enabled_modules if str(module["id"]) in WHITE_BACKGROUND_MODULE_IDS and not reference_images
    ]
    if missing_white_background_reference:
        return {
            "source": "error",
            "images": [],
            "errors": [f"{module['id']}: {WHITE_BACKGROUND_REFERENCE_REQUIRED_ERROR}" for module in missing_white_background_reference],
        }

    generated_images: list[dict[str, str]] = []
    errors: list[str] = []
    if image_settings.api_key or settings.fallback_image.api_key or (reference_images and any(str(module["id"]) in WHITE_BACKGROUND_MODULE_IDS for module in enabled_modules)):
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
                    image_model_id=image_model_id,
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
        image_urls_by_module = {image["module_id"]: image["url"] for image in generated_images}
        ordered_images = [
            {"module_id": module["id"], "url": image_urls_by_module.get(module["id"], DEMO_IMAGE_URLS[module["id"]])}
            for module in enabled_modules
        ]
        return {"source": "mixed", "images": ordered_images, "errors": errors}

    return {
        "source": "demo",
        "images": [{"module_id": module["id"], "url": DEMO_IMAGE_URLS[module["id"]]} for module in enabled_modules],
        "errors": errors,
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


async def edit_generated_image(image_url: str, instruction: str, platform_size: str | None = None, image_model_id: str | None = None) -> dict[str, Any]:
    cleaned_instruction = instruction.strip()
    if not image_url:
        return {"source": "error", "error": "image_url is required"}
    if not cleaned_instruction:
        return {"source": "error", "error": "instruction is required"}

    settings = get_model_settings()
    image_settings = settings.image_options.get(image_model_id or settings.image.id, settings.image)
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
    return {"source": "model", "url": url}


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
        slot: str = "documents"
        filename: str
        content_type: str = "application/octet-stream"
        data_url: str | None = None
        text: str | None = None

    class AnalyzeMaterialsRequest(BaseModel):
        materials: list[MaterialPayload] = Field(default_factory=list)

    class GenerateRequest(BaseModel):
        module_ids: list[str] = Field(default_factory=lambda: [module["id"] for module in DEFAULT_MODULES])
        style_id: str = "green_repair"
        product_info: dict[str, Any] | None = None
        reference_images: list[str] = Field(default_factory=list)
        style_reference_images: list[str] = Field(default_factory=list)
        custom_style: dict[str, Any] | None = None
        promotion_info: str | None = None
        platform_size: str | None = None
        image_model_id: str | None = None

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
            "image_model_id": request.image_model_id,
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
                payload.get("style_id") or "green_repair",
                product_info=payload.get("product_info"),
                reference_images=payload.get("reference_images") or [],
                style_reference_images=payload.get("style_reference_images") or [],
                custom_style=payload.get("custom_style"),
                promotion_info=payload.get("promotion_info"),
                platform_size=payload.get("platform_size"),
                image_model_id=payload.get("image_model_id"),
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

    class PlanStyleRequest(BaseModel):
        product_info: dict[str, Any] | None = None
        product_images: list[MaterialPayload] = Field(default_factory=list)

    class PlanStyleSampleRequest(BaseModel):
        style: dict[str, Any]
        product_info: dict[str, Any] | None = None

    class EditImageRequest(BaseModel):
        image_url: str
        instruction: str
        platform_size: str | None = None
        image_model_id: str | None = None

    class DownloadImageRequest(BaseModel):
        url: str
        filename: str = "generated-image.png"

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
        return {"project": create_demo_project(), "styles": STYLE_OPTIONS, "modules": DEFAULT_MODULES}

    @router.get("/defaults")
    async def get_project_defaults() -> dict[str, Any]:
        return {"styles": STYLE_OPTIONS, "modules": DEFAULT_MODULES}

    @router.post("/analyze")
    async def analyze_project(request: AnalyzeRequest) -> dict[str, Any]:
        return await analyze_product_materials(request.raw_text)

    @router.post("/analyze-materials")
    async def analyze_project_materials(request: AnalyzeMaterialsRequest) -> dict[str, Any]:
        materials = [uploaded_material_from_payload(payload) for payload in request.materials[:8]]
        return await analyze_uploaded_materials(materials)

    @router.post("/plan-style")
    async def plan_project_style(request: PlanStyleRequest) -> dict[str, Any]:
        product_images = [uploaded_material_from_payload(payload) for payload in request.product_images[:3]]
        return await plan_custom_style(request.product_info, product_images=product_images)

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
            image_model_id=request.image_model_id,
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
        return await edit_generated_image(request.image_url, request.instruction, platform_size=request.platform_size, image_model_id=request.image_model_id)

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
