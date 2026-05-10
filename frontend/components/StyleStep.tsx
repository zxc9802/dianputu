"use client";

import { Check, Sparkles } from "lucide-react";
import type { StyleOption, StyleSource } from "@/lib/types";

export function StyleStep({
  styles,
  styleSource,
  selectedStyleId,
  customStyle,
  isPlanningCustomStyle,
  isGeneratingStyleSample,
  recommendedStyleId,
  onSelect,
  onAiCustomStyleSelect,
  onPlanAiCustomStyle,
  onGenerateAiStyleSample,
  onBack,
  onNext
}: {
  styles: StyleOption[];
  styleSource: StyleSource;
  selectedStyleId: string;
  customStyle: StyleOption | null;
  isPlanningCustomStyle: boolean;
  isGeneratingStyleSample: boolean;
  recommendedStyleId: string;
  onSelect: (id: string) => void;
  onAiCustomStyleSelect: () => void;
  onPlanAiCustomStyle: () => void;
  onGenerateAiStyleSample: () => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <>
      <section className="panel mainPanel fullPanel">
        <div className="sectionTitle">
          <span>2</span>
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
