from __future__ import annotations

import re
import base64
import json
from io import BytesIO
from typing import Any, Protocol

from app.services.compliance_rules import ALL_PLATFORM_IDS, GLOBAL_RULES, ComplianceRule


NEGATIVE_CUES = ("不要", "不能", "不得", "避免", "禁止", "不写", "别写")
SUPPORT_KEYS = ("authority_assets", "effect_claims", "material_highlights")


class ImageComplianceProviderUnavailableError(RuntimeError):
    pass


class ImageComplianceProvider(Protocol):
    source: str

    async def check_image(
        self,
        image_bytes: bytes,
        *,
        location: dict[str, Any],
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError


class NoopImageComplianceProvider:
    source = "noop"

    async def check_image(
        self,
        image_bytes: bytes,
        *,
        location: dict[str, Any],
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        raise ImageComplianceProviderUnavailableError("AI image compliance provider is not configured")


class VisionModelImageComplianceProvider:
    def __init__(self, text_settings: Any):
        self.text_settings = text_settings
        self.source = str(getattr(text_settings, "model", "") or "vision_model")

    async def check_image(
        self,
        image_bytes: bytes,
        *,
        location: dict[str, Any],
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        if not getattr(self.text_settings, "api_key", ""):
            raise ImageComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        from app.services.text_model import call_text_model

        raw = await call_text_model(self.text_settings, _build_vision_compliance_messages(image_bytes, platform_id=platform_id, product_info=product_info))
        return _parse_vision_compliance_response(raw, base_location=location, platform_id=platform_id)


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


def _image_location(image: dict[str, Any], image_index: int, source_type: str = "image_ai") -> dict[str, Any]:
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


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return "{}"


def _build_vision_compliance_messages(
    image_bytes: bytes,
    *,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    prompt = "\n".join(
        [
            "你是中国电商商品图合规审核助手，请直接查看图片并判断是否存在违规或高风险内容，不要只识别文字。",
            "审核对象是护肤/化妆品店铺图片。请结合图片中的所有可见文字、产品包装、角标、图标、数据、活动信息和视觉表达判断。",
            f"目标平台：{platform_id or '未指定'}。",
            f"商品资料 JSON：{_safe_json(product_info)}。",
            "重点检查：绝对化/极限词，医疗治疗或治愈暗示，普通化妆品功效宣称是否需要资料依据，权威背书，实验/临床/百分比数据，价格补贴和限时压力，竞品攻击，平台资质/授权表达，敏感违法内容，以及明显乱码、不可读文字、水印或平台 UI。",
            "严重级别：block=应阻断导出或强提醒；warn=有明显合规风险；review=需要人工确认资料或模型不确定。",
            "只输出 JSON，不要解释。格式：",
            "{\"issues\":[{\"id\":\"...\",\"severity\":\"block|warn|review\",\"category\":\"absolute_claim|medical_claim|cosmetic_claim|authority_claim|data_claim|promotion_claim|competitor_claim|platform_claim|sensitive_content|visual_quality|other\",\"platform_ids\":[\"tmall\"],\"term\":\"...\",\"matched_text\":\"...\",\"reason\":\"...\",\"suggestion\":\"...\",\"qualification_hint\":\"...\",\"box\":[x1,y1,x2,y2]}],\"extracted_texts\":[{\"text\":\"...\",\"confidence\":0.0,\"box\":[x1,y1,x2,y2]}],\"warnings\":[]}",
            "如果没有发现风险，输出 {\"issues\":[],\"extracted_texts\":[],\"warnings\":[]}。box 不确定时省略或设为 null，confidence 取 0 到 1。",
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


def _json_object_from_model_text(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").strip()
    if not cleaned:
        return {}
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("AI compliance response must be a JSON object")
    return data


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return max(0.0, min(confidence, 1.0))


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(item) for item in value if _clean_text(item)]


def _coerce_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_issue_location(item: dict[str, Any], base_location: dict[str, Any]) -> dict[str, Any]:
    location = dict(base_location)
    item_location = item.get("location")
    if isinstance(item_location, dict):
        for key in ("image_index", "block_index", "image_url", "module_id", "field", "language"):
            if item_location.get(key) not in (None, ""):
                location[key] = item_location[key]
    box = _coerce_box(item.get("box"))
    if box is None and isinstance(item_location, dict):
        box = _coerce_box(item_location.get("box"))
    if box:
        location["box"] = _box_to_list(box)
    location["source_type"] = "image_ai"
    return location


def _normalize_ai_issue(item: Any, *, base_location: dict[str, Any], platform_id: str | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    severity = _clean_text(item.get("severity")).lower()
    if severity not in {"block", "warn", "review"}:
        severity = "review"
    term = _clean_text(item.get("term") or item.get("matched_text") or item.get("text") or "AI 合规风险")
    matched_text = _clean_text(item.get("matched_text") or item.get("text") or term)
    platform_ids = _coerce_string_list(item.get("platform_ids")) or ([platform_id] if platform_id else list(ALL_PLATFORM_IDS))
    return {
        "id": _clean_text(item.get("id")) or f"ai_{_clean_text(item.get('category')) or 'compliance'}",
        "severity": severity,
        "category": _clean_text(item.get("category")) or "other",
        "platform_ids": platform_ids,
        "term": term,
        "matched_text": matched_text,
        "location": _normalize_issue_location(item, base_location),
        "reason": _clean_text(item.get("reason")) or "AI 判断该图片内容存在合规风险，需要人工确认。",
        "suggestion": _clean_text(item.get("suggestion")) or "请删除或改写风险表达，导出前进行人工复核。",
        "qualification_hint": _clean_text(item.get("qualification_hint")),
    }


def _normalize_extracted_text(item: Any, *, base_location: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    text = _clean_text(item.get("text"))
    if not text:
        return None
    location = _normalize_issue_location(item, base_location)
    box = _coerce_box(item.get("box"))
    return {
        "text": text,
        "confidence": _coerce_confidence(item.get("confidence")),
        "box": _box_to_list(box),
        "location": location,
    }


def _parse_vision_compliance_response(raw: str, *, base_location: dict[str, Any], platform_id: str | None) -> dict[str, Any]:
    data = _json_object_from_model_text(raw)
    issues = [
        issue
        for issue in (_normalize_ai_issue(item, base_location=base_location, platform_id=platform_id) for item in _coerce_list(data.get("issues")))
        if issue is not None
    ]
    extracted_texts = [
        text
        for text in (_normalize_extracted_text(item, base_location=base_location) for item in _coerce_list(data.get("extracted_texts")))
        if text is not None
    ]
    return {
        "issues": issues,
        "extracted_texts": extracted_texts,
        "warnings": _coerce_string_list(data.get("warnings")),
    }


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
    compliance_provider: ImageComplianceProvider | None = None,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    provider = compliance_provider or NoopImageComplianceProvider()
    ai_source = str(getattr(provider, "source", provider.__class__.__name__))
    issues: list[dict[str, Any]] = []
    extracted_texts: list[dict[str, Any]] = []
    warnings: list[str] = []

    for image_index, image in enumerate(images):
        image_bytes = image.get("bytes")
        location = _image_location(image, image_index)
        if not isinstance(image_bytes, bytes) or not image_bytes:
            reason = str(image.get("read_error") or "image bytes are empty")
            warnings.append(reason)
            issues.append(
                _review_issue(
                    issue_id="image_read_failed",
                    category="image_ai_review",
                    term="图片读取失败",
                    reason=f"图片无法读取，未完成 Gemini 图片合规复查：{reason}",
                    suggestion="请重新生成或重新上传图片后再复查，导出前建议人工确认。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue

        try:
            image_report = await provider.check_image(
                image_bytes,
                location=location,
                platform_id=platform_id,
                product_info=product_info,
                debug=debug,
            )
        except ImageComplianceProviderUnavailableError as exc:
            reason = str(exc)
            warnings.append(reason)
            issues.append(
                _review_issue(
                    issue_id="image_ai_review_unavailable",
                    category="image_ai_review",
                    term="Gemini 图片合规复查未完成",
                    reason=f"Gemini 图片合规复查未完成：{reason}",
                    suggestion="请配置可识别图片的 Gemini 3.1 Pro 文本模型，或在导出前人工核对成图内容。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue
        except Exception as exc:
            reason = str(exc)
            warnings.append(reason)
            issues.append(
                _review_issue(
                    issue_id="image_ai_review_failed",
                    category="image_ai_review",
                    term="Gemini 图片合规复查失败",
                    reason=f"Gemini 图片合规复查失败：{reason}",
                    suggestion="请重试 Gemini 图片合规复查，若仍失败则导出前人工核对成图内容。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue

        issues.extend(
            issue
            for issue in (_normalize_ai_issue(item, base_location=location, platform_id=platform_id) for item in _coerce_list(image_report.get("issues")))
            if issue is not None
        )
        extracted_texts.extend(
            text
            for text in (_normalize_extracted_text(item, base_location=location) for item in _coerce_list(image_report.get("extracted_texts")))
            if text is not None
        )
        warnings.extend(_coerce_string_list(image_report.get("warnings")))

    report = {
        "source": "image_ai",
        "ai_source": ai_source,
        "summary": _summary(issues),
        "issues": issues,
        "extracted_texts": extracted_texts,
        "image_count": len(images),
        "warnings": warnings,
    }
    return report
