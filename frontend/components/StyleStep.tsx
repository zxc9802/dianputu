"use client";

import { useState } from "react";
import { Check, FileText, FileUp, FolderOpen, Sparkles, Trash2 } from "lucide-react";
import type { StyleOption, StyleSource, UploadedFileInfo, UploadSlot } from "@/lib/types";

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function StyleStep({
  styles,
  category,
  styleSource,
  selectedStyleId,
  customStyle,
  isPlanningCustomStyle,
  isGeneratingStyleSample,
  uploadedFiles,
  brandColors,
  recommendedStyleId,
  onSelect,
  onAiCustomStyleSelect,
  onPlanAiCustomStyle,
  onGenerateAiStyleSample,
  onStyleReferenceSelect,
  onCategoryChange,
  onStyleFilesAdded,
  onStyleFileRemove,
  onBack,
  onNext
}: {
  styles: StyleOption[];
  category: string;
  styleSource: StyleSource;
  selectedStyleId: string;
  customStyle: StyleOption | null;
  isPlanningCustomStyle: boolean;
  isGeneratingStyleSample: boolean;
  uploadedFiles: UploadedFileInfo[];
  brandColors: string[];
  recommendedStyleId: string;
  onSelect: (id: string) => void;
  onAiCustomStyleSelect: () => void;
  onPlanAiCustomStyle: () => void;
  onGenerateAiStyleSample: () => void;
  onStyleReferenceSelect: () => void;
  onCategoryChange: (category: string) => void;
  onStyleFilesAdded: (slot: UploadSlot, files: File[]) => void;
  onStyleFileRemove: (id: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const [isDragging, setIsDragging] = useState(false);
  const styleRefFiles = uploadedFiles.filter((f) => f.slot === "style_reference");
  const isReferenceSelected = styleSource === "reference";

  function handleFiles(files: FileList | File[]) {
    const nextFiles = Array.from(files);
    if (nextFiles.length > 0) onStyleFilesAdded("style_reference", nextFiles);
  }

  return (
    <>
      <section className="panel mainPanel fullPanel">
        <div className="sectionTitle">
          <span>2</span>
          <div>
            <h2>选择品类和风格</h2>
            <p>可选择固定风格，也可以让 Gemini 3.1 Pro 根据产品规划独立视觉风格。</p>
          </div>
        </div>

        <label className="fieldLabel" htmlFor="category">
          品类
        </label>
        <select id="category" className="select" value={category} onChange={(event) => onCategoryChange(event.target.value)}>
          <option>护肤精华</option>
          <option>面霜乳液</option>
          <option>清洁洗护</option>
        </select>

        <h3 className="subheading">风格</h3>
        {brandColors.length > 0 ? (
          <div className="brandColorPanel">
            <div>
              <b>提取到的产品主色</b>
              <span>产品主色会提供给 AI 自定义风格，也保留预设风格推荐作参考。</span>
            </div>
            <div className="colorSwatches">
              {brandColors.map((color) => (
                <span key={color}>
                  <i style={{ background: color }} />
                  {color}
                </span>
              ))}
            </div>
          </div>
        ) : null}
        <div className="styleGrid">
          <article className={`styleCard aiCustomStyleCard ${styleSource === "ai_custom" ? "selected" : ""}`}>
            {styleSource === "ai_custom" ? (
              <span className="selectedMark">
                <Check size={24} />
              </span>
            ) : null}
            <em className="recommendBadge">Gemini 3.1 Pro</em>
            <h3 style={{ color: customStyle?.primary_color ?? "#1F8C43" }}>AI 自定义风格</h3>
            <p>{customStyle ? customStyle.name : "让 AI 根据产品定位、卖点和包装色规划全新风格。"}</p>
            {customStyle?.asset ? (
              <img src={customStyle.asset} alt={`${customStyle.name} 样例图`} />
            ) : (
              <div className="aiStylePreview" style={{ background: customStyle?.primary_color ?? "#E6F4EA" }}>
                <Sparkles size={30} />
              </div>
            )}
            {customStyle ? (
              <>
                <div className="keywordRow">
                  {customStyle.keywords.map((keyword) => (
                    <span key={keyword}>{keyword}</span>
                  ))}
                </div>
                <p className="aiStyleBrief">{customStyle.visual_direction}</p>
                <button className="outlineButton fullWidth" onClick={onAiCustomStyleSelect}>
                  {styleSource === "ai_custom" ? "已选择" : "选择此风格"}
                </button>
                <button className="outlineButton fullWidth" type="button" onClick={onGenerateAiStyleSample} disabled={isGeneratingStyleSample}>
                  {isGeneratingStyleSample ? "样例图生成中..." : customStyle.asset ? "重新生成样例图" : "生成样例图"}
                </button>
              </>
            ) : null}
            <button className="primaryButton fullWidth" type="button" onClick={onPlanAiCustomStyle} disabled={isPlanningCustomStyle}>
              {isPlanningCustomStyle ? "AI 规划中..." : customStyle ? "重新规划风格" : "让 AI 规划风格"}
            </button>
          </article>
          {styles.map((style) => {
            const selected = styleSource === "preset" && style.id === selectedStyleId;
            const recommended = style.id === recommendedStyleId;
            return (
              <article className={`styleCard ${selected ? "selected" : ""}`} key={style.id}>
                {selected ? (
                  <span className="selectedMark">
                    <Check size={24} />
                  </span>
                ) : null}
                {recommended ? <em className="recommendBadge">AI 推荐</em> : null}
                <h3 style={{ color: style.primary_color }}>{style.name}</h3>
                <p>{style.keywords.slice(0, 3).join(" / ")}</p>
                <img src={style.asset} alt={style.name} />
                <div className="keywordRow">
                  {style.keywords.map((keyword) => (
                    <span key={keyword}>{keyword}</span>
                  ))}
                </div>
                <button className="outlineButton fullWidth" onClick={() => onSelect(style.id)}>
                  {selected ? "已选择" : "选择此风格"}
                </button>
              </article>
            );
          })}
        </div>

        <h3 className="subheading" style={{ marginTop: "2rem" }}>
          <Sparkles size={20} style={{ verticalAlign: "middle", marginRight: "0.4rem" }} />
          风格参考图（可选）
        </h3>
        <p className="styleRefHint">上传参考图后，AI 只参考排版、色调、光影和氛围，不改变产品外观、包装和品牌信息。</p>

        <article
          className={`uploadSlotCard styleRefCard ${isDragging ? "dragging" : ""} ${isReferenceSelected ? "selected" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            handleFiles(event.dataTransfer.files);
          }}
        >
          {isReferenceSelected ? (
            <span className="selectedMark">
              <Check size={24} />
            </span>
          ) : null}
          <div className="slotIcon">
            <Sparkles size={28} />
          </div>
          <h3>风格参考图</h3>
          <p>只参考排版、色调、光影和氛围，不改变产品外观、包装和品牌信息。</p>
          <input
            id="style-reference-upload"
            className="fileInput"
            type="file"
            multiple
            accept="image/*"
            onChange={(event) => {
              if (event.currentTarget.files) handleFiles(event.currentTarget.files);
              event.currentTarget.value = "";
            }}
          />
          <label className="outlineButton" htmlFor="style-reference-upload">
            <FolderOpen size={19} />
            选择文件
          </label>
          <button
            className="outlineButton"
            type="button"
            disabled={styleRefFiles.length === 0}
            onClick={onStyleReferenceSelect}
          >
            {isReferenceSelected ? "已选择" : "选择此风格"}
          </button>
          <span className="dropHint">
            <FileUp size={16} />
            {styleRefFiles.length > 0 ? "可作为独立风格来源" : "上传后可选择此风格"}
          </span>

          {styleRefFiles.length > 0 ? (
            <div className="slotFileList">
              {styleRefFiles.map((file) => (
                <div className="uploadedFileRow compact" key={file.id}>
                  <FileText size={18} />
                  <span>{file.name}</span>
                  <em>{formatFileSize(file.size)}</em>
                  <button aria-label={`移除 ${file.name}`} onClick={() => onStyleFileRemove(file.id)}>
                    <Trash2 size={17} />
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </article>
      </section>

      <footer className="bottomActions">
        <button className="ghostButton" onClick={onBack}>
          上一步
        </button>
        <button className="primaryButton" onClick={onNext}>
          下一步：确认信息
        </button>
      </footer>
    </>
  );
}
