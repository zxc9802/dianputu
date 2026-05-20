"use client";

import { ArrowDown, ArrowUp, Check, ImagePlus, Sparkles, Trash2, Wand2, X } from "lucide-react";
import { GLOBAL_STYLE_REFERENCE_SCOPE, hasScope, normalizeStyleReferenceScopes, type StyleReferenceScopeGroups } from "@/lib/styleReferenceTargeting";
import type { SavedStyleRecord, StyleOption, StyleReferenceScope, StyleSource, UploadedFileInfo } from "@/lib/types";

export function StyleStep({
  styles,
  styleSource,
  selectedStyleId,
  customStyle,
  styleReferenceFiles,
  styleReferenceScopeGroups,
  isPlanningCustomStyle,
  isAnalyzingStyleReference,
  isGeneratingStyleSample,
  savedStyles,
  isLoadingSavedStyles,
  isSavingStyle,
  deletingSavedStyleId,
  recommendedStyleId,
  onSelect,
  onAiCustomStyleSelect,
  onPlanAiCustomStyle,
  onSaveCustomStyle,
  onSelectSavedStyle,
  onDeleteSavedStyle,
  onStyleReferenceFilesAdded,
  onStyleReferenceFileRemove,
  onStyleReferenceFileMove,
  onStyleReferenceScopeToggle,
  onAnalyzeStyleReference,
  onGenerateAiStyleSample,
  onBack,
  onNext
}: {
  styles: StyleOption[];
  styleSource: StyleSource;
  selectedStyleId: string;
  customStyle: StyleOption | null;
  styleReferenceFiles: UploadedFileInfo[];
  styleReferenceScopeGroups: StyleReferenceScopeGroups;
  isPlanningCustomStyle: boolean;
  isAnalyzingStyleReference: boolean;
  isGeneratingStyleSample: boolean;
  savedStyles: SavedStyleRecord[];
  isLoadingSavedStyles: boolean;
  isSavingStyle: boolean;
  deletingSavedStyleId: string;
  recommendedStyleId: string;
  onSelect: (id: string) => void;
  onAiCustomStyleSelect: () => void;
  onPlanAiCustomStyle: () => void;
  onSaveCustomStyle: () => void;
  onSelectSavedStyle: (record: SavedStyleRecord) => void;
  onDeleteSavedStyle: (id: string) => void;
  onStyleReferenceFilesAdded: (files: File[]) => void;
  onStyleReferenceFileRemove: (id: string) => void;
  onStyleReferenceFileMove: (id: string, direction: -1 | 1) => void;
  onStyleReferenceScopeToggle: (id: string, scope: StyleReferenceScope) => void;
  onAnalyzeStyleReference: () => void;
  onGenerateAiStyleSample: () => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const scopeOptionGroups = [
    { id: "detail", title: "详情图", options: styleReferenceScopeGroups.detail },
    { id: "main", title: "店铺主图", options: styleReferenceScopeGroups.main },
    { id: "campaign", title: "活动主图", options: styleReferenceScopeGroups.campaign }
  ];

  function scopeSummary(file: UploadedFileInfo) {
    const scopes = normalizeStyleReferenceScopes(file.styleReferenceScopes);
    const moduleCount = scopes.filter((scope) => scope.type === "module").length;
    const globalCount = hasScope(file.styleReferenceScopes, GLOBAL_STYLE_REFERENCE_SCOPE) ? 1 : 0;
    if (globalCount && moduleCount) return `全局 + ${moduleCount} 屏`;
    if (globalCount) return "全局影响";
    return `${moduleCount} 屏`;
  }

  return (
    <>
      <section className="panel mainPanel fullPanel">
        <div className="sectionTitle">
          <span>3</span>
          <div>
            <h2>选择风格</h2>
            <p>品类由 AI 根据上传资料识别，可选择固定风格，也可以让 Gemini 3.1 Pro 根据产品规划独立视觉风格。</p>
          </div>
        </div>

        <h3 className="subheading">风格</h3>
        <div className="styleGrid">
          <article className={`styleCard aiCustomStyleCard ${styleSource === "ai_custom" ? "selected" : ""}`}>
            {styleSource === "ai_custom" ? (
              <span className="selectedMark">
                <Check size={24} />
              </span>
            ) : null}
            <h3 style={{ color: customStyle?.primary_color ?? "#1F8C43" }}>AI 自定义风格</h3>
            <p>{customStyle ? customStyle.name : "让 AI 根据产品定位、卖点和质感规划统一视觉元素，每张图可按模块变化颜色。"}</p>
            <div className="styleReferencePanel">
              <div className="styleReferenceHeader">
                <b>图片对标</b>
                <label className="smallButton" htmlFor="style-reference-upload">
                  <ImagePlus size={16} />
                  上传
                </label>
                <input
                  accept="image/*"
                  id="style-reference-upload"
                  multiple
                  type="file"
                  onChange={(event) => {
                    const files = Array.from(event.currentTarget.files ?? []);
                    if (files.length) onStyleReferenceFilesAdded(files);
                    event.currentTarget.value = "";
                  }}
                />
              </div>
              {styleReferenceFiles.length ? (
                <div className="styleReferenceThumbs">
                  {styleReferenceFiles.map((file, index) => (
                    <article className="styleReferenceItem" key={file.id}>
                      <figure>
                        {file.dataUrl ? <img src={file.dataUrl} alt={file.name} /> : <span>{file.name}</span>}
                      </figure>
                      <div className="styleReferenceMeta">
                        <div className="styleReferenceTitleRow">
                          <b>{index + 1}. {file.name}</b>
                          <div className="styleReferenceActions">
                            <button type="button" onClick={() => onStyleReferenceFileMove(file.id, -1)} disabled={index === 0} aria-label={`上移 ${file.name}`}>
                              <ArrowUp size={15} />
                            </button>
                            <button type="button" onClick={() => onStyleReferenceFileMove(file.id, 1)} disabled={index === styleReferenceFiles.length - 1} aria-label={`下移 ${file.name}`}>
                              <ArrowDown size={15} />
                            </button>
                            <button type="button" onClick={() => onStyleReferenceFileRemove(file.id)} aria-label={`移除 ${file.name}`}>
                              <X size={15} />
                            </button>
                          </div>
                        </div>
                        <details className="scopeDropdown">
                          <summary>{scopeSummary(file)}</summary>
                          <div className="scopeDropdownMenu">
                            <label className="scopeCheckbox">
                              <input
                                type="checkbox"
                                checked={hasScope(file.styleReferenceScopes, GLOBAL_STYLE_REFERENCE_SCOPE)}
                                onChange={() => onStyleReferenceScopeToggle(file.id, GLOBAL_STYLE_REFERENCE_SCOPE)}
                              />
                              全局影响
                            </label>
                            {scopeOptionGroups.map((group) => (
                              <div className="scopeGroup" key={group.id}>
                                <b>{group.title}</b>
                                {group.options.map((option) => {
                                  const scope: StyleReferenceScope = { type: "module", moduleId: option.moduleId };
                                  return (
                                    <label className="scopeCheckbox" key={option.moduleId}>
                                      <input
                                        type="checkbox"
                                        checked={hasScope(file.styleReferenceScopes, scope)}
                                        onChange={() => onStyleReferenceScopeToggle(file.id, scope)}
                                      />
                                      {option.label}
                                    </label>
                                  );
                                })}
                              </div>
                            ))}
                          </div>
                        </details>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="styleReferenceEmpty">上传竞品或目标视觉图，Gemini 会提取色彩、光影、构图、材质和字体层级。</p>
              )}
              <button className="outlineButton fullWidth" type="button" onClick={onAnalyzeStyleReference} disabled={isAnalyzingStyleReference || styleReferenceFiles.length === 0}>
                <Wand2 size={16} />
                {isAnalyzingStyleReference ? "对标分析中..." : customStyle?.id === "style_reference" ? "重新分析对标图" : "分析对标图风格"}
              </button>
            </div>
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
                <button className="outlineButton fullWidth" type="button" onClick={onSaveCustomStyle} disabled={isSavingStyle}>
                  {isSavingStyle ? "保存中..." : "保存到我的风格"}
                </button>
              </>
            ) : null}
            <button className="primaryButton fullWidth aiPlanButton" type="button" onClick={() => onPlanAiCustomStyle()} disabled={isPlanningCustomStyle}>
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
                {style.asset ? (
                  <img src={style.asset} alt={style.name} />
                ) : (
                  <div
                    className="styleThemePreview"
                    style={{
                      background: `radial-gradient(circle at 24% 22%, ${style.primary_color}66, transparent 34%), linear-gradient(135deg, ${style.primary_color}1f, #ffffff 48%, ${style.primary_color}33)`
                    }}
                  >
                    <span>{style.theme ?? style.name}</span>
                  </div>
                )}
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

        <div className="savedStyleLibrary">
          <div className="savedStyleHeader">
            <h3>我的保存风格</h3>
            <span>{isLoadingSavedStyles ? "读取中..." : `${savedStyles.length} 个`}</span>
          </div>
          {savedStyles.length ? (
            <div className="savedStyleGrid">
              {savedStyles.map((record) => (
                <article className="savedStyleCard" key={record.id}>
                  <h4 style={{ color: record.style.primary_color }}>{record.name}</h4>
                  <p>{record.style.keywords.slice(0, 4).join(" / ")}</p>
                  <div className="keywordRow">
                    {record.style.keywords.slice(0, 6).map((keyword) => (
                      <span key={keyword}>{keyword}</span>
                    ))}
                  </div>
                  <div className="savedStyleActions">
                    <button className="outlineButton" type="button" onClick={() => onSelectSavedStyle(record)}>
                      使用
                    </button>
                    <button
                      className="smallIconButton dangerIconButton"
                      type="button"
                      aria-label={`删除 ${record.name}`}
                      onClick={() => onDeleteSavedStyle(record.id)}
                      disabled={deletingSavedStyleId === record.id}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="savedStyleEmpty">暂无保存风格</p>
          )}
        </div>
      </section>

      <footer className="bottomActions">
        <button className="ghostButton" onClick={onBack}>
          上一步
        </button>
        <button className="primaryButton" onClick={onNext}>
          下一步：选择模块
        </button>
      </footer>
    </>
  );
}
