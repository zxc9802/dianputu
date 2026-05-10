import unittest

from app.services.compliance_checker import check_image_items, check_text_items


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


class ImageComplianceCheckerTests(unittest.IsolatedAsyncioTestCase):
    async def test_uses_ai_provider_report_for_final_image_review(self):
        class FakeImageComplianceProvider:
            source = "fake_ai"

            async def check_image(self, image_bytes, *, location, platform_id=None, product_info=None, debug=False):
                self.image_bytes = image_bytes
                self.location = location
                self.platform_id = platform_id
                self.product_info = product_info
                return {
                    "issues": [
                        {
                            "id": "ai_medical_claim",
                            "severity": "block",
                            "category": "medical_claim",
                            "platform_ids": ["tmall"],
                            "term": "治愈",
                            "matched_text": "7天治愈敏感肌",
                            "location": location,
                            "reason": "AI 判断图片文案含普通护肤品不应使用的治疗化表达。",
                            "suggestion": "改为舒缓不适肤感或帮助维持肌肤稳定。",
                            "qualification_hint": "",
                        }
                    ],
                    "extracted_texts": [{"text": "7天治愈敏感肌", "confidence": 0.96, "box": [10, 20, 180, 60], "location": location}],
                    "warnings": [],
                }

        provider = FakeImageComplianceProvider()
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
            product_info={"product_name": "修护精华"},
        )

        self.assertEqual(provider.image_bytes, b"fake-image")
        self.assertEqual(provider.platform_id, "tmall")
        self.assertEqual(provider.product_info, {"product_name": "修护精华"})
        self.assertEqual(report["source"], "image_ai")
        self.assertEqual(report["ai_source"], "fake_ai")
        self.assertEqual(report["image_count"], 1)
        self.assertEqual(report["summary"]["status"], "block")
        self.assertEqual(report["issues"][0]["term"], "治愈")
        self.assertEqual(report["issues"][0]["location"]["source_type"], "image_ai")
        self.assertEqual(report["issues"][0]["location"]["module_id"], "main_effect")
        self.assertEqual(report["issues"][0]["location"]["image_index"], 0)
        self.assertEqual(report["extracted_texts"][0]["text"], "7天治愈敏感肌")
        self.assertEqual(report["extracted_texts"][0]["confidence"], 0.96)

    async def test_marks_review_when_ai_provider_is_unavailable(self):
        class UnavailableImageComplianceProvider:
            source = "vision_model"

            async def check_image(self, image_bytes, *, location, platform_id=None, product_info=None, debug=False):
                from app.services.compliance_checker import ImageComplianceProviderUnavailableError

                raise ImageComplianceProviderUnavailableError("TEXT_ANALYSIS_API_KEY is not configured")

        report = await check_image_items(
            [{"url": "https://example.com/generated.png", "bytes": b"fake-image"}],
            compliance_provider=UnavailableImageComplianceProvider(),
            platform_id="jd",
        )

        self.assertEqual(report["source"], "image_ai")
        self.assertEqual(report["summary"]["status"], "review")
        self.assertEqual(report["summary"]["review_count"], 1)
        self.assertEqual(report["issues"][0]["id"], "image_ai_review_unavailable")
        self.assertEqual(report["issues"][0]["severity"], "review")
        self.assertIn("Gemini", report["issues"][0]["term"])
        self.assertIn("Gemini", report["issues"][0]["reason"])
        self.assertIn("Gemini 3.1 Pro", report["issues"][0]["suggestion"])
        self.assertNotIn("OCR", report["issues"][0]["reason"])
        self.assertIn("TEXT_ANALYSIS_API_KEY", report["issues"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
