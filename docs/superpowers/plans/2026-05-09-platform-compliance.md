# Platform Compliance Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first-pass platform compliance checker that flags risky ecommerce image copy before export and attaches compliance reports to generated image versions.

**Architecture:** Add a deterministic backend rule engine with structured compliance reports, expose text and image-check endpoints, and integrate rule checks into layered generation, language rendering, and edit requests. The frontend stores reports in image versions, runs preflight checks for product and promotion copy, and displays compact risk badges and suggestions without blocking export by default.

**Tech Stack:** FastAPI, Pydantic, Python `unittest`, Next.js, React, TypeScript, existing static Node tests.

---

## File Structure

- Create `backend/app/services/compliance_rules.py`: rule definitions, platform ids, category/severity constants.
- Create `backend/app/services/compliance_checker.py`: scanner, summary builder, context suppression, OCR no-op provider.
- Create `backend/tests/test_compliance_checker.py`: unit tests for rules, severities, platform filtering, context suppression.
- Modify `backend/app/routers/projects.py`: Pydantic request models, `/compliance/check-text`, `/compliance/check-images`, generation/language/edit integration.
- Modify `backend/tests/test_api_contracts.py`: API contract and generation response coverage.
- Modify `frontend/lib/types.ts`: compliance report types on images and language versions.
- Modify `frontend/lib/api.ts`: compliance API client and platform id plumbing through generation, edit, and language calls.
- Create `frontend/lib/compliance.ts`: frontend helpers for labels, CSS classes, highest status, and product-info scan items.
- Modify `frontend/lib/projectEnhancements.ts`: preserve compliance reports when adding generated and language versions.
- Modify `frontend/tests/project-enhancements.test.cjs`: assert compliance reports are preserved.
- Modify `frontend/components/ReviewStep.tsx`: show product info compliance panel.
- Modify `frontend/components/ModulesStep.tsx`: show campaign promotion compliance preflight.
- Modify `frontend/components/PreviewStep.tsx`: show per-image compliance badges, issue details, and export summary.
- Modify `frontend/app/page.tsx`: preflight state, API calls, and selected platform id propagation.
- Modify `frontend/app/globals.css`: badge, panel, and issue list styles.
- Modify `frontend/tests/static-ui-contract.test.cjs`: static checks for compliance UI/API strings.

## Task 1: Backend Rule Engine

**Files:**
- Create: `backend/app/services/compliance_rules.py`
- Create: `backend/app/services/compliance_checker.py`
- Create: `backend/tests/test_compliance_checker.py`

- [ ] **Step 1: Write failing checker tests**

Create `backend/tests/test_compliance_checker.py`:

```python
import unittest

from app.services.compliance_checker import check_text_items


class ComplianceCheckerTests(unittest.TestCase):
    def test_flags_medical_claim_as_block(self):
        report = check_text_items(
            [
                {
                    "text": "7天治愈敏感肌",
                    "location": {"source_type": "text_layer", "module_id": "main_effect", "field": "title"},
                }
            ],
            platform_id="tmall",
        )

        self.assertEqual(report["source"], "rules")
        self.assertEqual(report["summary"]["status"], "block")
        self.assertEqual(report["summary"]["block_count"], 1)
        self.assertEqual(report["issues"][0]["term"], "治愈")
        self.assertEqual(report["issues"][0]["category"], "medical_claim")
        self.assertEqual(report["issues"][0]["location"]["module_id"], "main_effect")

    def test_flags_absolute_and_promotion_claims(self):
        report = check_text_items(
            [
                {"text": "全网最低价 护肤首选", "location": {"source_type": "promotion", "field": "promotion_info"}},
            ],
            platform_id="douyin",
        )

        terms = {issue["term"] for issue in report["issues"]}
        self.assertIn("全网最低", terms)
        self.assertIn("首选", terms)
        self.assertEqual(report["summary"]["status"], "block")

    def test_cosmetic_claim_is_warn_without_support_and_review_with_support(self):
        unsupported = check_text_items(
            [{"text": "美白淡斑精华", "location": {"source_type": "field", "field": "core_selling_points"}}],
            platform_id="jd",
        )
        supported = check_text_items(
            [{"text": "美白淡斑精华", "location": {"source_type": "field", "field": "core_selling_points"}}],
            platform_id="jd",
            product_info={
                "authority_assets": ["特殊化妆品注册备案资料"],
                "effect_claims": [{"claim": "美白淡斑", "value": "依据功效评价摘要", "source_type": "report"}],
            },
        )

        self.assertEqual(unsupported["summary"]["status"], "warn")
        self.assertEqual(unsupported["issues"][0]["severity"], "warn")
        self.assertEqual(supported["summary"]["status"], "review")
        self.assertEqual(supported["issues"][0]["severity"], "review")

    def test_negative_instruction_is_ignored(self):
        report = check_text_items(
            [
                {"text": "不要写治愈、根治、永久有效", "location": {"source_type": "edit_instruction", "field": "instruction"}},
            ],
            platform_id="pdd",
            debug=True,
        )

        self.assertEqual(report["summary"]["status"], "pass")
        self.assertEqual(report["issues"], [])
        self.assertTrue(report["ignored_matches"])

    def test_platform_filtering_uses_requested_platform_and_global_rules(self):
        report = check_text_items(
            [{"text": "平台补贴 官方旗舰", "location": {"source_type": "promotion", "field": "promotion_info"}}],
            platform_id="xiaohongshu_square",
        )

        self.assertTrue(all("xiaohongshu_square" in issue["platform_ids"] for issue in report["issues"]))
        self.assertEqual(report["summary"]["warn_count"], 2)

    def test_pass_summary_for_safe_copy(self):
        report = check_text_items(
            [{"text": "舒缓干燥泛红 水润保湿", "location": {"source_type": "text_layer", "field": "subtitle"}}],
            platform_id="tmall",
        )

        self.assertEqual(report["summary"], {"status": "pass", "block_count": 0, "warn_count": 0, "review_count": 0})
        self.assertEqual(report["issues"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run checker tests to verify failure**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/backend
PYTHONPATH=. python -m unittest tests.test_compliance_checker -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.compliance_checker'`.

