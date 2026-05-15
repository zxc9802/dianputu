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


MAIN_MODULES = [
    {"id": "main_white_bg", "name": "白底图", "description": "纯白背景 + 产品居中", "enabled": True, "order": 1, "image_group": "main"},
    {"id": "main_hero_selling_point", "name": "首图", "description": "产品图 + 一句话核心卖点", "enabled": True, "order": 2, "image_group": "main"},
    {"id": "main_ingredient", "name": "次图-成分", "description": "核心成分 + 原料质感", "enabled": True, "order": 3, "image_group": "main"},
    {"id": "main_effect", "name": "次图-效果", "description": "核心功效 + 使用收益", "enabled": True, "order": 4, "image_group": "main"},
    {"id": "main_usage_scene", "name": "次图-使用场景", "description": "目标人群 + 生活场景", "enabled": True, "order": 5, "image_group": "main"},
]


CAMPAIGN_MODULES = [
    {"id": "campaign_white_bg", "name": "活动白底图", "description": "白底商品 + 促销角标", "enabled": True, "order": 1, "image_group": "campaign"},
    {"id": "campaign_hero_selling_point", "name": "活动首图", "description": "产品图 + 核心卖点 + 促销利益点", "enabled": True, "order": 2, "image_group": "campaign"},
    {"id": "campaign_ingredient", "name": "活动次图-成分", "description": "核心成分 + 活动氛围", "enabled": True, "order": 3, "image_group": "campaign"},
    {"id": "campaign_effect", "name": "活动次图-效果", "description": "核心功效 + 促销转化", "enabled": True, "order": 4, "image_group": "campaign"},
    {"id": "campaign_usage_scene", "name": "活动次图-使用场景", "description": "使用场景 + 活动元素", "enabled": True, "order": 5, "image_group": "campaign"},
]


STANDARD_DETAIL_MODULES = [
    {"id": "hero", "name": "详情首图", "description": "产品大图 + 核心卖点", "enabled": True, "order": 1, "image_group": "detail"},
    {"id": "brand_qualification", "name": "品牌与资质背书", "description": "品牌背景与权威认证", "enabled": True, "order": 2, "image_group": "detail"},
    {"id": "research_strength", "name": "研发实力", "description": "研发流程 / 真人测试 / 科学配方", "enabled": True, "order": 3, "image_group": "detail"},
    {"id": "pain_scene", "name": "痛点场景", "description": "皮肤问题 + 尝试无效", "enabled": True, "order": 4, "image_group": "detail"},
    {"id": "effect_comparison", "name": "效果对比", "description": "使用前后 + 百分比数据", "enabled": True, "order": 5, "image_group": "detail"},
    {"id": "competitor_comparison", "name": "竞品对比", "description": "质地 / 成分 / 效果 / 负面体验", "enabled": True, "order": 6, "image_group": "detail"},
    {"id": "product_showcase", "name": "产品大图强化", "description": "产品大图 + 功效 + 质地 + 0添加", "enabled": True, "order": 7, "image_group": "detail"},
    {"id": "ingredient_overview", "name": "成分总览", "description": "整体成分体系 + 配方逻辑", "enabled": True, "order": 8, "image_group": "detail"},
    {"id": "usage", "name": "使用方法", "description": "商品怎么用", "enabled": True, "order": 9, "image_group": "detail"},
    {"id": "product_info", "name": "产品信息", "description": "产品基础信息 / 参数 / 成分说明", "enabled": True, "order": 10, "image_group": "detail"},
]


