import type { ProductInfo } from "@/lib/types";

export const PRODUCT_INFO_FIELD_KEYS = [
  "product_name",
  "core_selling_points",
  "ingredients",
  "functions",
  "usage_method",
  "effect_claims",
  "authority_assets"
] as const;

export type ProductInfoFieldKey = (typeof PRODUCT_INFO_FIELD_KEYS)[number];

export function createEmptyProductInfo(category = "护肤精华"): ProductInfo {
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
  if (key === "ingredients") return productInfo.ingredients.map((item) => item.name).join(" / ");
  if (key === "effect_claims") return productInfo.effect_claims.map((item) => `${item.claim} ${item.value}`.trim()).join(" / ");
  return Array.isArray(value) ? value.join(" / ") : "";
}

export function productInfoHasValue(productInfo: ProductInfo, key: ProductInfoFieldKey) {
  if (key === "product_name") return productInfo.product_name.trim().length > 0;
  if (key === "ingredients") return productInfo.ingredients.some((item) => item.name.trim().length > 0);
  if (key === "effect_claims") return productInfo.effect_claims.some((item) => item.claim.trim().length > 0);
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
      ingredients: items.map((name) => ({ name, benefit: "待确认" })),
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