- [ ] **Step 3: Add compliance rule definitions**

Create `backend/app/services/compliance_rules.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


ALL_PLATFORM_IDS = (
    "tmall",
    "jd",
    "douyin",
    "pdd",
    "xiaohongshu_square",
    "xiaohongshu_portrait",
)


@dataclass(frozen=True)
class ComplianceRule:
    id: str
    category: str
    severity: str
    terms: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ALL_PLATFORM_IDS
    reason: str = ""
    suggestion: str = ""
    qualification_hint: str = ""


GLOBAL_RULES: tuple[ComplianceRule, ...] = (
    ComplianceRule(
        id="absolute_extreme_terms",
        category="absolute_claim",
        severity="block",
        terms=("国家级", "最高级", "最佳", "第一", "顶级", "唯一", "首选", "全网最低", "销量冠军", "100%", "永久"),
        reason="广告宣传中的绝对化或极限表述容易触发平台审核和广告法风险。",
        suggestion="改为有边界的描述，例如「重点推荐」「热销款」「优惠价」或删除绝对排名表达。",
    ),
    ComplianceRule(
        id="medical_treatment_terms",
        category="medical_claim",
        severity="block",
        terms=("治疗", "治愈", "疗效", "消炎", "抗菌", "杀菌", "祛疤", "根治敏感", "修复皮炎"),
        reason="普通护肤品图片不应明示或暗示医疗治疗、治愈或药品功效。",
        suggestion="改为护肤体验表达，例如「舒缓不适肤感」「帮助维持肌肤稳定」「改善干燥粗糙」。",
    ),
    ComplianceRule(
        id="cosmetic_efficacy_terms",
        category="cosmetic_claim",
        severity="warn",
        terms=("美白", "祛斑", "防晒", "防脱发", "祛痘", "修护", "抗皱", "紧致", "舒缓敏感"),
        reason="功效宣称需要与产品备案、功效评价或资料依据一致。",
        suggestion="确认产品备案和资料依据，必要时改为更温和的日常护理表达。",
        qualification_hint="备案/功效评价资料",
    ),
    ComplianceRule(
        id="authority_endorsement_terms",
        category="authority_claim",
        severity="warn",
        terms=("国家认证", "央视推荐", "专家推荐", "医生推荐", "国家免检", "指定产品", "官方授权"),
        reason="权威背书、专家推荐和授权表达需要真实可核验证据。",
        suggestion="改为「资料可追溯」「品质检测」「配方研究」等不冒用背书的表达。",
    ),
    ComplianceRule(
        id="data_claim_terms",
        category="data_claim",
        severity="warn",
        terms=("临床证明", "实验室证明", "99%有效", "销量第一", "有效率"),
        patterns=(r"\d+(?:\.\d+)?\s*[%％]\s*(?:有效|提升|改善|增长|增加)",),
        reason="数据和实验结论需要对应来源，不能编造或夸大。",
        suggestion="保留真实数据来源；没有依据时改为体验型表达。",
    ),
    ComplianceRule(
        id="promotion_pressure_terms",
        category="promotion_claim",
        severity="warn",
        terms=("最低价", "史低", "亏本", "最后一天", "官方补贴", "平台补贴"),
        reason="价格、补贴和限时表达需要与真实活动规则一致。",
        suggestion="改为用户已提供的活动信息，或使用「限时活动」「到手优惠」等泛化表达。",
    ),
    ComplianceRule(
        id="competitor_attack_terms",
        category="competitor_claim",
        severity="warn",
        terms=("秒杀同类", "吊打竞品", "比某品牌更好", "智商税"),
        reason="贬低同类或指向竞品的表达存在不正当竞争和平台审核风险。",
        suggestion="改为描述自身卖点，不直接攻击同类商品。",
    ),
    ComplianceRule(
        id="platform_auth_terms",
        category="platform_claim",
        severity="warn",
        terms=("官方旗舰", "自营", "专柜正品", "品牌授权", "保税直发"),
        reason="店铺、授权和履约链路表达需要真实资质或平台身份支持。",
        suggestion="确认店铺资质后使用；无资质时删除该表达。",
    ),
    ComplianceRule(
        id="sensitive_content_terms",
        category="sensitive_content",
        severity="block",
        terms=("赌博", "迷信", "歧视", "色情", "暴力恐吓"),
        reason="敏感、违法或公序良俗风险内容不适合电商商品图。",
        suggestion="删除敏感内容，改为与商品真实卖点相关的表达。",
    ),
)
```

