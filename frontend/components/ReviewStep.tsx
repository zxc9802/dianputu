"use client";

import { useEffect, useMemo, useState } from "react";
import { Beaker, CheckCircle2, Droplet, Grid2X2, LineChart, Medal, Package, Pencil, Save, Shield, Sparkles, Tag } from "lucide-react";
import { complianceStatusClass, complianceStatusLabel } from "@/lib/compliance";
import { applyProductInfoDraft, productInfoFieldsForDetailLayout, productInfoValueFor, productInfoWithDetailLayoutFields, type ProductInfoFieldKey } from "@/lib/productInfo";
import type { ComplianceReport, DetailLayoutId, ProductInfo } from "@/lib/types";

const fieldIcons: Record<string, typeof Tag> = {
  product_name: Tag,
  core_selling_points: Sparkles,
  ingredients: Beaker,
  functions: Shield,
  target_users: Package,
  material_highlights: Sparkles,
  usage_method: Droplet,
  effect_claims: LineChart,
  authority_assets: Medal,
  detail_layout_brief: Grid2X2
};

function iconForField(key: ProductInfoFieldKey) {
  return key.startsWith("detail_module:") ? Grid2X2 : fieldIcons[key];
}

export function ReviewStep({
  productInfo,
  selectedDetailLayoutId,
  complianceReport,
  onUpdateProductInfo,
  onBack,
  onNext
}: {
  productInfo: ProductInfo | null;
  selectedDetailLayoutId: DetailLayoutId;
  complianceReport?: ComplianceReport | null;
  onUpdateProductInfo: (productInfo: ProductInfo) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const rows = productInfoFieldsForDetailLayout(selectedDetailLayoutId);
  const [editingKey, setEditingKey] = useState<ProductInfoFieldKey | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmedFields, setConfirmedFields] = useState<Set<ProductInfoFieldKey>>(() => new Set());
  const allConfirmed = rows.every((row) => confirmedFields.has(row.key));

  const confirmedProductInfo = useMemo(
    () => (productInfo ? ({ ...productInfo, confirmation_status: allConfirmed ? "confirmed" : "pending" } as ProductInfo) : null),
    [allConfirmed, productInfo]
  );

  useEffect(() => {
    const visibleKeys = new Set(rows.map((row) => row.key));
    setConfirmedFields((current) => new Set([...current].filter((key) => visibleKeys.has(key))));
    if (editingKey && !visibleKeys.has(editingKey)) {
      setEditingKey(null);
      setDraft("");
    }
  }, [editingKey, rows]);

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
    const expandedProductInfo = productInfoWithDetailLayoutFields(confirmedProductInfo, selectedDetailLayoutId);
    setConfirmedFields(all);
    onUpdateProductInfo({ ...expandedProductInfo, confirmation_status: "confirmed" });
    onNext();
  }

  return (
    <>
      <section className="panel mainPanel fullPanel">
        <div className="sectionTitle">
          <span>2</span>
          <div>
            <h2>确认 AI 提炼结果</h2>
            <p>生成前需要确认关键字段，必要时可逐项修改。</p>
          </div>
        </div>

        {productInfo ? (
          <>
            <div className="fieldList">
              {rows.map((row) => {
                const Icon = iconForField(row.key);
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
