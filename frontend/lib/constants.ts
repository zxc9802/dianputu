import type { CommercePlatform, ModuleConfig, ProjectTemplate, StyleOption } from "./types";

export const STYLE_OPTIONS: StyleOption[] = [
  {
    id: "space_repair",
    name: "太空修护风",
    theme: "太空风护肤视觉",
    primary_color: "#4B6CFF",
    asset: "/assets/style-space-repair.png",
    keywords: ["深空", "星环", "修护科技", "冷光", "高级"],
    best_for: ["修护精华", "屏障面霜", "抗老产品", "功效护肤"],
    visual_elements: ["星球", "星环", "轨道线", "星云", "全息 UI", "金属舱体", "漂浮粒子"],
    materials: ["深空渐变", "磨砂金属", "冷光玻璃", "透明亚克力", "星尘微粒"],
    lighting: ["蓝紫冷光", "边缘轮廓光", "点状星光", "产品背后柔和光晕"],
    module_usage: {
      首图: "星球背景 + 轨道光环 + 金属陈列台，产品作为太空舱核心样本展示",
      成分图: "漂浮样本舱 + 星尘微粒 + 透明玻璃卡片，成分像太空实验样本",
      效果图: "全息数据环 + 冷光科技面板 + 轨道进度条，突出功效可信感",
      使用场景: "舷窗光影 + 太空舱梳妆台 + 微重力漂浮道具",
      活动图: "深空促销舞台 + 星环优惠标签 + 高级冷光氛围"
    },
    forbidden: ["卡通宇航员", "飞船大战", "廉价科幻游戏 UI", "满屏星星", "产品被背景淹没"]
  },
  {
    id: "deep_sea_hydration",
    name: "深海补水风",
    theme: "深海水润护肤视觉",
    primary_color: "#21A7C7",
    asset: "/assets/style-deep-sea-hydration.png",
    keywords: ["深海", "水光", "气泡", "清透", "补水"],
    best_for: ["补水精华", "保湿面膜", "清透乳液", "水润喷雾"],
    visual_elements: ["海水波纹", "透明气泡", "水母光感", "蓝色水雾", "水滴微距"],
    materials: ["清透凝胶", "玻璃水面", "湿润高光", "半透明亚克力"],
    lighting: ["水下柔光", "焦散光纹", "蓝绿色高光"],
    module_usage: {
      首图: "清透水面 + 焦散光纹 + 透明亚克力陈列台，突出水润感",
      成分图: "水滴微距 + 气泡包裹成分 + 玻璃卡片，表现补水成分清透质地",
      效果图: "水波进度条 + 蓝绿色数据卡片 + 肌肤水光质感",
      使用场景: "晨间浴室或梳妆台水雾光影，产品周围有清透气泡",
      活动图: "深海水光背景 + 气泡优惠标签 + 清爽促销氛围"
    },
    forbidden: ["卡通海洋生物", "脏乱水草", "廉价泳池感", "过暗深海"]
  },
  {
    id: "lab_clinical_tech",
    name: "实验室科技风",
    theme: "功效实验室护肤视觉",
    primary_color: "#D9F3FF",
    asset: "/assets/style-lab-clinical-tech.png",
    keywords: ["实验室", "功效", "数据", "配方", "精准"],
    best_for: ["功效精华", "成分党产品", "数据型护肤", "敏感肌修护"],
    visual_elements: ["玻璃烧杯", "培养皿", "显微纹理", "数据面板", "配方分子线"],
    materials: ["透明玻璃", "银白金属", "冷白背景", "液体微距"],
    lighting: ["干净冷白光", "实验台反射光", "局部蓝色科技光"],
    module_usage: {
      首图: "冷白实验室背景 + 透明玻璃陈列台 + 精准科技线条，突出功效可信感",
      成分图: "培养皿和显微纹理 + 配方分子线 + 玻璃卡片，表现成分研究感",
      效果图: "数据面板 + 进度环 + 冷白科技图表，突出可视化功效",
      使用场景: "洁净实验室或研发台局部场景，避免医疗器械堆叠",
      活动图: "实验室科技背景 + 轻量促销标签 + 可信功效氛围"
    },
    forbidden: ["医院感", "医疗器械过重", "药品宣传", "真实机构背书"]
  },
  {
    id: "oriental_herbal",
    name: "东方草本风",
    theme: "东方植萃护肤视觉",
    primary_color: "#6E8F5A",
    asset: "/assets/style-oriental-herbal.png",
    keywords: ["草本", "东方", "温润", "植萃", "自然"],
    best_for: ["植萃精华", "舒缓面霜", "敏感肌护理", "国货护肤"],
    visual_elements: ["草本叶片", "竹影", "宣纸纹理", "陶瓷器皿", "晨露"],
    materials: ["温润陶瓷", "细腻纸纹", "植物微距", "柔雾背景"],
    lighting: ["晨间自然光", "柔和侧光", "低饱和暖光"],
    module_usage: {
      首图: "竹影柔光 + 陶瓷陈列台 + 少量草本叶片，突出温润植萃感",
      成分图: "草本叶片微距 + 晨露 + 纸纹卡片，表现植物原料来源",
      效果图: "低饱和草本数据卡 + 温润肌肤质感，避免强医疗数据感",
      使用场景: "自然窗光梳妆台 + 陶瓷器皿 + 少量植物影子",
      活动图: "东方礼赠背景 + 草本点缀 + 克制活动标签"
    },
    forbidden: ["中药铺感", "过度复古", "厚重棕色", "杂乱植物堆"]
  },
  {
    id: "glacier_cooling",
    name: "冰川冷感风",
    theme: "冰川清爽护肤视觉",
    primary_color: "#A8E8F5",
    asset: "/assets/style-glacier-cooling.png",
    keywords: ["冰川", "冷感", "清爽", "控油", "舒缓"],
    best_for: ["控油精华", "晒后舒缓", "清爽乳液", "啫喱面霜"],
    visual_elements: ["冰晶", "冷雾", "透明冰块", "雪蓝渐变", "水珠凝结"],
    materials: ["冰透玻璃", "凝露质地", "冷白亚克力", "细碎冰晶"],
    lighting: ["冷白高光", "冰蓝轮廓光", "清透顶光"],
    module_usage: {
      首图: "冰透亚克力陈列台 + 冷雾 + 雪蓝渐变，突出清爽冷感",
      成分图: "透明凝露和冰晶微距 + 冷白卡片，表现控油舒缓成分",
      效果图: "冰蓝数据条 + 清爽肌肤质感 + 冷感图形符号",
      使用场景: "夏日梳妆台冷光场景 + 水珠凝结，避免旅游雪景化",
      活动图: "冰川清爽背景 + 冷蓝促销标签 + 轻量冰晶点缀"
    },
    forbidden: ["过度寒冷刺痛感", "雪山旅游海报", "廉价冰块素材"]
  },
  {
    id: "floral_fragrance",
    name: "花园香氛风",
    theme: "花园香氛护肤视觉",
    primary_color: "#E9A6B8",
    asset: "/assets/style-floral-fragrance.png",
    keywords: ["花园", "柔肤", "香氛", "礼盒", "浪漫"],
    best_for: ["身体乳", "香氛护肤", "柔肤乳液", "礼盒套装"],
    visual_elements: ["花瓣", "柔雾", "丝带", "香氛光晕", "晨露花枝"],
    materials: ["丝绸", "磨砂玻璃", "花瓣微距", "柔焦背景"],
    lighting: ["柔粉自然光", "暖白边缘光", "轻微逆光"],
    module_usage: {
      首图: "柔焦花园背景 + 丝绸陈列台 + 少量花瓣，突出柔肤香氛感",
      成分图: "花瓣微距 + 晨露 + 磨砂玻璃卡片，表现香氛和植萃来源",
      效果图: "柔粉光晕数据卡 + 肌肤柔滑质感，避免硬科技面板",
      使用场景: "自然光梳妆台或浴室局部 + 丝带花枝点缀",
      活动图: "礼盒花园背景 + 丝带促销标签 + 柔和节日氛围"
    },
    forbidden: ["婚庆廉价感", "花朵堆满画面", "过甜卡通风", "产品被花遮挡"]
  },
  {
    id: "black_gold_luxury",
    name: "黑金奢华风",
    theme: "黑金高奢护肤视觉",
    primary_color: "#C8A24A",
    asset: "/assets/style-black-gold-luxury.png",
    keywords: ["黑金", "高奢", "抗老", "鎏金", "精致"],
    best_for: ["抗老面霜", "高端精华", "贵妇护肤", "礼盒套装", "紧致修护产品"],
    visual_elements: ["黑色丝绒背景", "鎏金线条", "金属光环", "奢华陈列台", "金箔粒子", "高级礼盒", "珠宝级高光"],
    materials: ["黑色丝绒", "拉丝金属", "亮面黑玻璃", "香槟金箔", "镜面亚克力"],
    lighting: ["低调暗场光", "金色边缘光", "产品轮廓高光", "局部聚光", "细碎金色粒子光"],
    module_usage: {
      首图: "黑色高级背景 + 金色轮廓光 + 镜面陈列台，突出产品高端价格感",
      成分图: "金箔粒子 + 黑金玻璃卡片 + 成分微距，表现珍贵配方感",
      效果图: "金色数据环 + 黑色科技面板 + 精致进度条，突出抗老和紧致功效",
      使用场景: "高端梳妆台 + 暗场柔光 + 金属细节道具，营造贵妇护肤场景",
      活动图: "黑金礼盒舞台 + 鎏金促销标签 + 高级节日礼赠氛围"
    },
    forbidden: ["土豪金大面积铺满", "廉价夜店风", "过暗看不清产品", "金色文字过多", "珠宝喧宾夺主"]
  }
];