- [ ] **Step 4: Add compliance checker implementation**

Create `backend/app/services/compliance_checker.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.compliance_rules import ALL_PLATFORM_IDS, GLOBAL_RULES, ComplianceRule


NEGATIVE_CUES = ("不要", "不能", "不得", "避免", "禁止", "不写", "别写")
SUPPORT_KEYS = ("authority_assets", "effect_claims", "material_highlights")


@dataclass(frozen=True)
class OcrTextBlock:
    text: str
    confidence: float = 0.0
    box: tuple[int, int, int, int] | None = None


class OcrProvider(Protocol):
    async def extract_text(self, image_bytes: bytes) -> list[OcrTextBlock]:
        raise NotImplementedError


class NoopOcrProvider:
    async def extract_text(self, image_bytes: bytes) -> list[OcrTextBlock]:
        return []


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
```

- [ ] **Step 5: Run checker tests to verify pass**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/backend
PYTHONPATH=. python -m unittest tests.test_compliance_checker -v
```

Expected: PASS for all six tests.

- [ ] **Step 6: Commit backend rule engine**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
git add backend/app/services/compliance_rules.py backend/app/services/compliance_checker.py backend/tests/test_compliance_checker.py
git commit -m "Add compliance rule checker"
```

Expected: commit succeeds and only the three listed files are included in this commit.

## Task 2: Backend API And Generation Integration

**Files:**
- Modify: `backend/app/routers/projects.py`
- Modify: `backend/tests/test_api_contracts.py`

- [ ] **Step 1: Write failing backend integration tests**

In `backend/tests/test_api_contracts.py`, update the import from `app.routers.projects` to include `check_project_text_compliance` after it exists:

```python
from app.routers.projects import COMPOSE_JOBS, build_layered_generated_image, check_project_text_compliance, compose_long_jpeg, edit_generated_image, generate_detail_images, render_layered_language_version, router as projects_router
```

Add these tests inside `GenerationContractTests` after `test_render_language_version_translates_then_reuses_base_image`:

```python
    async def test_layered_generation_includes_compliance_report(self):
        image = Image.new("RGB", (320, 320), (230, 244, 235))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        module = next(module for module in DEFAULT_MODULES if module["id"] == "main_hero_selling_point")

        with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)):
            result = await build_layered_generated_image(
                module=module,
                product_info={"product_name": "修护精华", "core_selling_points": ["7天治愈敏感肌"], "functions": ["水润透亮"]},
                base_url=data_url,
                platform_id="tmall",
            )

        self.assertEqual(result["compliance"]["summary"]["status"], "block")
        self.assertEqual(result["language_versions"]["zh-CN"]["compliance"]["summary"]["status"], "block")

    async def test_render_language_version_includes_compliance_report(self):
        image = Image.new("RGB", (320, 320), (240, 240, 255))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        data_url = "data:image/png;base64," + b64encode(buffer.getvalue()).decode("ascii")
        layers = [
            {
                "id": "title",
                "role": "title",
                "source_text": "深层补水",
                "text": "深层补水",
                "x": 0.1,
                "y": 0.1,
                "width": 0.5,
                "height": 0.1,
                "font_size": 0.06,
            }
        ]

        with patch("app.routers.projects.translate_text_layers", new=AsyncMock(return_value=[{**layers[0], "text": "100% effective"}])):
            with patch("app.routers.projects.upload_image_url_if_configured", new=AsyncMock(side_effect=lambda url, folder: url)):
                result = await render_layered_language_version(base_url=data_url, layers=layers, language="en", platform_id="tmall")

        self.assertEqual(result["compliance"]["summary"]["status"], "block")
        self.assertEqual(result["compliance"]["issues"][0]["category"], "absolute_claim")

    async def test_edit_generated_image_returns_instruction_compliance(self):
        previous_key = environ.get("IMAGE_GENERATION_API_KEY")
        environ["IMAGE_GENERATION_API_KEY"] = "test-key"
        try:
            with patch("app.routers.projects.call_image_edit_model", new=AsyncMock(return_value=["https://example.com/edited.png"])):
                result = await edit_generated_image(
                    "data:image/png;base64,YWJj",
                    "把标题改成全网最低价",
                    platform_size="800x800",
                    platform_id="tmall",
                )
        finally:
            if previous_key is None:
                environ.pop("IMAGE_GENERATION_API_KEY", None)
            else:
                environ["IMAGE_GENERATION_API_KEY"] = previous_key

        self.assertEqual(result["source"], "model")
        self.assertEqual(result["compliance"]["summary"]["status"], "block")
```

Add this test inside `DownloadContractTests`:

```python
    def test_text_compliance_endpoint_returns_report(self):
        response = self.make_client().post(
            "/api/projects/compliance/check-text",
            json={
                "platform_id": "tmall",
                "items": [
                    {
                        "text": "7天治愈敏感肌",
                        "location": {"source_type": "field", "field": "core_selling_points"},
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "rules")
        self.assertEqual(payload["summary"]["status"], "block")
        self.assertEqual(payload["issues"][0]["term"], "治愈")
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/backend
PYTHONPATH=. python -m unittest tests.test_api_contracts -v
```

