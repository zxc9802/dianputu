from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any, Protocol


ALL_PLATFORM_IDS = (
    "tmall",
    "jd",
    "douyin",
    "pdd",
    "xiaohongshu_square",
    "xiaohongshu_portrait",
)
VALID_STATUSES = ("pass", "review", "warn", "block")
VALID_SEVERITIES = ("review", "warn", "block")
STATUS_RANK = {"pass": 0, "review": 1, "warn": 2, "block": 3}


class ComplianceProviderUnavailableError(RuntimeError):
    pass


class ComplianceProvider(Protocol):
    source: str

    async def review_text(
        self,
        items: list[dict[str, Any]],
        *,
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def review_image(
        self,
        image_bytes: bytes,
        *,
        metadata: dict[str, Any],
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError


class NoopComplianceProvider:
    source = "gemini"

    async def review_text(
        self,
        items: list[dict[str, Any]],
        *,
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        raise ComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

    async def review_image(
        self,
        image_bytes: bytes,
        *,
        metadata: dict[str, Any],
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        raise ComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")


class ModelComplianceProvider:
    source = "gemini"

    def __init__(self, text_settings: Any):
        self.text_settings = text_settings

    async def review_text(
        self,
        items: list[dict[str, Any]],
        *,
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        if not getattr(self.text_settings, "api_key", ""):
            raise ComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        from app.services.text_model import call_text_model

        raw = await call_text_model(
            self.text_settings,
            _build_text_review_messages(items, platform_id=platform_id, product_info=product_info),
        )
        return _parse_model_report(raw)

    async def review_image(
        self,
        image_bytes: bytes,
        *,
        metadata: dict[str, Any],
        platform_id: str | None = None,
        product_info: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        if not getattr(self.text_settings, "api_key", ""):
            raise ComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        from app.services.text_model import call_text_model

        raw = await call_text_model(
            self.text_settings,
            _build_image_review_messages(image_bytes, metadata=metadata, platform_id=platform_id, product_info=product_info),
        )
        return _parse_model_report(raw)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _empty_summary(status: str = "pass") -> dict[str, Any]:
    return {"status": status, "block_count": 0, "warn_count": 0, "review_count": 0}


def _status_from_counts(block_count: int, warn_count: int, review_count: int) -> str:
    if block_count:
        return "block"
    if warn_count:
        return "warn"
    if review_count:
        return "review"
    return "pass"


def _summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
    block_count = sum(1 for issue in issues if issue.get("severity") == "block")
    warn_count = sum(1 for issue in issues if issue.get("severity") == "warn")
    review_count = sum(1 for issue in issues if issue.get("severity") == "review")
    return {
        "status": _status_from_counts(block_count, warn_count, review_count),
        "block_count": block_count,
        "warn_count": warn_count,
        "review_count": review_count,
    }


def _platform_ids(platform_id: str | None, value: Any = None) -> list[str]:
    if isinstance(value, list):
        cleaned = [_clean_text(item) for item in value if _clean_text(item)]
        if cleaned:
            return cleaned
    if platform_id:
        return [platform_id]
    return list(ALL_PLATFORM_IDS)


def _coerce_status(value: Any) -> str:
    status = _clean_text(value)
    return status if status in VALID_STATUSES else "pass"


def _coerce_severity(value: Any) -> str:
    severity = _clean_text(value)
    return severity if severity in VALID_SEVERITIES else "review"


def _image_location(image: dict[str, Any], image_index: int) -> dict[str, Any]:
    location: dict[str, Any] = {
        "source_type": "image_review",
        "image_index": image_index,
    }
    for key in ("module_id", "field", "language"):
        if image.get(key):
            location[key] = image[key]
    if image.get("url"):
        location["image_url"] = image["url"]
    return location


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


def _json_payload(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _schema_instruction() -> str:
    return "\n".join(
        [
            "只输出 JSON，不要输出 Markdown 或解释。",
            "JSON 格式必须为：",
            '{"summary":{"status":"pass|review|warn|block","block_count":0,"warn_count":0,"review_count":0},"issues":[{"id":"...","severity":"review|warn|block","category":"...","term":"...","matched_text":"...","location":{},"reason":"...","suggestion":"...","qualification_hint":"..."}]}',
            "status 规则：pass=无明显风险；review=需要人工确认；warn=有合规风险；block=高风险或明显违规。",
            "若发现敏感词、违规词、医疗化功效、绝对化宣传、虚假背书、未经证实的数据、竞品攻击、平台身份/授权风险，都要列入 issues。",
            "location 必须尽量沿用输入中的 location；图片问题可使用 metadata.location。",
        ]
    )


def _build_text_review_messages(
    items: list[dict[str, Any]],
    *,
    platform_id: str | None,
    product_info: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    prompt = "\n\n".join(
        [
            "你是中国电商商品图合规审核助手。请直接判断输入文字是否包含违规词、敏感词或平台审核风险。",
            "请重点检查护肤/美妆类商品常见风险：医疗治疗、治愈承诺、绝对化用语、虚假数据、权威背书、功效宣称和价格促销夸大。",
            _schema_instruction(),
            f"目标平台：{platform_id or '未指定'}",
            "产品资料：\n" + _json_payload(product_info or {}),
            "待审核文字：\n" + _json_payload(items),
        ]
    )
    return [{"role": "user", "content": prompt}]


def _build_image_review_messages(
    image_bytes: bytes,
    *,
    metadata: dict[str, Any],
    platform_id: str | None,
    product_info: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    prompt = "\n\n".join(
        [
            "你是中国电商商品图合规审核助手。请直接审查这张图片是否包含违规词、敏感词、虚假或高风险宣传，以及不适合电商平台展示的画面元素。",
            "不要只做文字识别；你需要基于图片中文字和画面内容给出合规结论。",
            _schema_instruction(),
            f"目标平台：{platform_id or '未指定'}",
            "产品资料：\n" + _json_payload(product_info or {}),
            "图片元数据：\n" + _json_payload(metadata),
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


def _parse_model_report(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("Gemini compliance response is empty")
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Gemini compliance response must be a JSON object")
    return data


def _normalize_issue(
    issue: dict[str, Any],
    *,
    default_location: dict[str, Any] | None,
    platform_id: str | None,
) -> dict[str, Any]:
    location = issue.get("location") if isinstance(issue.get("location"), dict) else default_location or {}
    category = _clean_text(issue.get("category")) or "model_review"
    term = _clean_text(issue.get("term")) or _clean_text(issue.get("matched_text")) or "合规风险"
    return {
        "id": _clean_text(issue.get("id")) or f"gemini_{category}",
        "severity": _coerce_severity(issue.get("severity")),
        "category": category,
        "platform_ids": _platform_ids(platform_id, issue.get("platform_ids")),
        "term": term,
        "matched_text": _clean_text(issue.get("matched_text")),
        "location": location,
        "reason": _clean_text(issue.get("reason")) or "Gemini 判断该内容存在合规风险。",
        "suggestion": _clean_text(issue.get("suggestion")) or "请调整为真实、克制且有依据的表达。",
        "qualification_hint": _clean_text(issue.get("qualification_hint")),
    }


def _synthetic_issue_for_summary(
    *,
    status: str,
    default_location: dict[str, Any] | None,
    platform_id: str | None,
) -> dict[str, Any]:
    return {
        "id": "gemini_compliance_review",
        "severity": status if status in VALID_SEVERITIES else "review",
        "category": "model_review",
        "platform_ids": _platform_ids(platform_id),
        "term": "Gemini 合规提示",
        "matched_text": "",
        "location": default_location or {},
        "reason": "Gemini 返回了非通过的合规状态，但没有列出具体条目。",
        "suggestion": "请人工核对商品图和文案中的宣传用语。",
        "qualification_hint": "",
    }


def _normalize_model_report(
    report: dict[str, Any],
    *,
    source: str,
    default_location: dict[str, Any] | None = None,
    platform_id: str | None = None,
) -> dict[str, Any]:
    raw_issues = report.get("issues")
    issue_values = raw_issues if isinstance(raw_issues, list) else []
    issues = [
        _normalize_issue(issue, default_location=default_location, platform_id=platform_id)
        for issue in issue_values
        if isinstance(issue, dict)
    ]
    summary_input = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    model_status = _coerce_status(summary_input.get("status"))
    if not issues and model_status != "pass":
        issues.append(_synthetic_issue_for_summary(status=model_status, default_location=default_location, platform_id=platform_id))

    summary = _summary(issues)
    if not issues and model_status == "pass":
        summary = _empty_summary("pass")

    return {
        "source": _clean_text(report.get("source")) or source,
        "summary": summary,
        "issues": issues,
    }


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
        "platform_ids": _platform_ids(platform_id),
        "term": term,
        "matched_text": "",
        "location": location,
        "reason": reason,
        "suggestion": suggestion,
        "qualification_hint": "",
    }


def _review_report(
    *,
    source: str,
    issue: dict[str, Any],
    image_count: int | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    report = {"source": source, "summary": _summary([issue]), "issues": [issue]}
    if image_count is not None:
        report["image_count"] = image_count
    if warnings is not None:
        report["warnings"] = warnings
    return report


def _provider_source(provider: ComplianceProvider) -> str:
    return _clean_text(getattr(provider, "source", provider.__class__.__name__)) or "gemini"


async def check_text_items(
    items: list[dict[str, Any]],
    *,
    compliance_provider: ComplianceProvider | None = None,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    cleaned_items = [
        {"text": _clean_text(item.get("text")), "location": item.get("location") if isinstance(item.get("location"), dict) else {}}
        for item in items
        if _clean_text(item.get("text"))
    ]
    if not cleaned_items:
        return {"source": _provider_source(compliance_provider or NoopComplianceProvider()), "summary": _empty_summary(), "issues": []}

    provider = compliance_provider or NoopComplianceProvider()
    source = _provider_source(provider)
    try:
        report = await provider.review_text(cleaned_items, platform_id=platform_id, product_info=product_info, debug=debug)
    except ComplianceProviderUnavailableError as exc:
        issue = _review_issue(
            issue_id="model_compliance_unavailable",
            category="model_review",
            term="Gemini 合规复查未完成",
            reason=f"Gemini 合规复查未完成：{exc}",
            suggestion="请配置可用于文字和图片理解的 TEXT_ANALYSIS_API_KEY，或导出前人工核对。",
            location=cleaned_items[0]["location"],
            platform_id=platform_id,
        )
        return _review_report(source=source, issue=issue)
    except Exception as exc:
        issue = _review_issue(
            issue_id="model_compliance_failed",
            category="model_review",
            term="Gemini 合规复查失败",
            reason=f"Gemini 合规复查失败：{exc}",
            suggestion="请重试合规复查，若仍失败则导出前人工核对。",
            location=cleaned_items[0]["location"],
            platform_id=platform_id,
        )
        return _review_report(source=source, issue=issue)
    return _normalize_model_report(report, source=source, default_location=cleaned_items[0]["location"], platform_id=platform_id)


async def check_image_items(
    images: list[dict[str, Any]],
    *,
    compliance_provider: ComplianceProvider | None = None,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    provider = compliance_provider or NoopComplianceProvider()
    source = _provider_source(provider)
    issues: list[dict[str, Any]] = []
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
                    category="image_review",
                    term="图片读取失败",
                    reason=f"图片无法读取，未完成 Gemini 图片合规复查：{reason}",
                    suggestion="请重新生成或重新上传图片后再复查，导出前建议人工确认。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue

        metadata = {"location": location, "image_index": image_index, "image_url": image.get("url", "")}
        try:
            image_report = await provider.review_image(
                image_bytes,
                metadata=metadata,
                platform_id=platform_id,
                product_info=product_info,
                debug=debug,
            )
        except ComplianceProviderUnavailableError as exc:
            reason = str(exc)
            warnings.append(reason)
            issues.append(
                _review_issue(
                    issue_id="model_compliance_unavailable",
                    category="image_review",
                    term="Gemini 图片复查未完成",
                    reason=f"Gemini 图片合规复查未完成：{reason}",
                    suggestion="请配置可用于图片理解的 TEXT_ANALYSIS_API_KEY，或导出前人工核对图片内容。",
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
                    issue_id="model_compliance_failed",
                    category="image_review",
                    term="Gemini 图片复查失败",
                    reason=f"Gemini 图片合规复查失败：{reason}",
                    suggestion="请重试图片合规复查，若仍失败则导出前人工核对图片内容。",
                    location=location,
                    platform_id=platform_id,
                )
            )
            continue

        normalized = _normalize_model_report(image_report, source=source, default_location=location, platform_id=platform_id)
        issues.extend(normalized["issues"])

    return {
        "source": source,
        "summary": _summary(issues),
        "issues": issues,
        "image_count": len(images),
        "warnings": warnings,
    }
