"use client";

import { useMemo, useState } from "react";
import { Beaker, CheckCircle2, Droplet, LineChart, Medal, Pencil, Save, Shield, Sparkles, Tag } from "lucide-react";
import { complianceStatusClass, complianceStatusLabel } from "@/lib/compliance";
import { applyProductInfoDraft, productInfoValueFor, type ProductInfoFieldKey } from "@/lib/productInfo";
import type { ComplianceReport, ProductInfo } from "@/lib/types";

const rows = [
  { key: "product_name", label: "产品名称", icon: Tag },
  { key: "core_selling_points", label: "核心卖点", icon: Sparkles },
  { key: "ingredients", label: "核心成分", icon: Beaker },
  { key: "functions", label: "功效", icon: Shield },
  { key: "material_highlights", label: "资料亮点摘要", icon: Sparkles },
  { key: "usage_method", label: "使用方法", icon: Droplet },
  { key: "effect_claims", label: "效果数据", icon: LineChart },
  { key: "authority_assets", label: "权威资质", icon: Medal }
] as const satisfies Array<{ key: ProductInfoFieldKey; label: string; icon: typeof Tag }>;

export function ReviewStep({
  productInfo,
  complianceReport,
  onUpdateProductInfo,
  onBack,
  onNext
}: {
  productInfo: ProductInfo | null;
  complianceReport?: ComplianceReport | null;
  onUpdateProductInfo: (productInfo: ProductInfo) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const [editingKey, setEditingKey] = useState<ProductInfoFieldKey | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmedFields, setConfirmedFields] = useState<Set<ProductInfoFieldKey>>(() => new Set());
  const allConfirmed = confirmedFields.size === rows.length;

  const confirmedProductInfo = useMemo(
    () => (productInfo ? ({ ...productInfo, confirmation_status: allConfirmed ? "confirmed" : "pending" } as ProductInfo) : null),
    [allConfirmed, productInfo]
  );

  function beginEdit(key: ProductInfoFieldKey) {
    if (!productInfo) return;
    setEditingKey(key);
    setDraft(productInfoValueFor(productInfo, key));
  }

  function saveEdit(key: ProductInfoFieldKey) {
    if (!productInfo) return;
    const next = applyProductInfoDraft(productInfo, key, draft);
    onUpdateProductInfo(next);
    setEditingKey(null);
    setDraft("");
  }

  function confirmField(key: ProductInfoFieldKey) {
    setConfirmedFields((current) => new Set(current).add(key));
  }

  function confirmAllAndContinue() {
    if (!confirmedProductInfo) return;
    const all = new Set(rows.map((row) => row.key));
    setConfirmedFields(all);
    onUpdateProductInfo({ ...confirmedProductInfo, confirmation_status: "confirmed" });
    onNext();
  }

  return (
    <>
      <section className="panel mainPanel fullPanel">
        <div className="sectionTitle">
          <span>3</span>
          <div>
            <h2>确认 AI 提炼结果</h2>
            <p>生成前需要确认关键字段，必要时可逐项修改。</p>
          </div>
        </div>

        {productInfo ? (
          <>
            <div className="fieldList">
              {rows.map((row) => {
                const Icon = row.icon;
                const isEditing = editingKey === row.key;
                const isConfirmed = confirmedFields.has(row.key);
                return (
                  <div className={`infoRow ${isEditing ? "editing" : ""}`} key={row.key}>
                    <Icon size={25} />
                    <strong>{row.label}</strong>
                    {isEditing ? (
                      <textarea value={draft} onChange={(event) => setDraft(event.target.value)} aria-label={`编辑${row.label}`} />
                    ) : (
                      <p>{productInfoValueFor(productInfo, row.key)}</p>
                    )}
                    {isEditing ? (
                      <button className="smallButton" onClick={() => saveEdit(row.key)}>
                        <Save size={18} />
                        保存
                      </button>
                    ) : (
                      <button className="smallButton" onClick={() => beginEdit(row.key)}>
                        <Pencil size={18} />
                        修改
                      </button>
                    )}
                    <button className={`smallButton ${isConfirmed ? "confirmed" : ""}`} onClick={() => confirmField(row.key)}>
                      <CheckCircle2 size={18} />
                      {isConfirmed ? "已确认" : "确认"}
                    </button>
                  </div>
                );
              })}
            </div>
            {complianceReport ? (
              <aside className={`compliancePanel ${complianceStatusClass(complianceReport.summary.status)}`}>
                <header>
                  <b>合规风险</b>
                  <span>{complianceStatusLabel(complianceReport.summary.status)}</span>
                </header>
                {complianceReport.issues.length ? (
                  <ul className="complianceIssueList">
                    {complianceReport.issues.slice(0, 5).map((issue, index) => (
                      <li key={`${issue.term}-${index}`}>
                        <strong>{issue.term}</strong>
                        <span>{issue.reason}</span>
                        <em>{issue.suggestion}</em>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>当前提炼文案未发现明显违规词。</p>
                )}
              </aside>
            ) : null}
          </>
        ) : (
          <div className="emptyState">
            <Sparkles size={34} />
            <h3>暂无 AI 提炼结果</h3>
            <p>请先在上传资料页上传产品图、检测报告或说明书，并点击 AI 解析。只有模型真实返回的商品信息才会显示在这里。</p>
          </div>
        )}
      </section>

      <footer className="bottomActions">
        <button className="ghostButton" onClick={onBack}>
          上一步
        </button>
        <button className="primaryButton" onClick={confirmAllAndContinue} disabled={!productInfo}>
          {allConfirmed ? "进入模块选择" : "全部确认，进入模块选择"}
        </button>
      </footer>
    </>
  );
}