Expected: FAIL because `check_project_text_compliance`, endpoint models, and compliance fields are missing.

- [ ] **Step 3: Import checker and add helper functions**

Modify the top imports in `backend/app/routers/projects.py`:

```python
from app.services.compliance_checker import check_text_items
```

Add these helpers near `build_layered_generated_image`:

```python
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


def check_project_text_compliance(
    items: list[dict[str, Any]],
    *,
    platform_id: str | None = None,
    product_info: dict[str, Any] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    return check_text_items(items, platform_id=platform_id, product_info=product_info, debug=debug)
```

- [ ] **Step 4: Integrate compliance into layered rendering**

Change `render_layered_language_version` signature in `backend/app/routers/projects.py`:

```python
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
```

Inside the function, after the line `uploaded_url = await upload_image_url_if_configured(data_url, f"{folder}/{normalized_language}")`, add:

```python
    compliance = check_project_text_compliance(
        text_layers_to_compliance_items(translated_layers, module_id=module_id, language=normalized_language),
        platform_id=platform_id,
        product_info=product_info,
    )
```

Return `compliance`:

```python
    return {
        "language": normalized_language,
        "language_label": language_label(normalized_language),
        "url": uploaded_url,
        "layers": translated_layers,
        "warnings": warnings,
        "compliance": compliance,
    }
```

Change `build_layered_generated_image` signature:

```python
async def build_layered_generated_image(
    *,
    module: dict[str, Any],
    product_info: dict[str, Any] | None,
    base_url: str,
    promotion_info: str | None = None,
    platform_id: str | None = None,
) -> dict[str, Any]:
```

Pass values into default rendering:

```python
    default_version = await render_layered_language_version(
        base_url=base_url,
        layers=layers,
        language=DEFAULT_LANGUAGE,
        folder=f"generated/{module_id}/languages",
        module_id=module_id,
        platform_id=platform_id,
        product_info=product_info,
    )
```

Return top-level compliance:

```python
    return {
        "module_id": module_id,
        "url": default_version["url"],
        "base_url": base_url,
        "text_layers": layers,
        "language_versions": {DEFAULT_LANGUAGE: default_version},
        "compliance": default_version["compliance"],
    }
```

- [ ] **Step 5: Thread platform id through generation**

Update the existing `_generate_module_image` signature so it includes `platform_id` between `platform_size` and `image_model_id`:

```python
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
) -> tuple[dict[str, Any] | None, str | None]:
```

Update the existing `generate_detail_images` signature so it includes `platform_id` between `platform_size` and `image_model_id`:

```python
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
) -> dict[str, Any]:
```

Update the existing `edit_generated_image` signature so it includes `platform_id` at the end:

```python
async def edit_generated_image(
    image_url: str,
    instruction: str,
    platform_size: str | None = None,
    image_model_id: str | None = None,
    platform_id: str | None = None,
) -> dict[str, Any]:
```

Every call to `build_layered_generated_image` inside `_generate_module_image` must include:

```python
platform_id=platform_id,
```

Every call to `_generate_module_image` inside `generate_detail_images` must include:

```python
platform_id=platform_id,
```

Every call to `generate_detail_images` from `run_generation_job` and `generate_project` must pass the request value:

```python
platform_id=payload.get("platform_id"),
```

and:

```python
platform_id=request.platform_id,
```

Update `GenerateRequest`:

```python
platform_id: str | None = None
```

Update `_generation_payload_from_request`:

```python
"platform_id": request.platform_id,
```

- [ ] **Step 6: Return compliance from edit requests**

At the start of `edit_generated_image`, after `cleaned_instruction` validation, add:

```python
    compliance = check_project_text_compliance(
        [
            {
                "text": cleaned_instruction,
                "location": {"source_type": "edit_instruction", "field": "instruction"},
            }
        ],
        platform_id=platform_id,
    )
```

Change the success return to:

```python
    return {"source": "model", "url": url, "compliance": compliance}
```

Update `EditImageRequest`:

```python
platform_id: str | None = None
```

Update `edit_project_image`:

```python
return await edit_generated_image(
    request.image_url,
    request.instruction,
    platform_size=request.platform_size,
    image_model_id=request.image_model_id,
    platform_id=request.platform_id,
)
```

- [ ] **Step 7: Add compliance API request models and endpoints**

Inside the `try:` router model section of `backend/app/routers/projects.py`, add:

```python
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
```

Add endpoints before `/download-image`:

```python
    @router.post("/compliance/check-text")
    async def check_project_text_compliance_endpoint(request: ComplianceCheckTextRequest) -> dict[str, Any]:
        items = [
            {"text": item.text, "location": item.location.model_dump()}
            for item in request.items
        ]
        return check_project_text_compliance(
            items,
            platform_id=request.platform_id,
            product_info=request.product_info,
            debug=request.debug,
        )

    @router.post("/compliance/check-images")
    async def check_project_image_compliance_endpoint(request: ComplianceCheckImagesRequest) -> dict[str, Any]:
        return {
            "source": "ocr_noop",
            "summary": {"status": "pass", "block_count": 0, "warn_count": 0, "review_count": 0},
            "issues": [],
            "image_count": len(request.image_urls),
            "platform_id": request.platform_id,
        }
```

