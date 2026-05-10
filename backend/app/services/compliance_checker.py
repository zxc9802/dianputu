from __future__ import annotations

import re
import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Protocol

from app.services.compliance_rules import ALL_PLATFORM_IDS, GLOBAL_RULES, ComplianceRule


NEGATIVE_CUES = ("不要", "不能", "不得", "避免", "禁止", "不写", "别写")
SUPPORT_KEYS = ("authority_assets", "effect_claims", "material_highlights")


@dataclass(frozen=True)
class OcrTextBlock:
    text: str
    confidence: float = 0.0
    box: tuple[int, int, int, int] | None = None


class OcrProviderUnavailableError(RuntimeError):
    pass


class OcrProvider(Protocol):
    source: str

    async def extract_text(self, image_bytes: bytes) -> list[OcrTextBlock]:
        raise NotImplementedError


class NoopOcrProvider:
    source = "noop"

    async def extract_text(self, image_bytes: bytes) -> list[OcrTextBlock]:
        raise OcrProviderUnavailableError("OCR provider is not configured")


class VisionModelOcrProvider:
    source = "vision_model"

    def __init__(self, text_settings: Any):
        self.text_settings = text_settings

    async def extract_text(self, image_bytes: bytes) -> list[OcrTextBlock]:
        if not getattr(self.text_settings, "api_key", ""):
            raise OcrProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        from app.services.text_model import call_text_model

        raw = await call_text_model(self.text_settings, _build_vision_ocr_messages(image_bytes))
        return _parse_vision_ocr_response(raw)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _stringify_product_info(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_stringify_product_info(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_stringify_product_info(item) for item in value)
    return str(value)


def _has_supporting_evidence(product_info: dict[str, Any] | None) -> bool:
    info = product_info or {}
    return any(_clean_text(_stringify_product_info(info.get(key))) for key in SUPPORT_KEYS)


def _severity_for_rule(rule: ComplianceRule, product_info: dict[str, Any] | None) -> str:
    if rule.category == "cosmetic_claim" and _has_supporting_evidence(product_info):
        return "review"
    return rule.severity


def _is_negative_context(text: str, start: int) -> bool:
    prefix = text[max(0, start - 12) : start]
    sentence_prefix = text[:start]
    return any(cue in prefix or sentence_prefix.startswith(cue) for cue in NEGATIVE_CUES)


def _platforms_for(rule: ComplianceRule, platform_id: str | None) -> list[str]:
    platforms = list(rule.platforms or ALL_PLATFORM_IDS)
    if platform_id and platform_id in platforms:
        return [platform_id]
    return platforms


def _summary_from_counts(block_count: int, warn_count: int, review_count: int) -> dict[str, Any]:
    status = "pass"
    if block_count:
        status = "block"
    elif warn_count:
        status = "warn"
    elif review_count:
        status = "review"
    return {
        "status": status,
        "block_count": block_count,
        "warn_count": warn_count,
        "review_count": review_count,
    }


def _issue(
    *,
    rule: ComplianceRule,
    severity: str,
    term: str,
    text: str,
    location: dict[str, Any],
    platform_id: str | None,
) -> dict[str, Any]:
    return {
        "id": rule.id,
        "severity": severity,
        "category": rule.category,
        "platform_ids": _platforms_for(rule, platform_id),
        "term": term,
        "matched_text": text,
        "location": location,
        "reason": rule.reason,
        "suggestion": rule.suggestion,
        "qualification_hint": rule.qualification_hint,
    }


def _summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
    block_count = sum(1 for issue in issues if issue["severity"] == "block")
    warn_count = sum(1 for issue in issues if issue["severity"] == "warn")
    review_count = sum(1 for issue in issues if issue["severity"] == "review")
    return _summary_from_counts(block_count, warn_count, review_count)


def _review_issue(
    *,
    issue_id: str,
    category: str,
    term: str,
    reason: str,
    suggestion: str,
    location: dict[str, Any],
    platform_id: str | None,
) -> dict[str, Any]:
    return {
        "id": issue_id,
        "severity": "review",
        "category": category,
        "platform_ids": [platform_id] if platform_id else list(ALL_PLATFORM_IDS),
        "term": term,
        "matched_text": "",
        "location": location,
        "reason": reason,
        "suggestion": suggestion,
        "qualification_hint": "",
    }


def _image_location(image: dict[str, Any], image_index: int, source_type: str = "image_ocr") -> dict[str, Any]:
    location: dict[str, Any] = {
        "source_type": source_type,
        "image_index": image_index,
    }
    for key in ("module_id", "field", "language"):
        if image.get(key):
            location[key] = image[key]
    if image.get("url"):
        location["image_url"] = image["url"]
    return location


def _box_to_list(box: tuple[int, int, int, int] | None) -> list[int] | None:
    return list(box) if box else None


def _guess_image_mime(image_bytes: bytes) -> str:
    try:
        from PIL import Image

        with Image.open(BytesIO(image_bytes)) as image:
            image_format = (image.format or "PNG").lower()
    except Exception:
        image_format = "png"
    if image_format == "jpg":
        image_format = "jpeg"
    return f"image/{image_format}"


def _image_data_url(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{_guess_image_mime(image_bytes)};base64,{encoded}"


def _build_vision_ocr_messages(image_bytes: bytes) -> list[dict[str, Any]]:
    prompt = "\n".join(
        [
            "你是电商商品图 OCR 审核助手。请识别图片中所有可读文字。",
            "只输出 JSON，不要解释。",
            "JSON 格式：{\"items\":[{\"text\":\"...\",\"confidence\":0.0,\"box\":[x1,y1,x2,y2]}]}。",
            "如果没有可读文字，输出 {\"items\":[]}。",
            "box 不确定时可省略或设为 null；confidence 取 0 到 1。",
        ]
    )
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _image_data_url(image_bytes)}},
            ],
        }
    ]


