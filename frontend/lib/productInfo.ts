import type { ProductInfo } from "@/lib/types";

export const PRODUCT_INFO_FIELD_KEYS = [
  "product_name",
  "core_selling_points",
  "ingredients",
  "functions",
  "material_highlights",
  "usage_method",
  "effect_claims",
  "authority_assets"
] as const;

export type ProductInfoFieldKey = (typeof PRODUCT_INFO_FIELD_KEYS)[number];

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
  const value = productInfo[key];
  if (typeof value === "string") return value;
  if (key === "ingredients") return productInfo.ingredients.map(formatIngredientForDisplay).filter(Boolean).slice(0, 3).join(" / ");
  if (key === "effect_claims") return productInfo.effect_claims.map((item) => `${item.claim} ${item.value}`.trim()).join(" / ");
  if (key === "material_highlights") return (productInfo.material_highlights ?? []).join(" / ");
  return Array.isArray(value) ? value.join(" / ") : "";
}

export function productInfoHasValue(productInfo: ProductInfo, key: ProductInfoFieldKey) {
  if (key === "product_name") return productInfo.product_name.trim().length > 0;
  if (key === "ingredients") return productInfo.ingredients.some((item) => item.name.trim().length > 0);
  if (key === "effect_claims") return productInfo.effect_claims.some((item) => item.claim.trim().length > 0);
  if (key === "material_highlights") return (productInfo.material_highlights ?? []).length > 0;
  return productInfo[key].length > 0;
}

export function productInfoDraftHasValue(key: ProductInfoFieldKey, draft: string) {
  if (key === "product_name") return draft.trim().length > 0;
  return splitProductFieldDraft(draft).length > 0;
}

export function applyProductInfoDraft(productInfo: ProductInfo, key: ProductInfoFieldKey, draft: string): ProductInfo {
  const items = splitProductFieldDraft(draft);
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
  return { ...productInfo, [key]: items, confirmation_status: "pending" } as ProductInfo;
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
      (next[key] as ProductInfo[ProductInfoFieldKey]) = current[key] as ProductInfo[ProductInfoFieldKey];
    }
  }

  return next;
}