- [ ] **Step 8: Update render-language endpoint**

Update `RenderLanguageRequest`:

```python
platform_id: str | None = None
product_info: dict[str, Any] | None = None
```

Update the call in `render_project_language`:

```python
            version = await render_layered_language_version(
                base_url=request.base_url,
                layers=request.text_layers,
                language=request.language,
                platform_id=request.platform_id,
                product_info=request.product_info,
            )
```

- [ ] **Step 9: Run backend integration tests**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/backend
PYTHONPATH=. python -m unittest tests.test_api_contracts -v
PYTHONPATH=. python -m unittest tests.test_compliance_checker -v
```

Expected: both test modules pass.

- [ ] **Step 10: Commit backend integration**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
git add backend/app/routers/projects.py backend/tests/test_api_contracts.py
git commit -m "Attach compliance reports to project APIs"
```

Expected: commit succeeds and only the two listed files are included in this commit.

## Task 3: Frontend Types, API, And State Plumbing

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`
- Create: `frontend/lib/compliance.ts`
- Modify: `frontend/lib/projectEnhancements.ts`
- Modify: `frontend/tests/project-enhancements.test.cjs`
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Write failing project enhancement tests**

In `frontend/tests/project-enhancements.test.cjs`, extend the destructuring to include no new helper. Modify the existing `layered` input object by adding:

```js
      compliance: { source: "rules", summary: { status: "block", block_count: 1, warn_count: 0, review_count: 0 }, issues: [{ term: "治愈" }] },
```

Also add the same report to the existing `language_versions["zh-CN"]` object:

```js
      language_versions: {
        "zh-CN": {
          language: "zh-CN",
          language_label: "中文",
          url: "hero-zh.png",
          compliance: { source: "rules", summary: { status: "block", block_count: 1, warn_count: 0, review_count: 0 }, issues: [{ term: "治愈" }] }
        }
      }
```

Add these assertions after `assert.equal(layeredVersion.languageVersions["zh-CN"].url, "hero-zh.png");`:

```js
assert.equal(layeredVersion.compliance.summary.status, "block");
assert.equal(layeredVersion.languageVersions["zh-CN"].compliance.summary.status, "block");
```

Modify the `withEnglish` `addLanguageVersion` input to include:

```js
  compliance: { source: "rules", summary: { status: "warn", block_count: 0, warn_count: 1, review_count: 0 }, issues: [{ term: "100%" }] },
```

Add this assertion after `assert.equal(withEnglish.versions.hero[0].languageVersions.en.url, "hero-en.png");`:

```js
assert.equal(withEnglish.versions.hero[0].languageVersions.en.compliance.summary.status, "warn");
```

- [ ] **Step 2: Run frontend helper test to verify failure**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
npm run test -- --runInBand
```

Expected: FAIL in `project-enhancements.test.cjs` because compliance fields are not preserved. If the extra argument is ignored by npm scripts, run `node tests/project-enhancements.test.cjs` and expect the same failure.

- [ ] **Step 3: Add compliance types**

Modify `frontend/lib/types.ts` by adding after `CommercePlatform`:

```ts
export type ComplianceStatus = "pass" | "review" | "warn" | "block";
export type ComplianceSeverity = "review" | "warn" | "block";

export type ComplianceSummary = {
  status: ComplianceStatus;
  block_count: number;
  warn_count: number;
  review_count: number;
};

export type ComplianceIssue = {
  id?: string;
  severity: ComplianceSeverity;
  category: string;
  platform_ids?: CommercePlatformId[];
  term: string;
  matched_text?: string;
  location?: {
    source_type?: string;
    module_id?: string;
    field?: string;
    language?: string;
  };
  reason: string;
  suggestion: string;
  qualification_hint?: string;
};

export type ComplianceReport = {
  source: string;
  summary: ComplianceSummary;
  issues: ComplianceIssue[];
  ignored_matches?: Array<{ term: string; text: string; reason: string }>;
};

export type ComplianceTextItem = {
  text: string;
  location: {
    source_type: string;
    module_id?: string;
    field?: string;
    language?: string;
  };
};
```

Add `compliance?: ComplianceReport;` to `GeneratedImageVersion`.

Add `compliance?: ComplianceReport;` to `GeneratedImage`.

Add `compliance?: ComplianceReport;` to `LanguageVersion`.

- [ ] **Step 4: Preserve compliance in project enhancements**

Modify the imports in `frontend/lib/projectEnhancements.ts` to include `ComplianceReport`.

Change `GeneratedImageInput`:

```ts
type GeneratedImageInput = { module_id: string; url: string; compliance?: ComplianceReport };
```

Change `LayeredGeneratedImageInput`:

```ts
type LayeredGeneratedImageInput = GeneratedImageInput & {
  base_url?: string;
  text_layers?: GeneratedImageVersion["textLayers"];
  language_versions?: GeneratedImageVersion["languageVersions"];
};
```

Inside `nextVersion`, add:

```ts
      ...(image.compliance ? { compliance: image.compliance } : {}),
```

No change is needed in `addLanguageVersion` if `LanguageVersion` already carries `compliance`; the existing spread preserves it.

- [ ] **Step 5: Create frontend compliance helpers**

Create `frontend/lib/compliance.ts`:

