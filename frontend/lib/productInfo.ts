import type { DetailLayoutId, ProductInfo } from "@/lib/types";

export const PRODUCT_INFO_FIELD_KEYS = [
  "product_name",
  "core_selling_points",
  "ingredients",
  "functions",
  "target_users",
  "material_highlights",
  "usage_method",
  "effect_claims",
  "authority_assets",
  "detail_layout_brief"
] as const;

export type ProductInfoBaseFieldKey = (typeof PRODUCT_INFO_FIELD_KEYS)[number];
export type ProductInfoFieldKey = ProductInfoBaseFieldKey | `detail_module:${string}`;

export type ProductInfoFieldConfig = {
  key: ProductInfoFieldKey;
  label: string;
  placeholder: string;
  moduleId?: string;
};

const STANDARD_DETAIL_FIELD_MODULES = [
  ["hero", "第 1 屏：详情首图", "产品大图 + 核心卖点"],
  ["brand_qualification", "第 2 屏：品牌与资质背书", "品牌背景、产地来源、渠道保障、资质认证"],
  ["research_strength", "第 3 屏：研发实力", "研发流程、真人测试、科学配方或检测依据"],
  ["pain_scene", "第 4 屏：痛点场景", "目标人群、皮肤问题、使用前困扰"],
  ["effect_comparison", "第 5 屏：效果对比", "使用前后、功效数据、趋势证明"],
  ["competitor_comparison", "第 6 屏：竞品对比", "普通同类产品不足、本品差异化优势"],
  ["product_showcase", "第 7 屏：产品大图强化", "产品大图、功效、质地、温和安全感"],
  ["ingredient_overview", "第 8 屏：成分总览", "整体成分体系、核心成分复配逻辑"],
  ["usage", "第 9 屏：使用方法", "3-4 步用法、用量、手法和频率"],
  ["product_info", "第 10 屏：产品信息", "产品参数、规格、成分说明、使用说明"]
] as const;

const EVIDENCE_CHAIN_DETAIL_FIELD_MODULES = [
  ["detail_ec_hero", "第 1 屏：首屏爆点", "产品大图、核心功效、可信卖点标签"],
  ["detail_ec_pain_matrix", "第 2 屏：痛点放大", "用户痛点、局部问题、代入感"],
  ["detail_ec_solution", "第 3 屏：产品解决方案", "产品方案、核心成分、质地展开"],
  ["detail_ec_competitor_comparison", "第 4 屏：差评与竞品对比", "普通同类产品不足、本品差异化方案"],
  ["detail_ec_real_trial", "第 5 屏：真人实测引入", "真人使用场景、测试周期、状态变化期待"],
  ["detail_ec_effect_validation", "第 6 屏：效果对比验证", "局部前后对比、数据或趋势证明"],
  ["detail_ec_research_system", "第 7 屏：研发体系背书", "研发流程、检测体系、配方可信度"],
  ["detail_ec_ingredient_1_mechanism", "第 8 屏：核心成分一机制", "第 1 核心成分与消费者可理解作用"],
  ["detail_ec_ingredient_1_proof", "第 9 屏：核心成分一证明", "成分配比、稳定性、肤感或测试依据"],
  ["detail_ec_ingredient_2_mechanism", "第 10 屏：核心成分二机制", "第 2 核心成分与辅助护理逻辑"],
  ["detail_ec_auxiliary_mechanism", "第 11 屏：辅助功效机制", "第二层购买理由，不固定功效"],
  ["detail_ec_auxiliary_validation", "第 12 屏：辅助功效验证", "辅助功效测试、对比或用户感受证明"],
  ["detail_ec_real_feedback", "第 13 屏：真人反馈合集", "真人反馈、局部对比、使用感合集"],
  ["detail_ec_texture", "第 14 屏：质地与肤感展示", "质地特写、延展、吸收、清爽度"],
  ["detail_ec_brand_sensory", "第 15 屏：品牌感与情绪价值", "品牌理念、香氛、原料来源或使用仪式感"],
  ["detail_ec_usage", "第 16 屏：使用方法", "3-4 步正确使用流程"]
] as const;