export const DEFAULT_MODULES: ModuleConfig[] = [
  { id: "main_white_bg", name: "白底图", description: "纯白背景 + 产品居中", enabled: true, order: 1, image_group: "main" },
  { id: "main_hero_selling_point", name: "首图", description: "产品图 + 一句话核心卖点", enabled: true, order: 2, image_group: "main" },
  { id: "main_ingredient", name: "次图-成分", description: "核心成分 + 原料质感", enabled: true, order: 3, image_group: "main" },
  { id: "main_effect", name: "次图-效果", description: "核心功效 + 使用收益", enabled: true, order: 4, image_group: "main" },
  { id: "main_usage_scene", name: "次图-使用场景", description: "目标人群 + 生活场景", enabled: true, order: 5, image_group: "main" },
  { id: "campaign_white_bg", name: "活动白底图", description: "白底商品 + 促销角标", enabled: true, order: 1, image_group: "campaign" },
  { id: "campaign_hero_selling_point", name: "活动首图", description: "产品图 + 核心卖点 + 促销利益点", enabled: true, order: 2, image_group: "campaign" },
  { id: "campaign_ingredient", name: "活动次图-成分", description: "核心成分 + 活动氛围", enabled: true, order: 3, image_group: "campaign" },
  { id: "campaign_effect", name: "活动次图-效果", description: "核心功效 + 促销转化", enabled: true, order: 4, image_group: "campaign" },
  { id: "campaign_usage_scene", name: "活动次图-使用场景", description: "使用场景 + 活动元素", enabled: true, order: 5, image_group: "campaign" },
  { id: "hero", name: "详情首图", description: "产品大图 + 核心卖点", enabled: true, order: 1, image_group: "detail" },
  { id: "authority", name: "权威资质展示", description: "实验室 / 科学家 / 报告 / 专利", enabled: true, order: 2, image_group: "detail" },
  { id: "pain_scene", name: "痛点场景", description: "皮肤问题 + 尝试无效", enabled: true, order: 3, image_group: "detail" },
  { id: "effect_comparison", name: "效果对比", description: "使用前后 + 百分比数据", enabled: true, order: 4, image_group: "detail" },
  { id: "competitor_comparison", name: "竞品对比", description: "质地 / 成分 / 效果 / 负面体验", enabled: true, order: 5, image_group: "detail" },
  { id: "ingredient_overview", name: "成分总览", description: "整体成分体系 + 配方逻辑", enabled: true, order: 6, image_group: "detail" },
  { id: "ingredient_1", name: "成分 1 讲解", description: "第 1 个核心成分作用讲解", enabled: true, order: 7, image_group: "detail" },
  { id: "ingredient_2", name: "成分 2 讲解", description: "第 2 个核心成分作用讲解", enabled: true, order: 8, image_group: "detail" },
  { id: "ingredient_3", name: "成分 3 讲解", description: "第 3 个核心成分作用讲解", enabled: true, order: 9, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "商品怎么用", enabled: true, order: 10, image_group: "detail" }
];