EVIDENCE_CHAIN_DETAIL_MODULES = [
    {"id": "detail_ec_hero", "name": "首屏爆点", "description": "产品大图 + 核心功效 + 可信卖点标签", "enabled": True, "order": 1, "image_group": "detail"},
    {"id": "detail_ec_pain_matrix", "name": "痛点放大", "description": "用户痛点 / 局部问题 / 代入感", "enabled": True, "order": 2, "image_group": "detail"},
    {"id": "detail_ec_solution", "name": "产品解决方案", "description": "产品方案 + 核心成分 / 质地展开", "enabled": True, "order": 3, "image_group": "detail"},
    {"id": "detail_ec_competitor_comparison", "name": "差评与竞品对比", "description": "普通同类产品不足 + 本品差异化方案", "enabled": True, "order": 4, "image_group": "detail"},
    {"id": "detail_ec_real_trial", "name": "真人实测引入", "description": "真人使用场景 + 状态变化期待", "enabled": True, "order": 5, "image_group": "detail"},
    {"id": "detail_ec_effect_validation", "name": "效果对比验证", "description": "局部前后对比 + 数据 / 趋势证明", "enabled": True, "order": 6, "image_group": "detail"},
    {"id": "detail_ec_research_system", "name": "研发体系背书", "description": "研发流程 / 检测体系 / 配方可信度", "enabled": True, "order": 7, "image_group": "detail"},
    {"id": "detail_ec_ingredient_1_mechanism", "name": "核心成分一机制", "description": "第 1 核心成分 + 消费者可理解作用", "enabled": True, "order": 8, "image_group": "detail"},
    {"id": "detail_ec_ingredient_1_proof", "name": "核心成分一证明", "description": "成分配比 / 稳定性 / 肤感或测试依据", "enabled": True, "order": 9, "image_group": "detail"},
    {"id": "detail_ec_ingredient_2_mechanism", "name": "核心成分二机制", "description": "第 2 核心成分 + 辅助护理逻辑", "enabled": True, "order": 10, "image_group": "detail"},
    {"id": "detail_ec_auxiliary_mechanism", "name": "辅助功效机制", "description": "从资料中选择第二层购买理由，不固定功效", "enabled": True, "order": 11, "image_group": "detail"},
    {"id": "detail_ec_auxiliary_validation", "name": "辅助功效验证", "description": "辅助功效测试 / 对比 / 用户感受证明", "enabled": True, "order": 12, "image_group": "detail"},
    {"id": "detail_ec_real_feedback", "name": "真人反馈合集", "description": "真人反馈 / 局部对比 / 使用感合集", "enabled": True, "order": 13, "image_group": "detail"},
    {"id": "detail_ec_texture", "name": "质地与肤感展示", "description": "质地特写 + 延展 / 吸收 / 清爽度", "enabled": True, "order": 14, "image_group": "detail"},
    {"id": "detail_ec_brand_sensory", "name": "品牌感与情绪价值", "description": "品牌理念 / 香氛 / 原料来源 / 使用仪式感", "enabled": True, "order": 15, "image_group": "detail"},
    {"id": "detail_ec_usage", "name": "使用方法", "description": "3-4 步正确使用流程", "enabled": True, "order": 16, "image_group": "detail"},
]


DEFAULT_DETAIL_LAYOUT_ID = "detail_evidence_chain_16"


DETAIL_LAYOUTS = [
    {
        "id": "detail_evidence_chain_16",
        "name": "证据链长图结构",
        "description": "16 屏长图，先痛点和方案，再用成分、实验、真人反馈和使用方法完成说服。",
        "modules": EVIDENCE_CHAIN_DETAIL_MODULES,
    },
    {
        "id": "detail_standard_conversion_10",
        "name": "标准转化结构",
        "description": "当前 10 屏结构，适合更短的常规详情页。",
        "modules": STANDARD_DETAIL_MODULES,
    },
]


DEFAULT_MODULES = [
    *MAIN_MODULES,
    *CAMPAIGN_MODULES,
    *EVIDENCE_CHAIN_DETAIL_MODULES,
]


ALL_MODULES = [
    *MAIN_MODULES,
    *CAMPAIGN_MODULES,
    *EVIDENCE_CHAIN_DETAIL_MODULES,
    *STANDARD_DETAIL_MODULES,
]


