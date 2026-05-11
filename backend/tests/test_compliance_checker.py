import asyncio
import unittest

from app.services.compliance_checker import ComplianceProviderUnavailableError, check_image_items, check_text_items


def model_report(status="pass", issues=None):
    issue_list = issues or []
    return {
        "summary": {
            "status": status,
            "block_count": sum(1 for issue in issue_list if issue.get("severity") == "block"),
            "warn_count": sum(1 for issue in issue_list if issue.get("severity") == "warn"),
            "review_count": sum(1 for issue in issue_list if issue.get("severity") == "review"),
        },
        "issues": issue_list,
    }


class TextComplianceCheckerTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_review_uses_model_provider_instead_of_local_rules(self):
        class FakeComplianceProvider:
            source = "fake_gemini"

            async def review_text(self, items, *, platform_id=None, product_info=None, debug=False):
                self.items = items
                self.platform_id = platform_id
                self.product_info = product_info
                return model_report(
                    "warn",
                    [
                        {
                            "id": "gemini_sensitive_claim",
                            "severity": "warn",
                            "category": "medical_claim",
                            "term": "治愈",
                            "matched_text": "7天治愈敏感肌",
                            "location": items[0]["location"],
                            "reason": "普通护肤品不应使用治疗或治愈表达。",
                            "suggestion": "改为舒缓不适肤感。",
                        }
                    ],
                )

        provider = FakeComplianceProvider()
        report = await check_text_items(
            [
                {
                    "text": "7天治愈敏感肌",
                    "location": {"source_type": "field", "field": "core_selling_points"},
                }
            ],
            compliance_provider=provider,
            platform_id="tmall",
            product_info={"product_name": "修护精华"},
        )

        self.assertEqual(provider.platform_id, "tmall")
        self.assertEqual(provider.product_info["product_name"], "修护精华")
        self.assertEqual(provider.items[0]["text"], "7天治愈敏感肌")
        self.assertEqual(report["source"], "fake_gemini")
        self.assertEqual(report["summary"]["status"], "warn")
        self.assertEqual(report["issues"][0]["term"], "治愈")

    async def test_text_review_marks_review_when_model_is_unavailable(self):
        class UnavailableComplianceProvider:
            source = "gemini"

            async def review_text(self, items, *, platform_id=None, product_info=None, debug=False):
                raise ComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        report = await check_text_items(
            [{"text": "舒缓保湿", "location": {"source_type": "field", "field": "functions"}}],
            compliance_provider=UnavailableComplianceProvider(),
            platform_id="jd",
        )

        self.assertEqual(report["source"], "gemini")
        self.assertEqual(report["summary"], {"status": "review", "block_count": 0, "warn_count": 0, "review_count": 1})
        self.assertEqual(report["issues"][0]["id"], "model_compliance_unavailable")
        self.assertIn("TEXT_ANALYSIS_API_KEY", report["issues"][0]["reason"])


class ImageComplianceCheckerTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_review_runs_up_to_three_reviews_concurrently(self):
        class SlowComplianceProvider:
            source = "fake_gemini"

            def __init__(self):
                self.active_count = 0
                self.max_active_count = 0
                self.lock = asyncio.Lock()

            async def review_image(self, image_bytes, *, metadata, platform_id=None, product_info=None, debug=False):
                async with self.lock:
                    self.active_count += 1
                    self.max_active_count = max(self.max_active_count, self.active_count)
                try:
                    await asyncio.sleep(0.02)
                finally:
                    async with self.lock:
                        self.active_count -= 1
                return model_report("pass")

        provider = SlowComplianceProvider()
        report = await check_image_items(
            [{"url": f"https://example.com/{index}.png", "bytes": b"fake-image"} for index in range(5)],
            compliance_provider=provider,
            platform_id="tmall",
        )

        self.assertEqual(report["summary"]["status"], "pass")
        self.assertEqual(report["image_count"], 5)
        self.assertEqual(provider.max_active_count, 3)

    async def test_image_review_sends_image_to_model_provider(self):
        class FakeComplianceProvider:
            source = "fake_gemini"

            async def review_image(self, image_bytes, *, metadata, platform_id=None, product_info=None, debug=False):
                self.image_bytes = image_bytes
                self.metadata = metadata
                return model_report(
                    "block",
                    [
                        {
                            "id": "gemini_image_claim",
                            "severity": "block",
                            "category": "absolute_claim",
                            "term": "100%",
                            "matched_text": "100%有效",
                            "location": metadata["location"],
                            "reason": "绝对化数据表达需要删除或提供依据。",
                            "suggestion": "改为有依据的数据表达。",
                        }
                    ],
                )

        provider = FakeComplianceProvider()
        report = await check_image_items(
            [
                {
                    "url": "data:image/png;base64,abc",
                    "bytes": b"fake-image",
                    "module_id": "main_effect",
                }
            ],
            compliance_provider=provider,
            platform_id="tmall",
        )

        self.assertEqual(provider.image_bytes, b"fake-image")
        self.assertEqual(provider.metadata["location"]["source_type"], "image_review")
        self.assertEqual(provider.metadata["location"]["module_id"], "main_effect")
        self.assertEqual(report["source"], "fake_gemini")
        self.assertEqual(report["image_count"], 1)
        self.assertEqual(report["summary"]["status"], "block")
        self.assertEqual(report["issues"][0]["term"], "100%")
        self.assertEqual(set(report), {"source", "summary", "issues", "image_count", "warnings"})

    async def test_image_review_marks_review_when_model_is_unavailable(self):
        class UnavailableComplianceProvider:
            source = "gemini"

            async def review_image(self, image_bytes, *, metadata, platform_id=None, product_info=None, debug=False):
                raise ComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        report = await check_image_items(
            [{"url": "https://example.com/generated.png", "bytes": b"fake-image"}],
            compliance_provider=UnavailableComplianceProvider(),
            platform_id="jd",
        )

        self.assertEqual(report["source"], "gemini")
        self.assertEqual(report["summary"]["status"], "review")
        self.assertEqual(report["summary"]["review_count"], 1)
        self.assertEqual(report["issues"][0]["id"], "model_compliance_unavailable")
        self.assertEqual(report["issues"][0]["severity"], "review")


if __name__ == "__main__":
    unittest.main()