export const COMMERCE_PLATFORMS: CommercePlatform[] = [
  { id: "tmall", name: "淘宝 / 天猫", mainSize: "800x800", generationSize: "2048x2048", detailWidth: 1500, note: "按 2K 生成，发布前可压缩到平台规格" },
  { id: "jd", name: "京东", mainSize: "800x800", generationSize: "2048x2048", detailWidth: 1500, note: "按 2K 生成，发布前可压缩到平台规格" },
  { id: "douyin", name: "抖音电商", mainSize: "600x600", generationSize: "2048x2048", detailWidth: 1500, note: "按 2K 生成，发布前可压缩到平台规格" },
  { id: "pdd", name: "拼多多", mainSize: "750x750", generationSize: "2048x2048", detailWidth: 1500, note: "按 2K 生成，发布前可压缩到平台规格" },
  { id: "xiaohongshu_square", name: "小红书 1:1", mainSize: "1080x1080", generationSize: "2048x2048", detailWidth: 2048, note: "按 2K 方图生成，适合高清种草图" },
  { id: "xiaohongshu_portrait", name: "小红书 3:4", mainSize: "1080x1440", generationSize: "1536x2048", detailWidth: 1536, note: "按 2K 竖图生成，适合高清种草封面" }
];

export const OFFICIAL_PROJECT_TEMPLATES: ProjectTemplate[] = [
  {
    id: "official-serum-green",
    name: "精华类模板",
    category: "护肤精华",
    styleId: "space_repair",
    platformId: "tmall",
    source: "official",
    modules: [
      { id: "main_white_bg", enabled: true, order: 1 },
      { id: "main_hero_selling_point", enabled: true, order: 2 },
      { id: "main_ingredient", enabled: true, order: 3 },
      { id: "main_effect", enabled: true, order: 4 },
      { id: "main_usage_scene", enabled: true, order: 5 },
      { id: "hero", enabled: true, order: 1 },
      { id: "authority", enabled: true, order: 2 },
      { id: "effect_comparison", enabled: true, order: 3 },
      { id: "ingredient_overview", enabled: true, order: 4 },
      { id: "ingredient_1", enabled: true, order: 5 },
      { id: "ingredient_2", enabled: true, order: 6 },
      { id: "ingredient_3", enabled: true, order: 7 },
      { id: "usage", enabled: true, order: 8 }
    ]
  },
  {
    id: "official-cream-gold",
    name: "面霜类模板",
    category: "面霜乳液",
    styleId: "black_gold_luxury",
    platformId: "jd",
    source: "official",
    modules: [
      { id: "main_white_bg", enabled: true, order: 1 },
      { id: "main_hero_selling_point", enabled: true, order: 2 },
      { id: "main_effect", enabled: true, order: 3 },
      { id: "campaign_white_bg", enabled: true, order: 1 },
      { id: "campaign_hero_selling_point", enabled: true, order: 2 },
      { id: "hero", enabled: true, order: 1 },
      { id: "pain_scene", enabled: true, order: 2 },
      { id: "effect_comparison", enabled: true, order: 3 },
      { id: "competitor_comparison", enabled: true, order: 4 },
      { id: "ingredient_overview", enabled: true, order: 5 },
      { id: "ingredient_1", enabled: true, order: 6 },
      { id: "ingredient_2", enabled: true, order: 7 },
      { id: "ingredient_3", enabled: true, order: 8 },
      { id: "usage", enabled: true, order: 9 }
    ]
  },
  {
    id: "official-clean-blue",
    name: "清洁洗护模板",
    category: "清洁洗护",
    styleId: "deep_sea_hydration",
    platformId: "douyin",
    source: "official",
    modules: [
      { id: "main_white_bg", enabled: true, order: 1 },
      { id: "main_hero_selling_point", enabled: true, order: 2 },
      { id: "main_usage_scene", enabled: true, order: 3 },
      { id: "hero", enabled: true, order: 1 },
      { id: "pain_scene", enabled: true, order: 2 },
      { id: "ingredient_overview", enabled: true, order: 3 },
      { id: "ingredient_1", enabled: true, order: 4 },
      { id: "ingredient_2", enabled: true, order: 5 },
      { id: "ingredient_3", enabled: true, order: 6 },
      { id: "usage", enabled: true, order: 7 }
    ]
  }
];