def _coerce_box(value: Any) -> tuple[int, int, int, int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        return tuple(int(float(item)) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _parse_vision_ocr_response(raw: str) -> list[OcrTextBlock]:
    import json

    cleaned = (raw or "").strip()
    if not cleaned:
        return []
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("OCR response must contain items")
    blocks: list[OcrTextBlock] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = _clean_text(item.get("text"))
        if not text:
            continue
        try:
            confidence = float(item.get("confidence", 0.0) or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        blocks.append(OcrTextBlock(text=text, confidence=max(0.0, min(confidence, 1.0)), box=_coerce_box(item.get("box"))))
    return blocks


def check_text_items(
    items: list[dict[str, Any]],
    *,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    ignored_matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for item in items:
        text = _clean_text(item.get("text"))
        if not text:
            continue
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        for rule in GLOBAL_RULES:
            severity = _severity_for_rule(rule, product_info)
            for term in rule.terms:
                start = text.find(term)
                if start < 0:
                    continue
                if _is_negative_context(text, start):
                    if debug:
                        ignored_matches.append({"term": term, "text": text, "location": location, "reason": "negative_context"})
                    continue
                key = (rule.id, term, text, repr(sorted(location.items())))
                if key in seen:
                    continue
                seen.add(key)
                issues.append(_issue(rule=rule, severity=severity, term=term, text=text, location=location, platform_id=platform_id))
            for pattern in rule.patterns:
                for match in re.finditer(pattern, text):
                    term = match.group(0)
                    if _is_negative_context(text, match.start()):
                        if debug:
                            ignored_matches.append({"term": term, "text": text, "location": location, "reason": "negative_context"})
                        continue
                    key = (rule.id, term, text, repr(sorted(location.items())))
                    if key in seen:
                        continue
                    seen.add(key)
                    issues.append(_issue(rule=rule, severity=severity, term=term, text=text, location=location, platform_id=platform_id))

    report = {"source": "rules", "summary": _summary(issues), "issues": issues}
    if debug:
        report["ignored_matches"] = ignored_matches
    return report


async def check_image_items(
    images: list[dict[str, Any]],
    *,
    ocr_provider: OcrProvider | None = None,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    provider = ocr_provider or NoopOcrProvider()
    ocr_source = str(getattr(provider, "source", provider.__class__.__name__))
    compliance_items: list[dict[str, Any]] = []
    extracted_texts: list[dict[str, Any]] = []
    review_issues: list[dict[str, Any]] = []
    warnings: list[str] = []

    for image_index, image in enumerate(images):
        image_bytes = image.get("bytes")
        location = _image_location(image, image_index)
        if not isinstance(image_bytes, bytes) or not image_bytes:
            reason = str(image.get("read_error") or "image bytes are empty")
            warnings.append(reason)
            review_issues.append(
                _review_issue(
                    issue_id="image_read_failed",
                    category="image_ocr",
                    term="图片读取失败",
                    reason=f"图片无法读取，未完成图片文字合规检查：{reason}",
                    suggestion="请重新生成或重新上传图片后再复查，导出前建议人工确认。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue

        try:
            blocks = await provider.extract_text(image_bytes)
        except OcrProviderUnavailableError as exc:
            reason = str(exc)
            warnings.append(reason)
            review_issues.append(
                _review_issue(
                    issue_id="image_ocr_unavailable",
                    category="image_ocr",
                    term="图片 OCR 未完成",
                    reason=f"图片文字识别未完成：{reason}",
                    suggestion="请配置可识别图片的文本模型，或在导出前人工核对图片文字。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue
        except Exception as exc:
            reason = str(exc)
            warnings.append(reason)
            review_issues.append(
                _review_issue(
                    issue_id="image_ocr_failed",
                    category="image_ocr",
                    term="图片 OCR 失败",
                    reason=f"图片文字识别失败：{reason}",
                    suggestion="请重试图片合规检查，若仍失败则导出前人工核对图片文字。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue

        for block_index, block in enumerate(blocks):
            text = _clean_text(block.text)
            if not text:
                continue
            block_location = {**location, "block_index": block_index}
            if block.box:
                block_location["box"] = _box_to_list(block.box)
            compliance_items.append({"text": text, "location": block_location})
            extracted_texts.append(
                {
                    "text": text,
                    "confidence": block.confidence,
                    "box": _box_to_list(block.box),
                    "location": block_location,
                }
            )

    text_report = check_text_items(compliance_items, platform_id=platform_id, product_info=product_info, debug=debug)
    issues = [*text_report["issues"], *review_issues]
    report = {
        "source": "image_ocr",
        "ocr_source": ocr_source,
        "summary": _summary(issues),
        "issues": issues,
        "extracted_texts": extracted_texts,
        "image_count": len(images),
        "warnings": warnings,
    }
    if debug and text_report.get("ignored_matches"):
        report["ignored_matches"] = text_report["ignored_matches"]
    return report