const BASE_PRODUCT_FIELD: ProductInfoFieldConfig = {
  key: "product_name",
  label: "产品名称",
  placeholder: "例如：修护精华 / 面霜 / 化妆水"
};

export function detailModuleFieldKey(moduleId: string): ProductInfoFieldKey {
  return `detail_module:${moduleId}` as ProductInfoFieldKey;
}

export function isDetailModuleFieldKey(key: ProductInfoFieldKey): key is `detail_module:${string}` {
  return String(key).startsWith("detail_module:");
}

function detailModuleIdFromFieldKey(key: ProductInfoFieldKey) {
  return isDetailModuleFieldKey(key) ? String(key).slice("detail_module:".length) : "";
}

function detailModuleFields(modules: readonly (readonly [string, string, string])[]): ProductInfoFieldConfig[] {
  return modules.map(([moduleId, label, placeholder]) => ({
    key: detailModuleFieldKey(moduleId),
    moduleId,
    label,
    placeholder
  }));
}

const STANDARD_PRODUCT_INFO_FIELDS: ProductInfoFieldConfig[] = [
  BASE_PRODUCT_FIELD,
  ...detailModuleFields(STANDARD_DETAIL_FIELD_MODULES)
];

const EVIDENCE_CHAIN_PRODUCT_INFO_FIELDS: ProductInfoFieldConfig[] = [
  BASE_PRODUCT_FIELD,
  ...detailModuleFields(EVIDENCE_CHAIN_DETAIL_FIELD_MODULES)
];

export function productInfoFieldsForDetailLayout(detailLayoutId: DetailLayoutId | string): ProductInfoFieldConfig[] {
  return detailLayoutId === "detail_evidence_chain_16" ? EVIDENCE_CHAIN_PRODUCT_INFO_FIELDS : STANDARD_PRODUCT_INFO_FIELDS;
}

const PLACEHOLDER_BENEFITS = [
  "待确认",
  "待说明",
  "待补充",
  "作用待确认",
  "功效待确认",
  "效果待确认",
  "未知",
  "未提供",
  "无",
  "n/a",
  "na"
];

const INGREDIENT_BENEFIT_RULES: Array<{ keywords: string[]; benefit: string }> = [
  { keywords: ["透明质酸", "玻尿酸", "hyaluronic"], benefit: "帮助提升水润肤感" },
  { keywords: ["烟酰胺", "niacinamide"], benefit: "帮助提亮肤色观感" },
  { keywords: ["积雪草", "cica", "centella"], benefit: "帮助舒缓干燥不适" },
  { keywords: ["神经酰胺", "ceramide", "泛醇", "panthenol"], benefit: "帮助维持肌肤屏障舒适" },
  { keywords: ["胶原", "肽", "胜肽", "pro-xylane", "玻色因"], benefit: "帮助支撑紧致弹润肤感" },
  { keywords: ["甘油", "角鲨烷", "squalane"], benefit: "帮助提升滋润肤感" }
];

function isPlaceholderBenefit(value: string) {
  const cleaned = value.trim().toLowerCase();
  return !cleaned || PLACEHOLDER_BENEFITS.some((placeholder) => cleaned.includes(placeholder));
}

function inferIngredientBenefit(name: string) {
  const normalizedName = name.toLowerCase();
  return (
    INGREDIENT_BENEFIT_RULES.find((rule) =>
      rule.keywords.some((keyword) => normalizedName.includes(keyword.toLowerCase()))
    )?.benefit ?? "辅助日常肌肤护理"
  );
}

function normalizeIngredientBenefit(name: string, benefit: string | undefined) {
  const cleaned = String(benefit ?? "").trim();
  return isPlaceholderBenefit(cleaned) ? inferIngredientBenefit(name) : cleaned;
}

function formatIngredientForDisplay(item: { name: string; benefit: string }) {
  const name = item.name.trim();
  if (!name) return "";
  return `${name}：${normalizeIngredientBenefit(name, item.benefit)}`;
}