STYLE_OPTIONS = [
    {
        "id": "space_repair",
        "name": "太空修护风",
        "theme": "太空风护肤视觉",
        "primary_color": "#4B6CFF",
        "asset": "/assets/style-space-repair.png",
        "keywords": ["深空", "星环", "修护科技", "冷光", "高级"],
        "best_for": ["修护精华", "屏障面霜", "抗老产品", "功效护肤"],
        "visual_elements": ["星球", "星环", "轨道线", "星云", "全息 UI", "金属舱体", "漂浮粒子"],
        "materials": ["深空渐变", "磨砂金属", "冷光玻璃", "透明亚克力", "星尘微粒"],
        "lighting": ["蓝紫冷光", "边缘轮廓光", "点状星光", "产品背后柔和光晕"],
        "module_usage": {
            "首图": "星球背景 + 轨道光环 + 金属陈列台，产品作为太空舱核心样本展示",
            "成分图": "漂浮样本舱 + 星尘微粒 + 透明玻璃卡片，成分像太空实验样本",
            "效果图": "全息数据环 + 冷光科技面板 + 轨道进度条，突出功效可信感",
            "使用场景": "舷窗光影 + 太空舱梳妆台 + 微重力漂浮道具",
            "活动图": "深空促销舞台 + 星环优惠标签 + 高级冷光氛围",
        },
        "forbidden": ["卡通宇航员", "飞船大战", "廉价科幻游戏 UI", "满屏星星", "产品被背景淹没"],
    },
    {
        "id": "deep_sea_hydration",
        "name": "深海补水风",
        "theme": "深海水润护肤视觉",
        "primary_color": "#21A7C7",
        "asset": "/assets/style-deep-sea-hydration.png",
        "keywords": ["深海", "水光", "气泡", "清透", "补水"],
        "best_for": ["补水精华", "保湿面膜", "清透乳液", "水润喷雾"],
        "visual_elements": ["海水波纹", "透明气泡", "水母光感", "蓝色水雾", "水滴微距"],
        "materials": ["清透凝胶", "玻璃水面", "湿润高光", "半透明亚克力"],
        "lighting": ["水下柔光", "焦散光纹", "蓝绿色高光"],
        "module_usage": {
            "首图": "清透水面 + 焦散光纹 + 透明亚克力陈列台，突出水润感",
            "成分图": "水滴微距 + 气泡包裹成分 + 玻璃卡片，表现补水成分清透质地",
            "效果图": "水波进度条 + 蓝绿色数据卡片 + 肌肤水光质感",
            "使用场景": "晨间浴室或梳妆台水雾光影，产品周围有清透气泡",
            "活动图": "深海水光背景 + 气泡优惠标签 + 清爽促销氛围",
        },
        "forbidden": ["卡通海洋生物", "脏乱水草", "廉价泳池感", "过暗深海"],
    },
    {
        "id": "lab_clinical_tech",
        "name": "实验室科技风",
        "theme": "功效实验室护肤视觉",
        "primary_color": "#D9F3FF",
        "asset": "/assets/style-lab-clinical-tech.png",
        "keywords": ["实验室", "功效", "数据", "配方", "精准"],
        "best_for": ["功效精华", "成分党产品", "数据型护肤", "敏感肌修护"],
        "visual_elements": ["玻璃烧杯", "培养皿", "显微纹理", "数据面板", "配方分子线"],
        "materials": ["透明玻璃", "银白金属", "冷白背景", "液体微距"],
        "lighting": ["干净冷白光", "实验台反射光", "局部蓝色科技光"],
        "module_usage": {
            "首图": "冷白实验室背景 + 透明玻璃陈列台 + 精准科技线条，突出功效可信感",
            "成分图": "培养皿和显微纹理 + 配方分子线 + 玻璃卡片，表现成分研究感",
            "效果图": "数据面板 + 进度环 + 冷白科技图表，突出可视化功效",
            "使用场景": "洁净实验室或研发台局部场景，避免医疗器械堆叠",
            "活动图": "实验室科技背景 + 轻量促销标签 + 可信功效氛围",
        },
        "forbidden": ["医院感", "医疗器械过重", "药品宣传", "真实机构背书"],
    },
    {
        "id": "oriental_herbal",
        "name": "东方草本风",
        "theme": "东方植萃护肤视觉",
        "primary_color": "#6E8F5A",
        "asset": "/assets/style-oriental-herbal.png",
        "keywords": ["草本", "东方", "温润", "植萃", "自然"],
        "best_for": ["植萃精华", "舒缓面霜", "敏感肌护理", "国货护肤"],
        "visual_elements": ["草本叶片", "竹影", "宣纸纹理", "陶瓷器皿", "晨露"],
        "materials": ["温润陶瓷", "细腻纸纹", "植物微距", "柔雾背景"],
        "lighting": ["晨间自然光", "柔和侧光", "低饱和暖光"],
        "module_usage": {
            "首图": "竹影柔光 + 陶瓷陈列台 + 少量草本叶片，突出温润植萃感",
            "成分图": "草本叶片微距 + 晨露 + 纸纹卡片，表现植物原料来源",
            "效果图": "低饱和草本数据卡 + 温润肌肤质感，避免强医疗数据感",
            "使用场景": "自然窗光梳妆台 + 陶瓷器皿 + 少量植物影子",
            "活动图": "东方礼赠背景 + 草本点缀 + 克制活动标签",
        },
        "forbidden": ["中药铺感", "过度复古", "厚重棕色", "杂乱植物堆"],
    },
    {
        "id": "glacier_cooling",
        "name": "冰川冷感风",
        "theme": "冰川清爽护肤视觉",
        "primary_color": "#A8E8F5",
        "asset": "/assets/style-glacier-cooling.png",
        "keywords": ["冰川", "冷感", "清爽", "控油", "舒缓"],
        "best_for": ["控油精华", "晒后舒缓", "清爽乳液", "啫喱面霜"],
        "visual_elements": ["冰晶", "冷雾", "透明冰块", "雪蓝渐变", "水珠凝结"],
        "materials": ["冰透玻璃", "凝露质地", "冷白亚克力", "细碎冰晶"],
        "lighting": ["冷白高光", "冰蓝轮廓光", "清透顶光"],
        "module_usage": {
            "首图": "冰透亚克力陈列台 + 冷雾 + 雪蓝渐变，突出清爽冷感",
            "成分图": "透明凝露和冰晶微距 + 冷白卡片，表现控油舒缓成分",
            "效果图": "冰蓝数据条 + 清爽肌肤质感 + 冷感图形符号",
            "使用场景": "夏日梳妆台冷光场景 + 水珠凝结，避免旅游雪景化",
            "活动图": "冰川清爽背景 + 冷蓝促销标签 + 轻量冰晶点缀",
        },
        "forbidden": ["过度寒冷刺痛感", "雪山旅游海报", "廉价冰块素材"],
    },
    {
        "id": "floral_fragrance",
        "name": "花园香氛风",
        "theme": "花园香氛护肤视觉",
        "primary_color": "#E9A6B8",
        "asset": "/assets/style-floral-fragrance.png",
        "keywords": ["花园", "柔肤", "香氛", "礼盒", "浪漫"],
        "best_for": ["身体乳", "香氛护肤", "柔肤乳液", "礼盒套装"],
        "visual_elements": ["花瓣", "柔雾", "丝带", "香氛光晕", "晨露花枝"],
        "materials": ["丝绸", "磨砂玻璃", "花瓣微距", "柔焦背景"],
        "lighting": ["柔粉自然光", "暖白边缘光", "轻微逆光"],
        "module_usage": {
            "首图": "柔焦花园背景 + 丝绸陈列台 + 少量花瓣，突出柔肤香氛感",
            "成分图": "花瓣微距 + 晨露 + 磨砂玻璃卡片，表现香氛和植萃来源",
            "效果图": "柔粉光晕数据卡 + 肌肤柔滑质感，避免硬科技面板",
            "使用场景": "自然光梳妆台或浴室局部 + 丝带花枝点缀",
            "活动图": "礼盒花园背景 + 丝带促销标签 + 柔和节日氛围",
        },
        "forbidden": ["婚庆廉价感", "花朵堆满画面", "过甜卡通风", "产品被花遮挡"],
    },
    {
        "id": "black_gold_luxury",
        "name": "黑金奢华风",
        "theme": "黑金高奢护肤视觉",
        "primary_color": "#C8A24A",
        "asset": "/assets/style-black-gold-luxury.png",
        "keywords": ["黑金", "高奢", "抗老", "鎏金", "精致"],
        "best_for": ["抗老面霜", "高端精华", "贵妇护肤", "礼盒套装", "紧致修护产品"],
        "visual_elements": ["黑色丝绒背景", "鎏金线条", "金属光环", "奢华陈列台", "金箔粒子", "高级礼盒", "珠宝级高光"],
        "materials": ["黑色丝绒", "拉丝金属", "亮面黑玻璃", "香槟金箔", "镜面亚克力"],
        "lighting": ["低调暗场光", "金色边缘光", "产品轮廓高光", "局部聚光", "细碎金色粒子光"],
        "module_usage": {
            "首图": "黑色高级背景 + 金色轮廓光 + 镜面陈列台，突出产品高端价格感",
            "成分图": "金箔粒子 + 黑金玻璃卡片 + 成分微距，表现珍贵配方感",
            "效果图": "金色数据环 + 黑色科技面板 + 精致进度条，突出抗老和紧致功效",
            "使用场景": "高端梳妆台 + 暗场柔光 + 金属细节道具，营造贵妇护肤场景",
            "活动图": "黑金礼盒舞台 + 鎏金促销标签 + 高级节日礼赠氛围",
        },
        "forbidden": ["土豪金大面积铺满", "廉价夜店风", "过暗看不清产品", "金色文字过多", "珠宝喧宾夺主"],
    },
]


DEMO_IMAGE_URLS = {module["id"]: "/assets/generated-cica-asset-sheet.png" for module in ALL_MODULES}
