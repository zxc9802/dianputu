"use client";

import { useState } from "react";
import {
  Beaker,
  CheckCircle2,
  ClipboardCheck,
  Droplet,
  FileText,
  FileUp,
  FolderOpen,
  Grid2X2,
  ImageIcon,
  LineChart,
  Medal,
  Package,
  Palette,
  Shield,
  ShieldCheck,
  Sparkles,
  Tags,
  Trash2
} from "lucide-react";
import { productInfoFieldsForDetailLayout, productInfoValueFor, type ProductInfoFieldKey } from "@/lib/productInfo";
import type { DetailLayoutConfig, DetailLayoutId, ProductColorReference, ProductInfo, UploadedFileInfo, UploadSlot } from "@/lib/types";

const uploadSlots: Array<{
  id: string;
  slot: UploadSlot;
  title: string;
  description: string;
  accept: string;
  multiple: boolean;
  icon: typeof ImageIcon;
}> = [
  {
    id: "product-image-upload",
    slot: "product_image",
    title: "产品主图",
    description: "用于识别瓶身、包装、色系，并作为生图参考图。",
    accept: "image/*",
    multiple: true,
    icon: ImageIcon
  },

  {
    id: "report-file-upload",
    slot: "reports",
    title: "检测报告 / 资质",
    description: "用于提取实验室、报告、功效数据和权威背书。",
    accept: "image/*,.pdf,.txt,.csv",
    multiple: true,
    icon: ClipboardCheck
  },
  {
    id: "document-file-upload",
    slot: "documents",
    title: "成分表 / 说明书",
    description: "用于提取成分、使用方法、适用人群和卖点。",
    accept: "image/*,.txt,.csv,.doc,.docx,.xls,.xlsx,.pdf",
    multiple: true,
    icon: FileText
  }
];