function splitIngredientDraft(value: string) {
  return value
    .split(/[\/\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseIngredientDraftItem(value: string) {
  const cleaned = value.trim().replace(/^成分\s*[:：]\s*/, "");
  const actionMatch = cleaned.match(/^(.+?)\s*[;；]\s*(?:作用|功效|效果)\s*[:：]\s*(.+)$/);
  const basicMatch = cleaned.match(/^(.+?)\s*(?:[:：]|\s[-—–]\s)\s*(.+)$/);
  const match = actionMatch ?? basicMatch;
  const name = (match?.[1] ?? cleaned).trim();
  const rawBenefit = match?.[2]?.trim() ?? "";
  return { name, benefit: normalizeIngredientBenefit(name, rawBenefit) };
}

function formatDetailLayoutBrief(productInfo: ProductInfo) {
  const brief = productInfo.detail_layout_brief;
  if (!brief) return "";
  const lines: string[] = [];
  if (brief.selected_auxiliary_effect) lines.push(`辅助功效：${brief.selected_auxiliary_effect}`);
  if (brief.competitor_comparison) lines.push(`竞品对比：${brief.competitor_comparison}`);
  if (brief.manual_layout_notes?.length) lines.push(...brief.manual_layout_notes);
  if (brief.modules?.length) {
    lines.push(
      ...brief.modules
        .map((module) =>
          [
            module.module_name || module.module_id,
            module.page_task,
            module.headline_direction,
            ...(module.required_content ?? [])
          ]
            .filter(Boolean)
            .join("：")
        )
        .filter(Boolean)
    );
  }
  return lines.join(" / ");
}

function formatEffectClaims(productInfo: ProductInfo) {
  return productInfo.effect_claims.map((item) => `${item.claim} ${item.value}`.trim()).filter(Boolean).join(" / ");
}

function detailModuleBriefFor(productInfo: ProductInfo, moduleId: string) {
  return productInfo.detail_layout_brief?.modules?.find((module) => module.module_id === moduleId);
}

function formatDetailModuleBrief(productInfo: ProductInfo, moduleId: string) {
  const brief = detailModuleBriefFor(productInfo, moduleId);
  if (!brief) return "";
  return [
    brief.page_task,
    brief.headline_direction,
    brief.primary_visual,
    ...(brief.required_content ?? []),
    ...(brief.manual_notes ?? []),
    brief.data_source_note
  ]
    .filter(Boolean)
    .join(" / ");
}

function fallbackDetailModuleValue(productInfo: ProductInfo, moduleId: string) {
  const sellingPoints = productInfo.core_selling_points.join(" / ");
  const functions = productInfo.functions.join(" / ");
  const targetUsers = productInfo.target_users.join(" / ");
  const ingredients = productInfo.ingredients.map(formatIngredientForDisplay).filter(Boolean).join(" / ");
  const highlights = (productInfo.material_highlights ?? []).join(" / ");
  const authority = productInfo.authority_assets.join(" / ");
  const effects = formatEffectClaims(productInfo);
  const usage = productInfo.usage_method.join(" / ");
  const auxiliary = productInfo.detail_layout_brief?.selected_auxiliary_effect ?? "";
  const competitor = productInfo.detail_layout_brief?.competitor_comparison ?? "";

  const values: Record<string, string> = {
    hero: sellingPoints,
    brand_qualification: [highlights, authority].filter(Boolean).join(" / "),
    research_strength: authority,
    pain_scene: [targetUsers, functions].filter(Boolean).join(" / "),
    effect_comparison: effects,
    competitor_comparison: [competitor, sellingPoints].filter(Boolean).join(" / "),
    product_showcase: [sellingPoints, functions, highlights].filter(Boolean).join(" / "),
    ingredient_overview: ingredients,
    usage,
    product_info: [productInfo.product_name, productInfo.spec, usage].filter(Boolean).join(" / "),
    detail_ec_hero: sellingPoints,
    detail_ec_pain_matrix: [targetUsers, functions].filter(Boolean).join(" / "),
    detail_ec_solution: [sellingPoints, functions, ingredients].filter(Boolean).join(" / "),
    detail_ec_competitor_comparison: [competitor, sellingPoints].filter(Boolean).join(" / "),
    detail_ec_real_trial: [targetUsers, effects, highlights].filter(Boolean).join(" / "),
    detail_ec_effect_validation: effects,
    detail_ec_research_system: authority,
    detail_ec_ingredient_1_mechanism: productInfo.ingredients[0] ? formatIngredientForDisplay(productInfo.ingredients[0]) : ingredients,
    detail_ec_ingredient_1_proof: [productInfo.ingredients[0] ? formatIngredientForDisplay(productInfo.ingredients[0]) : "", highlights].filter(Boolean).join(" / "),
    detail_ec_ingredient_2_mechanism: productInfo.ingredients[1] ? formatIngredientForDisplay(productInfo.ingredients[1]) : ingredients,
    detail_ec_auxiliary_mechanism: [auxiliary, functions, highlights].filter(Boolean).join(" / "),
    detail_ec_auxiliary_validation: [auxiliary, effects, highlights].filter(Boolean).join(" / "),
    detail_ec_real_feedback: [effects, highlights].filter(Boolean).join(" / "),
    detail_ec_texture: highlights,
    detail_ec_brand_sensory: highlights,
    detail_ec_usage: usage
  };

  return values[moduleId] ?? "";
}

function productInfoValueForDetailModule(productInfo: ProductInfo, key: ProductInfoFieldKey) {
  const moduleId = detailModuleIdFromFieldKey(key);
  if (!moduleId) return "";
  return formatDetailModuleBrief(productInfo, moduleId) || fallbackDetailModuleValue(productInfo, moduleId);
}

export function createEmptyProductInfo(category = ""): ProductInfo {
  return {
    product_name: "",
    category,
    spec: "",
    core_selling_points: [],
    functions: [],
    ingredients: [],
    target_users: [],
    usage_method: [],
    authority_assets: [],
    effect_claims: [],
    material_highlights: [],
    confirmation_status: "pending"
  };
}

export function splitProductFieldDraft(value: string) {
  return value
    .split(/[\/、,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function productInfoValueFor(productInfo: ProductInfo, key: ProductInfoFieldKey) {
  if (isDetailModuleFieldKey(key)) return productInfoValueForDetailModule(productInfo, key);
  const value = productInfo[key];
  if (typeof value === "string") return value;
  if (key === "ingredients") return productInfo.ingredients.map(formatIngredientForDisplay).filter(Boolean).slice(0, 3).join(" / ");
  if (key === "effect_claims") return formatEffectClaims(productInfo);
  if (key === "material_highlights") return (productInfo.material_highlights ?? []).join(" / ");
  if (key === "detail_layout_brief") return formatDetailLayoutBrief(productInfo);
  return Array.isArray(value) ? value.join(" / ") : "";
}

export function productInfoHasValue(productInfo: ProductInfo, key: ProductInfoFieldKey) {
  if (isDetailModuleFieldKey(key)) return productInfoValueForDetailModule(productInfo, key).trim().length > 0;
  if (key === "product_name") return productInfo.product_name.trim().length > 0;
  if (key === "ingredients") return productInfo.ingredients.some((item) => item.name.trim().length > 0);
  if (key === "effect_claims") return productInfo.effect_claims.some((item) => item.claim.trim().length > 0);
  if (key === "material_highlights") return (productInfo.material_highlights ?? []).length > 0;
  if (key === "detail_layout_brief") return formatDetailLayoutBrief(productInfo).trim().length > 0;
  return productInfo[key].length > 0;
}

export function productInfoDraftHasValue(key: ProductInfoFieldKey, draft: string) {
  if (key === "product_name") return draft.trim().length > 0;
  return splitProductFieldDraft(draft).length > 0;
}

export function applyProductInfoDraft(productInfo: ProductInfo, key: ProductInfoFieldKey, draft: string): ProductInfo {
  const items = splitProductFieldDraft(draft);
  if (isDetailModuleFieldKey(key)) {
    const moduleId = detailModuleIdFromFieldKey(key);
    const modules = [...(productInfo.detail_layout_brief?.modules ?? [])];
    const moduleIndex = modules.findIndex((module) => module.module_id === moduleId);
    const nextModule = {
      ...(moduleIndex >= 0 ? modules[moduleIndex] : { module_id: moduleId }),
      module_id: moduleId,
      required_content: items,
      manual_notes: items
    };
    if (moduleIndex >= 0) {
      modules[moduleIndex] = nextModule;
    } else {
      modules.push(nextModule);
    }
    return {
      ...productInfo,
      detail_layout_brief: {
        ...(productInfo.detail_layout_brief ?? {}),
        modules
      },
      confirmation_status: "pending"
    };
  }
  if (key === "product_name") return { ...productInfo, product_name: draft.trim(), confirmation_status: "pending" };
  if (key === "ingredients") {
    return {
      ...productInfo,
      ingredients: splitIngredientDraft(draft).map(parseIngredientDraftItem).filter((item) => item.name).slice(0, 3),
      confirmation_status: "pending"
    };
  }
  if (key === "effect_claims") {
    return {
      ...productInfo,
      effect_claims: items.map((claim) => ({ claim, value: "", source_type: "ai_generated" })),
      confirmation_status: "pending"
    };
  }
  if (key === "detail_layout_brief") {
    return {
      ...productInfo,
      detail_layout_brief: {
        ...(productInfo.detail_layout_brief ?? {}),
        manual_layout_notes: items
      },
      confirmation_status: "pending"
    };
  }
  return { ...productInfo, [key]: items, confirmation_status: "pending" } as ProductInfo;
}

function detailModuleContentItems(productInfo: ProductInfo, key: ProductInfoFieldKey, placeholder: string) {
  const value = productInfoValueFor(productInfo, key).trim();
  const items = splitProductFieldDraft(value);
  return items.length ? items : [placeholder];
}

export function productInfoWithDetailLayoutFields(productInfo: ProductInfo, detailLayoutId: DetailLayoutId | string): ProductInfo {
  const existingModules = [...(productInfo.detail_layout_brief?.modules ?? [])];
  const modulesById = new Map(existingModules.map((module) => [module.module_id, module]));
  const detailFields = productInfoFieldsForDetailLayout(detailLayoutId).filter((field) => field.moduleId);

  const modules = detailFields.map((field) => {
    const moduleId = field.moduleId as string;
    const existing = modulesById.get(moduleId);
    const requiredContent = existing?.required_content?.length
      ? existing.required_content
      : detailModuleContentItems(productInfo, field.key, field.placeholder);
    return {
      ...(existing ?? {}),
      module_id: moduleId,
      module_name: existing?.module_name || field.label,
      page_task: existing?.page_task || field.placeholder,
      required_content: requiredContent,
      ...(existing?.manual_notes?.length ? { manual_notes: existing.manual_notes } : {})
    };
  });

  return {
    ...productInfo,
    detail_layout_brief: {
      ...(productInfo.detail_layout_brief ?? {}),
      layout_id: detailLayoutId,
      modules
    }
  };
}

export function mergeProductInfoWithManualPriority(
  current: ProductInfo,
  aiProductInfo: ProductInfo,
  manualFieldKeys: ProductInfoFieldKey[]
): ProductInfo {
  const manualKeys = new Set<ProductInfoFieldKey>(manualFieldKeys);
  const next = { ...current, ...aiProductInfo, confirmation_status: "pending" as const };

  for (const key of PRODUCT_INFO_FIELD_KEYS) {
    if (manualKeys.has(key) && productInfoHasValue(current, key)) {
      (next[key] as ProductInfo[ProductInfoBaseFieldKey]) = current[key] as ProductInfo[ProductInfoBaseFieldKey];
    }
  }

  const nextModules = [...(next.detail_layout_brief?.modules ?? [])];
  for (const key of manualKeys) {
    if (!isDetailModuleFieldKey(key) || !productInfoHasValue(current, key)) continue;
    const moduleId = detailModuleIdFromFieldKey(key);
    const currentModule = detailModuleBriefFor(current, moduleId);
    if (!currentModule) continue;
    const moduleIndex = nextModules.findIndex((module) => module.module_id === moduleId);
    if (moduleIndex >= 0) {
      nextModules[moduleIndex] = currentModule;
    } else {
      nextModules.push(currentModule);
    }
  }
  if (nextModules.length) {
    next.detail_layout_brief = { ...(next.detail_layout_brief ?? {}), modules: nextModules };
  }

  return next;
}