```ts
import type { ComplianceReport, ComplianceStatus, ComplianceTextItem, ProductInfo } from "./types";

const statusRank: Record<ComplianceStatus, number> = { pass: 0, review: 1, warn: 2, block: 3 };

export function complianceStatusLabel(status: ComplianceStatus) {
  if (status === "block") return "高风险";
  if (status === "warn") return "有风险";
  if (status === "review") return "需确认";
  return "通过";
}

export function complianceStatusClass(status: ComplianceStatus) {
  return `compliance-${status}`;
}

export function highestComplianceStatus(reports: Array<ComplianceReport | null | undefined>): ComplianceStatus {
  return reports.reduce<ComplianceStatus>((highest, report) => {
    const status = report?.summary.status ?? "pass";
    return statusRank[status] > statusRank[highest] ? status : highest;
  }, "pass");
}

export function buildProductInfoComplianceItems(productInfo: ProductInfo | null): ComplianceTextItem[] {
  if (!productInfo) return [];
  const items: ComplianceTextItem[] = [];
  const push = (field: string, value: unknown) => {
    if (Array.isArray(value)) {
      value.forEach((entry, index) => push(`${field}.${index}`, entry));
      return;
    }
    if (value && typeof value === "object") {
      Object.entries(value as Record<string, unknown>).forEach(([key, entry]) => push(`${field}.${key}`, entry));
      return;
    }
    const text = String(value ?? "").trim();
    if (!text) return;
    items.push({ text, location: { source_type: "field", field } });
  };

  push("product_name", productInfo.product_name);
  push("core_selling_points", productInfo.core_selling_points);
  push("functions", productInfo.functions);
  push("ingredients", productInfo.ingredients);
  push("usage_method", productInfo.usage_method);
  push("authority_assets", productInfo.authority_assets);
  push("effect_claims", productInfo.effect_claims);
  push("material_highlights", productInfo.material_highlights ?? []);
  return items;
}
```

- [ ] **Step 6: Add frontend API plumbing**

Modify the type import in `frontend/lib/api.ts`:

```ts
import type { CommercePlatformId, ComplianceReport, ComplianceTextItem, GenerationMode, LanguageCode, LanguageVersion, MaterialPayload, ModuleConfig, ProductInfo, PublicModelConfig, StyleOption, TextLayer } from "./types";
```

Update `generateImages` and `createGenerateImageJob` signatures to include `platformId: CommercePlatformId` before `layeredText`:

```ts
  generationMode: GenerationMode = "reference_generate",
  platformId: CommercePlatformId = "tmall",
  layeredText = false
```

Add `platform_id: platformId` to the job body.

Update the call from `generateImages` to `createGenerateImageJob` so it passes `platformId` immediately before `layeredText`.

Update `GenerateImagesResult.images` item type:

```ts
    compliance?: ComplianceReport;
```

Update `renderLanguageVersion` signature:

```ts
export async function renderLanguageVersion(baseUrl: string, textLayers: TextLayer[], language: LanguageCode, platformId: CommercePlatformId, productInfo?: ProductInfo | null) {
```

Add to body:

```ts
        platform_id: platformId,
        product_info: productInfo
```

Update `editGeneratedImage` signature:

```ts
export async function editGeneratedImage(imageUrl: string, instruction: string, platformSize = "", imageModelId = "", platformId: CommercePlatformId = "tmall") {
```

Add to body:

```ts
        platform_id: platformId
```

Update edit response type:

```ts
return await requestJson<{ source: string; url?: string; error?: string; compliance?: ComplianceReport }>("/api/projects/edit-image", {
```

Add this API function:

```ts
export async function checkTextCompliance(items: ComplianceTextItem[], platformId: CommercePlatformId, productInfo?: ProductInfo | null) {
  try {
    return await requestJson<ComplianceReport>("/api/projects/compliance/check-text", {
      method: "POST",
      body: JSON.stringify({
        items,
        platform_id: platformId,
        product_info: productInfo
      }),
      timeoutMs: 15000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      summary: { status: "pass" as const, block_count: 0, warn_count: 0, review_count: 0 },
      issues: []
    };
  }
}
```

- [ ] **Step 7: Thread compliance through page state**

Modify imports in `frontend/app/page.tsx`:

```ts
  checkTextCompliance,
```

and:

```ts
import { buildProductInfoComplianceItems } from "@/lib/compliance";
```

and include `ComplianceReport` in the type import.

Add state after `analysisSource`:

```ts
const [reviewCompliance, setReviewCompliance] = useState<ComplianceReport | null>(null);
const [promotionCompliance, setPromotionCompliance] = useState<ComplianceReport | null>(null);
```

Add this effect after the persistence effects:

```ts
  useEffect(() => {
    if (!hasAiProductInfo || !productInfo) {
      setReviewCompliance(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void checkTextCompliance(buildProductInfoComplianceItems(productInfo), selectedPlatformId, productInfo).then(setReviewCompliance);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [hasAiProductInfo, productInfo, selectedPlatformId]);
```

Update `handleGenerateLanguage` call:

```ts
      const result = await renderLanguageVersion(version.baseUrl, version.textLayers, language, selectedPlatformId, productInfo);
```

Update `handleEditImage` call:

```ts
    const result = await editGeneratedImage(imageUrl, trimmed, selectedPlatform.generationSize, selectedImageModelId, selectedPlatformId);
```

Update append after edit:

```ts
        appendImageVersions(current, [{ module_id: moduleId, url: result.url as string, compliance: result.compliance }], "edit", Date.now(), trimmed)
```

Inside `handleGenerate`, before setting progress, add:

```ts
    if (group === "campaign") {
      const report = await checkTextCompliance(
        [{ text: promotionInfo, location: { source_type: "promotion", field: "promotion_info" } }],
        selectedPlatformId,
        productInfo
      );
      setPromotionCompliance(report);
    }
```

Update the `generateImages` call to pass `selectedPlatformId` before `true`:

```ts
            selectedGenerationMode,
            selectedPlatformId,
            true
```

Pass props:

```tsx
            complianceReport={reviewCompliance}
```

to `ReviewStep`.

Pass:

```tsx
            promotionCompliance={promotionCompliance}
```

to `ModulesStep`.

- [ ] **Step 8: Run frontend helper tests**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
node tests/project-enhancements.test.cjs
```

Expected: PASS and output `Project enhancement checks passed.`

- [ ] **Step 9: Commit frontend plumbing**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
git add frontend/lib/types.ts frontend/lib/api.ts frontend/lib/compliance.ts frontend/lib/projectEnhancements.ts frontend/tests/project-enhancements.test.cjs frontend/app/page.tsx
git commit -m "Wire compliance reports through frontend state"
```

Expected: commit succeeds and only the six listed paths are included in this commit.

## Task 4: Frontend Compliance UI

**Files:**
- Modify: `frontend/components/ReviewStep.tsx`
- Modify: `frontend/components/ModulesStep.tsx`
- Modify: `frontend/components/PreviewStep.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/tests/static-ui-contract.test.cjs`

- [ ] **Step 1: Write failing static UI checks**

Add these checks near the other compliance-relevant frontend assertions in `frontend/tests/static-ui-contract.test.cjs`:

```js
assertIncludes("components/ReviewStep.tsx", "合规风险", "review step must show product-info compliance risks");
assertIncludes("components/ModulesStep.tsx", "促销合规预检", "modules step must show campaign promotion compliance preflight");
assertIncludes("components/PreviewStep.tsx", "ComplianceBadge", "preview step must render compliance badges on generated images");
assertIncludes("components/PreviewStep.tsx", "导出前合规提示", "preview export area must summarize selected image compliance");
assertIncludes("app/globals.css", "complianceBadge", "global styles must include compliance badge styling");
assertIncludes("app/globals.css", "complianceIssueList", "global styles must include compliance issue list styling");
```

- [ ] **Step 2: Run static UI checks to verify failure**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
node tests/static-ui-contract.test.cjs
```

Expected: FAIL because the new compliance strings and CSS classes are not rendered.

- [ ] **Step 3: Add ReviewStep compliance panel**

Modify imports in `frontend/components/ReviewStep.tsx`:

```ts
import { complianceStatusClass, complianceStatusLabel } from "@/lib/compliance";
import type { ComplianceReport, ProductInfo } from "@/lib/types";
```

Update props:

```ts
  complianceReport,
```

and prop type:

```ts
  complianceReport?: ComplianceReport | null;
