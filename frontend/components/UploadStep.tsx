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
  Shield,
  ShieldCheck,
  Sparkles,
  Tags,
  Trash2
} from "lucide-react";
import { productInfoValueFor, type ProductInfoFieldKey } from "@/lib/productInfo";
import type { ProductInfo, UploadedFileInfo, UploadSlot } from "@/lib/types";

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

const manualRows = [
  { key: "product_name", label: "产品名称", icon: Tags, placeholder: "例如：修护精华 / 面霜 / 洁面乳" },
  { key: "core_selling_points", label: "核心卖点", icon: Sparkles, placeholder: "每行一个，或用 / 分隔" },
  { key: "ingredients", label: "核心成分", icon: Beaker, placeholder: "例如：主打成分 / 复配成分" },
  { key: "functions", label: "功效", icon: Shield, placeholder: "例如：主要功效 / 辅助功效" },
  { key: "usage_method", label: "使用方法", icon: Droplet, placeholder: "例如：洁面后使用 / 轻拍至吸收" },
  { key: "effect_claims", label: "效果数据", icon: LineChart, placeholder: "例如：保湿力提升 92%" },
  { key: "authority_assets", label: "权威资质", icon: Medal, placeholder: "例如：实验报告 / 专研配方理念" }
] as const satisfies Array<{ key: ProductInfoFieldKey; label: string; icon: typeof Tags; placeholder: string }>;

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
  moduleCount,
  manualFieldKeys,
  isAnalyzing,
  analysisSource,
  onFilesAdded,
  onFileRemove,
  onManualFieldChange,
  onAnalyze,
  onNext
}: {
  uploadedFiles: UploadedFileInfo[];
  productInfo: ProductInfo | null;
  productName: string;
  selectedStyleName: string;
  moduleCount: number;
  manualFieldKeys: ProductInfoFieldKey[];
  isAnalyzing: boolean;
  analysisSource: string;
  onFilesAdded: (slot: UploadSlot, files: File[]) => void;
  onFileRemove: (id: string) => void;
  onManualFieldChange: (key: ProductInfoFieldKey, draft: string) => void;
  onAnalyze: () => void;
  onNext: () => void;
}) {
  const [draggingSlot, setDraggingSlot] = useState<UploadSlot | null>(null);
  const hasFiles = uploadedFiles.length > 0;

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
          </div>

          <div className="analysisBar">
            <div>
              <Sparkles size={24} />
              <p>
                <b>AI 资料解析</b>
                <span>{analysisSource || "上传后点击解析，产品信息会更新到第 3 步确认页。"}</span>
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
                const Icon = row.icon;
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
          下一步：选择品类和风格
        </button>
      </footer>
    </>
  );
}