export const DEMO_MODEL_CONFIG = {
  textAnalysis: {
    model: "gemini-3.1-pro-preview",
    configured: false,
    defaults: { max_tokens: 4096, temperature: 0.7 }
  },
  imageGeneration: {
    model: "gpt-image-2-all",
    configured: false,
    defaultOptionId: "fallback",
    options: [
      {
        id: "primary",
        label: "gpt image2(1)",
        model: "gpt-image-2-vip",
        configured: false,
        defaults: { size: "2048x2048", n: 0, quality: "", output_format: "png", response_format: "url" }
      },
      {
        id: "fallback",
        label: "gpt image2(2)",
        model: "gpt-image-2-all",
        configured: false,
        defaults: { size: "2048x2048", n: 1, quality: "", output_format: "", response_format: "" }
      },
      {
        id: "gemini_flash_image",
        label: "Gemini 3.1 Flash Image Preview",
        model: "gemini-3.1-flash-image-preview",
        configured: false,
        defaults: { size: "2048x2048", n: 1, response_format: "b64_json" }
      }
    ],
    defaults: { size: "2048x2048", n: 1, quality: "", output_format: "", response_format: "" },
    fallback: {
      label: "gpt image2(2)",
      model: "gpt-image-2-all",
      configured: false,
      defaults: { size: "2048x2048", n: 1 }
    }
  }
};
