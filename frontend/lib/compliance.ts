import type { ComplianceIssue, ComplianceReport, ComplianceStatus, ComplianceTextItem, ProductInfo } from "./types";

const statusRank: Record<ComplianceStatus, number> = { pass: 0, review: 1, warn: 2, block: 3 };

export function complianceStatusLabel(status: ComplianceStatus) {
  if (status === "block") return "高风险";
  if (status === "warn") return "有风险";
  if (status === "review") return "需确认";
  return "通过";
}

export function complianceStatusClass(status: ComplianceStatus) {
  return `compliance-${status}`;
}

export function highestComplianceStatus(reports: Array<ComplianceReport | null | undefined>): ComplianceStatus {
  return reports.reduce<ComplianceStatus>((highest, report) => {
    const status = report?.summary.status ?? "pass";
    return statusRank[status] > statusRank[highest] ? status : highest;
  }, "pass");
}

export function complianceIssueLocationLabel(issue: ComplianceIssue) {
  const imageIndex = issue.location?.image_index;
  if (typeof imageIndex === "number" && Number.isInteger(imageIndex) && imageIndex >= 0) {
    return `第 ${imageIndex + 1} 张`;
  }
  return "";
}

export function buildProductInfoComplianceItems(productInfo: ProductInfo | null): ComplianceTextItem[] {
  if (!productInfo) return [];
  const items: ComplianceTextItem[] = [];
  const push = (field: string, value: unknown) => {
    if (Array.isArray(value)) {
      value.forEach((entry, index) => push(`${field}.${index}`, entry));
      return;
    }
    if (value && typeof value === "object") {
      Object.entries(value as Record<string, unknown>).forEach(([key, entry]) => push(`${field}.${key}`, entry));
      return;
    }
    const text = String(value ?? "").trim();
    if (!text) return;
    items.push({ text, location: { source_type: "field", field } });
  };

  push("product_name", productInfo.product_name);
  push("core_selling_points", productInfo.core_selling_points);
  push("functions", productInfo.functions);
  push("ingredients", productInfo.ingredients);
  push("usage_method", productInfo.usage_method);
  push("authority_assets", productInfo.authority_assets);
  push("effect_claims", productInfo.effect_claims);
  push("material_highlights", productInfo.material_highlights ?? []);
  return items;
}
