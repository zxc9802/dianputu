import type { ModuleConfig, StyleOption } from "./types";

export const STYLE_OPTIONS: StyleOption[] = [
  {
    id: "green_repair",
    name: "绿色修护风",
    keywords: ["植物", "水滴", "温和", "屏障修护"],
    primary_color: "#1F8C43",
    asset: "/assets/style-green-repair.png"
  },
  {
    id: "blue_hydration",
    name: "蓝色补水风",
    keywords: ["清透", "水膜", "水润", "透明质酸"],
    primary_color: "#347FB9",
    asset: "/assets/style-blue-hydration.png"
  },
  {
    id: "gold_antiaging",
    name: "金色抗老风",
    keywords: ["胶原", "高级", "紧致", "金色光泽"],
    primary_color: "#B88727",
    asset: "/assets/style-gold-antiaging.png"
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
  { id: "ingredient", name: "成分页", description: "特殊成分 + 对应解决问题", enabled: true, order: 6, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "商品怎么用", enabled: true, order: 7, image_group: "detail" }
];

export const DEMO_MODEL_CONFIG = {
  textAnalysis: {
    model: "gemini-3.1-pro-preview",
    configured: false,
    defaults: { max_tokens: 4096, temperature: 0.2 }
  },
  imageGeneration: {
    model: "gpt-image-2",
    configured: false,
    defaults: { size: "1024x1024", n: 1, quality: "high", output_format: "png", response_format: "b64_json" },
    fallback: {
      model: "gpt-image-2-all",
      configured: false,
      defaults: { size: "1024x1024", n: 1 }
    }
  }
};
