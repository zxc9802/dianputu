DEFAULT_PRODUCT_INFO = {
    "product_name": "CICA 修护精华",
    "category": "护肤精华",
    "spec": "30ml",
    "core_selling_points": ["舒缓泛红不适", "补水锁水", "强韧肌肤屏障"],
    "functions": ["舒缓", "补水", "修护屏障"],
    "ingredients": [
        {"name": "积雪草", "benefit": "帮助舒缓泛红与脆弱不适"},
        {"name": "神经酰胺", "benefit": "帮助强韧肌肤屏障"},
        {"name": "透明质酸", "benefit": "补充水分，帮助锁水维稳"},
    ],
    "target_users": ["换季泛红人群", "干燥紧绷人群", "屏障脆弱人群"],
    "usage_method": ["洁面后使用", "取 2-3 滴于掌心", "均匀涂抹全脸", "轻拍至吸收"],
    "authority_assets": ["实验室研发", "实验报告", "专研配方理念"],
    "effect_claims": [
        {"claim": "肌肤更水润", "value": "92%", "source_type": "ai_generated"},
        {"claim": "泛红不适有所缓解", "value": "88%", "source_type": "ai_generated"},
    ],
    "confirmation_status": "pending",
}


DEFAULT_MODULES = [
    {"id": "main_white_bg", "name": "白底图", "description": "纯白背景 + 产品居中", "enabled": True, "order": 1, "image_group": "main"},
    {"id": "main_hero_selling_point", "name": "首图", "description": "产品图 + 一句话核心卖点", "enabled": True, "order": 2, "image_group": "main"},
    {"id": "main_ingredient", "name": "次图-成分", "description": "核心成分 + 原料质感", "enabled": True, "order": 3, "image_group": "main"},
    {"id": "main_effect", "name": "次图-效果", "description": "核心功效 + 使用收益", "enabled": True, "order": 4, "image_group": "main"},
    {"id": "main_usage_scene", "name": "次图-使用场景", "description": "目标人群 + 生活场景", "enabled": True, "order": 5, "image_group": "main"},
    {"id": "campaign_white_bg", "name": "活动白底图", "description": "白底商品 + 促销角标", "enabled": True, "order": 1, "image_group": "campaign"},
    {"id": "campaign_hero_selling_point", "name": "活动首图", "description": "产品图 + 核心卖点 + 促销利益点", "enabled": True, "order": 2, "image_group": "campaign"},
    {"id": "campaign_ingredient", "name": "活动次图-成分", "description": "核心成分 + 活动氛围", "enabled": True, "order": 3, "image_group": "campaign"},
    {"id": "campaign_effect", "name": "活动次图-效果", "description": "核心功效 + 促销转化", "enabled": True, "order": 4, "image_group": "campaign"},
    {"id": "campaign_usage_scene", "name": "活动次图-使用场景", "description": "使用场景 + 活动元素", "enabled": True, "order": 5, "image_group": "campaign"},
    {"id": "hero", "name": "详情首图", "description": "产品大图 + 核心卖点", "enabled": True, "order": 1, "image_group": "detail"},
    {"id": "authority", "name": "权威资质展示", "description": "实验室 / 科学家 / 报告 / 专利", "enabled": True, "order": 2, "image_group": "detail"},
    {"id": "pain_scene", "name": "痛点场景", "description": "皮肤问题 + 尝试无效", "enabled": True, "order": 3, "image_group": "detail"},
    {"id": "effect_comparison", "name": "效果对比", "description": "使用前后 + 百分比数据", "enabled": True, "order": 4, "image_group": "detail"},
    {"id": "competitor_comparison", "name": "竞品对比", "description": "质地 / 成分 / 效果 / 负面体验", "enabled": True, "order": 5, "image_group": "detail"},
    {"id": "ingredient_overview", "name": "成分总览", "description": "整体成分体系 + 配方逻辑", "enabled": True, "order": 6, "image_group": "detail"},
    {"id": "ingredient_1", "name": "成分 1 讲解", "description": "第 1 个核心成分作用讲解", "enabled": True, "order": 7, "image_group": "detail"},
    {"id": "ingredient_2", "name": "成分 2 讲解", "description": "第 2 个核心成分作用讲解", "enabled": True, "order": 8, "image_group": "detail"},
    {"id": "ingredient_3", "name": "成分 3 讲解", "description": "第 3 个核心成分作用讲解", "enabled": True, "order": 9, "image_group": "detail"},
    {"id": "usage", "name": "使用方法", "description": "商品怎么用", "enabled": True, "order": 10, "image_group": "detail"},
]


STYLE_OPTIONS = [
    {
        "id": "green_repair",
        "name": "绿色修护风",
        "keywords": ["植物", "水滴", "温和", "屏障修护"],
        "primary_color": "#1F8C43",
        "asset": "/assets/style-green-repair.png",
    },
    {
        "id": "blue_hydration",
        "name": "蓝色补水风",
        "keywords": ["清透", "水膜", "水润", "透明质酸"],
        "primary_color": "#347FB9",
        "asset": "/assets/style-blue-hydration.png",
    },
    {
        "id": "gold_antiaging",
        "name": "金色抗老风",
        "keywords": ["胶原", "高级", "紧致", "金色光泽"],
        "primary_color": "#B88727",
        "asset": "/assets/style-gold-antiaging.png",
    },
]


DEMO_IMAGE_URLS = {
    "main_white_bg": "/assets/generated-cica-asset-sheet.png",
    "main_hero_selling_point": "/assets/generated-cica-asset-sheet.png",
    "main_ingredient": "/assets/generated-cica-asset-sheet.png",
    "main_effect": "/assets/generated-cica-asset-sheet.png",
    "main_usage_scene": "/assets/generated-cica-asset-sheet.png",
    "campaign_white_bg": "/assets/generated-cica-asset-sheet.png",
    "campaign_hero_selling_point": "/assets/generated-cica-asset-sheet.png",
    "campaign_ingredient": "/assets/generated-cica-asset-sheet.png",
    "campaign_effect": "/assets/generated-cica-asset-sheet.png",
    "campaign_usage_scene": "/assets/generated-cica-asset-sheet.png",
    "hero": "/assets/generated-cica-asset-sheet.png",
    "authority": "/assets/generated-cica-asset-sheet.png",
    "pain_scene": "/assets/generated-cica-asset-sheet.png",
    "effect_comparison": "/assets/generated-cica-asset-sheet.png",
    "competitor_comparison": "/assets/generated-cica-asset-sheet.png",
    "ingredient_overview": "/assets/generated-cica-asset-sheet.png",
    "ingredient_1": "/assets/generated-cica-asset-sheet.png",
    "ingredient_2": "/assets/generated-cica-asset-sheet.png",
    "ingredient_3": "/assets/generated-cica-asset-sheet.png",
    "usage": "/assets/generated-cica-asset-sheet.png",
}
