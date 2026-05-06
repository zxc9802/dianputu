import { Check } from "lucide-react";
import type { StyleOption } from "@/lib/types";

export function StyleStep({
  styles,
  category,
  selectedStyleId,
  onSelect,
  onCategoryChange,
  onBack,
  onNext
}: {
  styles: StyleOption[];
  category: string;
  selectedStyleId: string;
  onSelect: (id: string) => void;
  onCategoryChange: (category: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <>
      <section className="panel mainPanel fullPanel">
        <div className="sectionTitle">
          <span>2</span>
          <div>
            <h2>选择品类和风格</h2>
            <p>第一版提供三套固定风格，避免生成结果视觉跑偏。</p>
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
        <div className="styleGrid">
          {styles.map((style) => {
            const selected = style.id === selectedStyleId;
            return (
              <article className={`styleCard ${selected ? "selected" : ""}`} key={style.id}>
                {selected ? (
                  <span className="selectedMark">
                    <Check size={24} />
                  </span>
                ) : null}
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
