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