const fieldIcons: Record<string, typeof Tags> = {
  product_name: Tags,
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

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function filesForSlot(uploadedFiles: UploadedFileInfo[], slot: UploadSlot) {
  return uploadedFiles.filter((file) => file.slot === slot);
}

export function UploadStep({
  uploadedFiles,
  productInfo,
  productName,
  selectedStyleName,
  detailLayouts,
  selectedDetailLayoutId,
  moduleCount,
  manualFieldKeys,
  isAnalyzing,
  analysisSource,
  productColor,
  onFilesAdded,
  onFileRemove,
  onDetailLayoutChange,
  onProductColorChange,
  onManualFieldChange,
  onAnalyze,
  onNext
}: {
  uploadedFiles: UploadedFileInfo[];
  productInfo: ProductInfo | null;
  productName: string;
  selectedStyleName: string;
  detailLayouts: DetailLayoutConfig[];
  selectedDetailLayoutId: DetailLayoutId;
  moduleCount: number;
  manualFieldKeys: ProductInfoFieldKey[];
  isAnalyzing: boolean;
  analysisSource: string;
  productColor: ProductColorReference | null;
  onFilesAdded: (slot: UploadSlot, files: File[]) => void;
  onFileRemove: (id: string) => void;
  onDetailLayoutChange: (id: DetailLayoutId) => void;
  onProductColorChange: (reference: ProductColorReference | null) => void;
  onManualFieldChange: (key: ProductInfoFieldKey, draft: string) => void;
  onAnalyze: () => void;
  onNext: () => void;
}) {
  const [draggingSlot, setDraggingSlot] = useState<UploadSlot | null>(null);
  const hasFiles = uploadedFiles.length > 0;
  const manualRows = productInfoFieldsForDetailLayout(selectedDetailLayoutId);
  const productColorLabel = productColor
    ? [productColor.name, productColor.hex].filter(Boolean).join(" · ")
    : "AI 自动识别";

  function handleFiles(slot: UploadSlot, files: FileList | File[]) {
    const nextFiles = Array.from(files);
    if (nextFiles.length > 0) onFilesAdded(slot, nextFiles);
  }

  return (
    <>
      <div className="workspace">
        <section className="panel mainPanel">
          <div className="sectionTitle">
            <span>1</span>
            <div>
              <h2>上传产品资料</h2>
              <p>先把产品图、报告和资料分开上传，AI 会按类型解析并用于后续生图。</p>
            </div>
          </div>

          <div className="detailLayoutPanel">
            <div>
              <h3>详情图排版结构</h3>
              <p>AI 会按选中的结构拆解资料，并用于后续详情图生成。</p>
            </div>
            <div className="detailLayoutOptions">
              {detailLayouts.map((layout) => (
                <button
                  className={selectedDetailLayoutId === layout.id ? "detailLayoutOption active" : "detailLayoutOption"}
                  key={layout.id}
                  onClick={() => onDetailLayoutChange(layout.id)}
                  type="button"
                >
                  <b>{layout.name}</b>
                  <span>{layout.modules.length} 屏 · {layout.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="uploadSlotGrid">
            {uploadSlots.map((slotConfig) => {
              const Icon = slotConfig.icon;
              const slotFiles = filesForSlot(uploadedFiles, slotConfig.slot);
              const isDragging = draggingSlot === slotConfig.slot;
              return (
                <article
                  className={`uploadSlotCard ${isDragging ? "dragging" : ""}`}
                  key={slotConfig.slot}
                  onDragOver={(event) => {
                    event.preventDefault();
                    setDraggingSlot(slotConfig.slot);
                  }}
                  onDragLeave={() => setDraggingSlot(null)}
                  onDrop={(event) => {
                    event.preventDefault();
                    setDraggingSlot(null);
                    handleFiles(slotConfig.slot, event.dataTransfer.files);
                  }}
                >
                  <div className="slotIcon">
                    <Icon size={28} />
                  </div>
                  <h3>{slotConfig.title}</h3>
                  <p>{slotConfig.description}</p>
                  <input
                    id={slotConfig.id}
                    className="fileInput"
                    type="file"
                    multiple={slotConfig.multiple}
                    accept={slotConfig.accept}
                    onChange={(event) => {
                      if (event.currentTarget.files) handleFiles(slotConfig.slot, event.currentTarget.files);
                      event.currentTarget.value = "";
                    }}
                  />
                  <label className="outlineButton" htmlFor={slotConfig.id}>
                    <FolderOpen size={19} />
                    选择文件
                  </label>
                  <span className="dropHint">
                    <FileUp size={16} />
                    也可拖拽到这里
                  </span>

                  {slotFiles.length > 0 ? (
                    <div className="slotFileList">
                      {slotFiles.map((file) => (
                        <div className="uploadedFileRow compact" key={file.id}>
                          <FileText size={18} />
                          <span>{file.name}</span>
                          <em>{formatFileSize(file.size)}</em>
                          <button aria-label={`移除 ${file.name}`} onClick={() => onFileRemove(file.id)}>
                            <Trash2 size={17} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </article>
              );
            })}

            <article className={`uploadSlotCard productColorCard ${productColor ? "selected" : ""}`}>
              <div className="productColorHeading">
                <div className="slotIcon">
                  <Palette size={28} />
                </div>
                {productColor ? (
                  <span className="priorityBadge">
                    <CheckCircle2 size={14} />
                    用户选择优先
                  </span>
                ) : null}
              </div>
              <h3>产品颜色</h3>
              <p>选择商品本体或包装主色；若与主图、报告或说明书冲突，以此处选择为准。</p>

              <div className="productColorFields">
                <label className="productColorPickerLabel">
                  <input
                    aria-label="选择任意产品颜色"
                    type="color"
                    value={productColor?.hex || "#F5F1E8"}
                    onChange={(event) => {
                      const hex = event.target.value.toUpperCase();
                      onProductColorChange({ name: productColor?.name ?? "", hex });
                    }}
                  />
                  <span
                    className="selectedColorSwatch"
                    style={{ backgroundColor: productColor?.hex || "#F5F1E8" }}
                  />
                  任意取色
                </label>
                <input
                  aria-label="产品颜色描述"
                  className="productColorNameInput"
                  placeholder="颜色描述，如：半透明淡蓝"
                  value={productColor?.name ?? ""}
                  onChange={(event) =>
                    onProductColorChange({
                      name: event.target.value,
                      hex: productColor?.hex ?? ""
                    })
                  }
                />
              </div>

              <div className="productColorFooter">
                <span>{productColorLabel}</span>
                {productColor ? (
                  <button onClick={() => onProductColorChange(null)} type="button">
                    清除选择
                  </button>
                ) : (
                  <em>未选择时由 AI 识别</em>
                )}
              </div>
            </article>
          </div>

          <div className="analysisBar">
            <div>
              <Sparkles size={24} />
              <p>
                <b>AI 资料解析</b>
                <span>{analysisSource || "上传后点击解析，产品信息会更新到第 2 步确认页。"}</span>
              </p>
            </div>
            <button className="primaryButton" onClick={onAnalyze} disabled={!hasFiles || isAnalyzing}>
              {isAnalyzing ? "AI 解析中..." : "AI 解析已上传资料"}
            </button>
          </div>
        </section>

        <aside className="panel sidePanel">
          <div className="sectionTitle compact">
            <span>
              <Package size={20} />
            </span>
            <div>
              <h2>当前项目</h2>
            </div>
          </div>
          <div className="summaryList">
            <div>
              <Tags size={26} />
              <p>
                <b>商品：</b>{productName}
              </p>
            </div>
            <div>
              <Grid2X2 size={26} />
              <p>
                <b>上传：</b>{uploadedFiles.length} 个文件
              </p>
            </div>
            <div>
              <ShieldCheck size={26} />
              <p>
                <b>风格：</b>{selectedStyleName}
              </p>
            </div>
            <div>
              <Palette size={26} />
              <p>
                <b>颜色：</b>{productColorLabel}
              </p>
            </div>
            <div>
              <Package size={26} />
              <p>
                <b>生成项：</b>{moduleCount} 个
              </p>
            </div>
          </div>

          <div className="manualSupplement">
            <header>
              <h3>手动补充信息（可不填）</h3>
              <p>手填内容优先，AI 解析时只补没有手填的字段。</p>
            </header>
            <div className="manualFieldStack">
              {manualRows.map((row) => {
                const Icon = iconForField(row.key);
                const isManual = manualFieldKeys.includes(row.key);
                const value = productInfo ? productInfoValueFor(productInfo, row.key) : "";
                return (
                  <label className={`manualField ${isManual ? "manual" : ""}`} key={row.key}>
                    <span>
                      <Icon size={17} />
                      <b>{row.label}</b>
                      {isManual ? (
                        <em>
                          <CheckCircle2 size={14} />
                          手填优先
                        </em>
                      ) : null}
                    </span>
                    {row.key === "product_name" ? (
                      <input
                        value={value}
                        placeholder={row.placeholder}
                        onChange={(event) => onManualFieldChange(row.key, event.target.value)}
                      />
                    ) : (
                      <textarea
                        value={value}
                        placeholder={row.placeholder}
                        rows={2}
                        onChange={(event) => onManualFieldChange(row.key, event.target.value)}
                      />
                    )}
                  </label>
                );
              })}
            </div>
          </div>
        </aside>
      </div>

      <footer className="bottomActions">
        <button className="ghostButton" onClick={onAnalyze} disabled={!hasFiles || isAnalyzing}>
          {isAnalyzing ? "解析中..." : "先用 AI 解析资料"}
        </button>
        <button className="primaryButton" onClick={onNext}>
          下一步：确认信息
        </button>
      </footer>
    </>
  );
}
