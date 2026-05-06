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
from uuid import uuid4

from app.core.config import get_model_settings
from app.demo_data import DEFAULT_MODULES, DEMO_IMAGE_URLS, STYLE_OPTIONS
from app.services.image_model import call_image_model
from app.services.prompt_builder import build_module_image_prompt
from app.services.text_model import call_text_model


logger = logging.getLogger("detail_image_generation")
MODEL_GATEWAY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
WHITE_BACKGROUND_MODULE_IDS = {"main_white_bg", "campaign_white_bg"}
COMPOSE_JOBS: dict[str, dict[str, Any]] = {}


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
            benefit = str(item.get("benefit", "")).strip() or "AI 待确认"
            if name:
                normalized.append({"name": name, "benefit": benefit})
        elif str(item).strip():
            normalized.append({"name": str(item).strip(), "benefit": "AI 待确认"})
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
        content = await call_text_model(settings.text, [{"role": "user", "content": prompt}])
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
        content = await call_text_model(settings.text, build_material_analysis_messages(materials))
    except Exception as exc:
        return {"source": "error", "error": str(exc)}
    if not content:
        return {"source": "error", "error": "text model returned empty content"}

    return {"source": "model", "product_info": normalize_product_info_from_model(content), "raw": content}


async def _generate_module_image(
    *,
    settings: Any,
    product_info: dict[str, Any] | None,
    reference_images: list[str] | None,
    promotion_info: str | None,
    style: dict[str, Any],
    module: dict[str, Any],
    module_index: int,
    total_modules: int,
) -> tuple[dict[str, str] | None, str | None]:
    logger.info("detail image generation start %s/%s module=%s", module_index, total_modules, module["id"])
    module_id = str(module["id"])
    if module_id in WHITE_BACKGROUND_MODULE_IDS and reference_images:
        return {"module_id": module_id, "url": reference_images[0]}, None

    prompt = build_module_image_prompt(
        product_info=product_info,
        style=style,
        module=module,
        module_index=module_index,
        total_modules=total_modules,
        promotion_info=promotion_info,
    )
    try:
        urls = await call_image_model(settings.image, prompt, image=reference_images)
    except Exception as primary_exc:
        logger.warning("primary image generation failed %s/%s module=%s error=%s", module_index, total_modules, module["id"], primary_exc)
        if not settings.fallback_image.api_key:
            return None, f"{module['id']}: {primary_exc}"
        try:
            urls = await call_image_model(settings.fallback_image, prompt, image=reference_images)
        except Exception as fallback_exc:
            logger.warning("fallback image generation failed %s/%s module=%s error=%s", module_index, total_modules, module["id"], fallback_exc)
            return None, f"{module['id']}: primary failed: {primary_exc}; fallback failed: {fallback_exc}"

    if urls:
        logger.info("detail image generation done %s/%s module=%s", module_index, total_modules, module["id"])
        return {"module_id": module["id"], "url": urls[0]}, None
    return None, None


async def generate_detail_images(
    module_ids: list[str],
    style_id: str,
    product_info: dict[str, Any] | None = None,
    reference_images: list[str] | None = None,
    promotion_info: str | None = None,
) -> dict[str, Any]:
    settings = get_model_settings()
    enabled_modules = [module for module in DEFAULT_MODULES if module["id"] in module_ids]
    style = next((item for item in STYLE_OPTIONS if item["id"] == style_id), STYLE_OPTIONS[0])

    generated_images: list[dict[str, str]] = []
    errors: list[str] = []
    if settings.image.api_key or settings.fallback_image.api_key or (reference_images and any(str(module["id"]) in WHITE_BACKGROUND_MODULE_IDS for module in enabled_modules)):
        total_modules = len(enabled_modules)
        results = await asyncio.gather(
            *(
                _generate_module_image(
                    settings=settings,
                    product_info=product_info,
                    reference_images=reference_images,
                    promotion_info=promotion_info,
                    style=style,
                    module=module,
                    module_index=index,
                    total_modules=total_modules,
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
    from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
    from pydantic import BaseModel, Field

    router = APIRouter(prefix="/api/projects", tags=["projects"])

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
        promotion_info: str | None = None

    class ComposeImageItem(BaseModel):
        module_id: str
        module_name: str = ""
        url: str

    class ComposeLongImageRequest(BaseModel):
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

    @router.post("/generate")
    async def generate_project(request: GenerateRequest) -> dict[str, Any]:
        return await generate_detail_images(
            request.module_ids,
            request.style_id,
            product_info=request.product_info,
            reference_images=request.reference_images,
            promotion_info=request.promotion_info,
        )

    @router.post("/compose-long-image")
    async def compose_project_long_image(request: ComposeLongImageRequest) -> Response:
        try:
            jpeg = await compose_long_jpeg([image.url for image in request.images])
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Content-Disposition": 'attachment; filename="full-detail.jpg"'},
        )

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
            COMPOSE_JOBS[job_id].update(
                {
                    "status": "done",
                    "stage": "done",
                    "current": len(image_urls[:20]),
                    "total": len(image_urls[:20]),
                    "message": "合成完成，正在下载",
                    "content": jpeg,
                }
            )
        except Exception as exc:
            COMPOSE_JOBS[job_id].update({"status": "error", "stage": "error", "message": str(exc), "error": str(exc)})

    @router.post("/compose-long-image/jobs")
    async def create_compose_project_long_image_job(request: ComposeLongImageRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
        image_urls = [image.url for image in request.images]
        if not image_urls:
            raise HTTPException(status_code=400, detail="at least one image is required")
        job_id = f"compose_{uuid4().hex}"
        COMPOSE_JOBS[job_id] = {
            "status": "pending",
            "stage": "pending",
            "current": 0,
            "total": min(len(image_urls), 20),
            "message": "等待开始合成",
            "content": b"",
        }
        background_tasks.add_task(run_compose_job, job_id, image_urls[:20])
        return {"job_id": job_id}

    @router.get("/compose-long-image/jobs/{job_id}")
    async def get_compose_project_long_image_job(job_id: str) -> dict[str, Any]:
        job = COMPOSE_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="compose job not found")
        return {key: value for key, value in job.items() if key != "content"}

    @router.get("/compose-long-image/jobs/{job_id}/download")
    async def download_compose_project_long_image_job(job_id: str) -> Response:
        job = COMPOSE_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="compose job not found")
        if job.get("status") != "done" or not job.get("content"):
            raise HTTPException(status_code=409, detail="compose job is not ready")
        return Response(
            content=job["content"],
            media_type="image/jpeg",
            headers={"Content-Disposition": 'attachment; filename="full-detail.jpg"'},
        )

except ModuleNotFoundError:
    router = None