```

Add this block after the `fieldList` rendering:

```tsx
          {complianceReport ? (
            <aside className={`compliancePanel ${complianceStatusClass(complianceReport.summary.status)}`}>
              <header>
                <b>合规风险</b>
                <span>{complianceStatusLabel(complianceReport.summary.status)}</span>
              </header>
              {complianceReport.issues.length ? (
                <ul className="complianceIssueList">
                  {complianceReport.issues.slice(0, 5).map((issue, index) => (
                    <li key={`${issue.term}-${index}`}>
                      <strong>{issue.term}</strong>
                      <span>{issue.reason}</span>
                      <em>{issue.suggestion}</em>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>当前提炼文案未发现明显违规词。</p>
              )}
            </aside>
          ) : null}
```

- [ ] **Step 4: Add ModulesStep promotion compliance panel**

Modify imports in `frontend/components/ModulesStep.tsx`:

```ts
import { complianceStatusClass, complianceStatusLabel } from "@/lib/compliance";
import type { CommercePlatform, CommercePlatformId, ComplianceReport, GenerationMode, ImageGroup, ModuleConfig, ProjectTemplate, PublicModelConfig, StyleOption, StyleSource } from "@/lib/types";
```

Add prop:

```ts
  promotionCompliance,
```

and prop type:

```ts
  promotionCompliance?: ComplianceReport | null;
```

Inside the campaign block, after the promotion `<label>`, add:

```tsx
            {promotionCompliance ? (
              <div className={`compliancePanel compact ${complianceStatusClass(promotionCompliance.summary.status)}`}>
                <header>
                  <b>促销合规预检</b>
                  <span>{complianceStatusLabel(promotionCompliance.summary.status)}</span>
                </header>
                {promotionCompliance.issues.length ? (
                  <ul className="complianceIssueList">
                    {promotionCompliance.issues.slice(0, 3).map((issue, index) => (
                      <li key={`${issue.term}-${index}`}>
                        <strong>{issue.term}</strong>
                        <span>{issue.reason}</span>
                        <em>{issue.suggestion}</em>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>当前促销文案未发现明显违规词。</p>
                )}
              </div>
            ) : null}
```

- [ ] **Step 5: Add PreviewStep compliance badges and summary**

Modify imports in `frontend/components/PreviewStep.tsx`:

```ts
import { complianceStatusClass, complianceStatusLabel, highestComplianceStatus } from "@/lib/compliance";
import type { CommercePlatform, ComplianceReport, GeneratedImageVersion, GeneratedImageVersionState, ImageGroup, LanguageCode, ModuleConfig } from "@/lib/types";
```

Add helpers above `LanguageVersionControls`:

```tsx
function ComplianceBadge({ report }: { report?: ComplianceReport | null }) {
  const status = report?.summary.status ?? "pass";
  return <span className={`complianceBadge ${complianceStatusClass(status)}`}>{complianceStatusLabel(status)}</span>;
}

function ComplianceIssueList({ report }: { report?: ComplianceReport | null }) {
  if (!report?.issues.length) return null;
  return (
    <ul className="complianceIssueList compact">
      {report.issues.slice(0, 3).map((issue, index) => (
        <li key={`${issue.term}-${index}`}>
          <strong>{issue.term}</strong>
          <span>{issue.reason}</span>
          <em>{issue.suggestion}</em>
        </li>
      ))}
    </ul>
  );
}
```

Inside each main image card footer, after `<b>{module.name}</b>`, add:

```tsx
                          <ComplianceBadge report={selectedVersion?.compliance} />
```

After `LanguageVersionControls` in the main card, add:

```tsx
                        <ComplianceIssueList report={selectedVersion?.compliance} />
```

Inside each long image controls header, after `<b>{item.module.name}</b>`, add:

```tsx
                          <ComplianceBadge report={selectedVersion?.compliance} />
```

After long image `LanguageVersionControls`, add:

```tsx
                          <ComplianceIssueList report={selectedVersion?.compliance} />
```

Before `<div className="exportActions">`, compute and render summary in JSX:

```tsx
          {(() => {
            const reports = visibleModules.map((module) => selectedVersionForModule(imageVersions, selectedVersionIds, module.id)?.compliance);
            const status = highestComplianceStatus(reports);
            return (
              <div className={`exportComplianceSummary ${complianceStatusClass(status)}`}>
                <b>导出前合规提示</b>
                <span>{complianceStatusLabel(status)}</span>
              </div>
            );
          })()}
```

- [ ] **Step 6: Add CSS styles**

Append to `frontend/app/globals.css`:

```css
.compliancePanel {
  margin-top: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px;
  background: #fffdf8;
}

.compliancePanel.compact {
  margin-top: 10px;
}

.compliancePanel header,
.exportComplianceSummary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.complianceBadge,
.compliancePanel header span,
.exportComplianceSummary span {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.compliance-pass {
  background: #e8f7ef;
  color: #167247;
}

.compliance-review {
  background: #fff6d8;
  color: #8a5a00;
}

.compliance-warn {
  background: #ffe9d6;
  color: #9a4a00;
}

.compliance-block {
  background: #ffe1e1;
  color: #9d1c1c;
}

.complianceIssueList {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.complianceIssueList.compact {
  margin-top: 10px;
}

.complianceIssueList li {
  display: grid;
  gap: 3px;
  padding: 9px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.complianceIssueList strong {
  font-size: 13px;
}

.complianceIssueList span,
.complianceIssueList em {
  font-size: 12px;
  line-height: 1.45;
  color: var(--muted);
  font-style: normal;
}

.exportComplianceSummary {
  margin: 12px 0;
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}
```

- [ ] **Step 7: Run static UI checks**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
node tests/static-ui-contract.test.cjs
```

Expected: PASS and output `Static UI contract checks passed.`

- [ ] **Step 8: Commit frontend UI**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
git add frontend/components/ReviewStep.tsx frontend/components/ModulesStep.tsx frontend/components/PreviewStep.tsx frontend/app/globals.css frontend/tests/static-ui-contract.test.cjs
git commit -m "Show compliance risks in the image workflow"
```

Expected: commit succeeds and only the five listed paths are included in this commit.

## Task 5: Full Verification And Handoff

**Files:**
- No source files unless verification exposes a concrete failing check.

- [ ] **Step 1: Run backend unit and contract tests**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/backend
PYTHONPATH=. python -m unittest tests.test_compliance_checker tests.test_api_contracts -v
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend test suite**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
npm test
```

Expected: `Static UI contract checks passed.`, `Product info merge checks passed.`, and `Project enhancement checks passed.`

- [ ] **Step 3: Run production build**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片/frontend
npm run build
```

Expected: Next.js build completes without TypeScript or rendering errors.

- [ ] **Step 4: Inspect git status**

Run:

```bash
cd /Users/a123/Desktop/自动生成店铺图片
git status --short
```

Expected: only pre-existing unrelated user changes remain. No unstaged changes from this implementation should remain outside committed files.

- [ ] **Step 5: Final implementation summary**

Report:

```text
Implemented platform compliance detection.
Backend: rule engine, text API, image no-op API, generation/language/edit integration.
Frontend: product and promotion preflight, image badges, export summary, persistence through versions.
Verification: backend unittest, frontend npm test, frontend build.
```
