import { Check, ImageIcon, Lock, WandSparkles } from "lucide-react";
import { complianceStatusClass, complianceStatusLabel } from "@/lib/compliance";
import type { CommercePlatform, CommercePlatformId, ComplianceReport, GenerationMode, ImageGroup, ModuleConfig, ProjectTemplate, PublicModelConfig, StyleOption, StyleSource } from "@/lib/types";

const imageGroups: ImageGroup[] = ["main", "campaign", "detail"];

const groupCopy: Record<ImageGroup, { title: string; description: string; output: string; moduleLabel: string; buttonLabel: string }> = {
  main: {
    title: "主图生成",
    description: "生成 5 张电商主图：白底图、首图、成分、效果、使用场景。",
    output: "5 张独立主图",
    moduleLabel: "主图",
    buttonLabel: "主图"
  },
  campaign: {
    title: "活动主图生成",
    description: "主图结构上加入促销角标、优惠券、限时活动等营销元素。",
    output: "5 张活动主图",
    moduleLabel: "活动主图",
    buttonLabel: "活动主图"
  },
  detail: {
    title: "详情图生成",
    description: "按详情页结构生成模块分图，可删减后合成完整长图。",
    output: "分图 + 完整长图",
    moduleLabel: "详情图模块",
    buttonLabel: "详情图"
  }
};

type GeneratedImage = { module_id: string; url: string };
type GenerationProgress = { isGenerating: boolean; completed: number; total: number; runningModuleIds: string[]; errorCount: number };
type GenerationProgressMap = Record<ImageGroup, GenerationProgress>;

function moduleGroup(module: ModuleConfig): ImageGroup {
  return module.image_group ?? "detail";
}

function groupModules(modules: ModuleConfig[], group: ImageGroup) {
  return modules.filter((module) => moduleGroup(module) === group).sort((a, b) => a.order - b.order);
}

export function ModulesStep({
  modules,
  activeImageGroup,
  selectedStyle,
  styleSource,
  modelConfig,
  generatedImages,
  generationProgress,
  promotionInfo,
  platforms,
  selectedPlatformId,
  templates,
  selectedImageModelId,
  generationMode,
  promotionCompliance,
  onPromotionInfoChange,
  onPlatformChange,
  onImageModelChange,
  onGenerationModeChange,
  onTemplateApply,
  onTemplateSave,
  onImageGroupChange,
  onToggleModule,
  onBack,
  onGenerate
}: {
  modules: ModuleConfig[];
  activeImageGroup: ImageGroup;
  selectedStyle: StyleOption;
  styleSource: StyleSource;
  modelConfig: PublicModelConfig;
  generatedImages: GeneratedImage[];
  generationProgress: GenerationProgressMap;
  promotionInfo: string;
  platforms: CommercePlatform[];
  selectedPlatformId: CommercePlatformId;
  templates: ProjectTemplate[];
  selectedImageModelId: string;
  generationMode: GenerationMode;
  promotionCompliance?: ComplianceReport | null;
  onPromotionInfoChange: (value: string) => void;
  onPlatformChange: (id: CommercePlatformId) => void;
  onImageModelChange: (id: string) => void;
  onGenerationModeChange: (mode: GenerationMode) => void;
  onTemplateApply: (template: ProjectTemplate) => void;
  onTemplateSave: () => void;
  onImageGroupChange: (group: ImageGroup) => void;
  onToggleModule: (id: string) => void;
  onBack: () => void;
  onGenerate: (moduleId?: string) => void;
}) {
  const generatedIds = new Set(generatedImages.map((image) => image.module_id));
  const currentModules = groupModules(modules, activeImageGroup);
  const enabledCount = currentModules.filter((module) => module.enabled).length;
  const generatedCount = currentModules.filter((module) => generatedIds.has(module.id)).length;
  const activeProgress = generationProgress[activeImageGroup];
  const copy = groupCopy[activeImageGroup];
  const selectedPlatform = platforms.find((platform) => platform.id === selectedPlatformId) ?? platforms[0];
  const imageModelOptions = modelConfig.imageGeneration.options?.length
    ? modelConfig.imageGeneration.options
    : [
        {
          id: modelConfig.imageGeneration.defaultOptionId ?? "primary",
          label: modelConfig.imageGeneration.model,
          model: modelConfig.imageGeneration.model,
          configured: modelConfig.imageGeneration.configured,
          defaults: modelConfig.imageGeneration.defaults
        }
      ];
  const selectedImageModel = imageModelOptions.find((option) => option.id === selectedImageModelId) ?? imageModelOptions[0];

  return (
    <>
      <div className="workspace">
        <section className="panel mainPanel">
          <div className="sectionTitle">
            <span>4</span>
            <div>
              <h2>选择生成版块</h2>
              <p>主图、活动主图和详情图可同时生成，切换版块即可查看各自进度。</p>
            </div>
          </div>

          <div className="groupTabs" role="tablist" aria-label="生成版块">
            {imageGroups.map((group) => {
              const groupProgress = generationProgress[group];
              const modulesInGroup = groupModules(modules, group);
              const groupGeneratedCount = modulesInGroup.filter((module) => generatedIds.has(module.id)).length;
              return (
                <button
                  key={group}
                  className={activeImageGroup === group ? "groupTab active" : "groupTab"}
                  onClick={() => onImageGroupChange(group)}
                  type="button"
                >
                  <b>{groupCopy[group].title}</b>
                  <span>{groupCopy[group].description}</span>
                  <em>
                    {groupProgress.isGenerating
                      ? `并行生成中 ${groupProgress.completed}/${groupProgress.total}`
                      : `已生成 ${groupGeneratedCount}/${modulesInGroup.length}`}
                  </em>
                </button>
              );
            })}
          </div>

          <div className="platformPanel">
            <label>
              <span>目标平台</span>
              <select value={selectedPlatformId} onChange={(event) => onPlatformChange(event.target.value as CommercePlatformId)}>
                {platforms.map((platform) => (
                  <option key={platform.id} value={platform.id}>
                    {platform.name} · 生成 {platform.generationSize}
                  </option>
                ))}
              </select>
            </label>
            <p>
              生成尺寸 {selectedPlatform.generationSize}，详情图宽 {selectedPlatform.detailWidth}px。发布参考：主图 {selectedPlatform.mainSize}。
              {selectedPlatform.note}
            </p>
          </div>

          <div className="templateStrip">
            <div>
              <b>项目模板</b>
              <span>套用模块、风格、品类和平台配置。</span>
            </div>
            <div className="templateActions">
              {templates.map((template) => (
                <button className="inlineActionButton" key={template.id} onClick={() => onTemplateApply(template)} type="button">
                  {template.name}
                </button>
              ))}
              <button className="inlineActionButton strong" onClick={onTemplateSave} type="button">
                保存当前为模板
              </button>
            </div>
          </div>

          {activeImageGroup === "campaign" ? (
            <>
              <label className="promotionField">
                <span>促销方式（生图时会参考）</span>
                <textarea
                  value={promotionInfo}
                  placeholder="例如：618 限时 8 折 / 买一送一 / 满 199 减 30 / 第二件半价"
                  rows={3}
                  onChange={(event) => onPromotionInfoChange(event.target.value)}
                />
                <em>不填写也可以生成，但模型只能使用泛化活动氛围，不会编造具体折扣或价格。</em>
              </label>
              {promotionCompliance ? (
                <div className={`compliancePanel compact ${complianceStatusClass(promotionCompliance.summary.status)}`}>
                  <header>
                    <b>促销合规预检</b>
                    <span>{complianceStatusLabel(promotionCompliance.summary.status)}</span>
                  </header>
                  {promotionCompliance.issues.length ? (
                    <ul className="complianceIssueList">
                      {promotionCompliance.issues.slice(0, 3).map((issue, index) => (
                        <li key={`${issue.term}-${index}`}>
                          <strong>{issue.term}</strong>
                          <span>{issue.reason}</span>
                          <em>{issue.suggestion}</em>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>当前促销文案未发现明显违规词。</p>
                  )}
                </div>
              ) : null}
            </>
          ) : null}

          <div className="moduleSectionHeader">
            <div>
              <h3>{copy.title}</h3>
              <p>{copy.description}</p>
            </div>
            <em>
              {activeProgress.isGenerating
                ? `并行生成中 ${activeProgress.completed}/${activeProgress.total}`
                : `${enabledCount}/${currentModules.length} 已选择，${generatedCount} 已生成`}
            </em>
          </div>

          <div className="moduleList">
            {currentModules.map((module) => {
              const isCurrent = (activeProgress.runningModuleIds ?? []).includes(module.id);
              const isGenerated = generatedIds.has(module.id);
              return (
                <div
                  className="moduleRow"
                  key={module.id}
                  onClick={() => onToggleModule(module.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onToggleModule(module.id);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                >
                  <span className={module.enabled ? "checkBox checked" : "checkBox"}>{module.enabled ? <Check size={20} /> : null}</span>
                  <span>
                    <b>{module.name}：</b>
                    {module.description}
                  </span>
                  <em className={isCurrent ? "moduleStatus active" : "moduleStatus"}>{isCurrent ? "生成中" : isGenerated ? "已生成" : "待生成"}</em>
                  <span className="moduleActions">
                    <button
                      className="inlineActionButton"
                      disabled={activeProgress.isGenerating}
                      onClick={(event) => {
                        event.stopPropagation();
                        onGenerate(module.id);
                      }}
                      type="button"
                    >
                      {isCurrent ? "生成中" : isGenerated ? "重新生成" : "生成"}
                    </button>
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="panel sidePanel">
          <div className="sectionTitle compact">
            <span>
              <WandSparkles size={20} />
            </span>
            <div>
              <h2>当前生成方案</h2>
              <p>生成前核对模型、风格和模块数量。</p>
            </div>
          </div>
          <div className="planCard">
            {styleSource === "preset" ? <img src={selectedStyle.asset} alt={selectedStyle.name} /> : null}
            <div className="planMeta">
              <div>
                <span>当前风格</span>
                <b>{selectedStyle.name}</b>
              </div>
              <div>
                <span>生成版块</span>
                <b>{copy.title}</b>
              </div>
              <div>
                <span>生成内容</span>
                <b>{enabledCount} 张{copy.moduleLabel}</b>
              </div>
              <div>
                <span>输出内容</span>
                <b>{copy.output}</b>
              </div>
              <div>
                <span>目标平台</span>
                <b>{selectedPlatform.name}</b>
              </div>
            </div>
          </div>
          <div className="modelStack">
            <article>
              <header>
                <h3>文字分析模型</h3>
                <code>{modelConfig.textAnalysis.model}</code>
              </header>
              <p>用于资料解析、卖点提炼、模块 brief 和图片 prompt 规划；默认 max_tokens {modelConfig.textAnalysis.defaults.max_tokens}。</p>
            </article>
            <article>
              <header>
                <h3>图片生成模型</h3>
                <code>{selectedImageModel.model}</code>
              </header>
              <label className="fieldLabel" htmlFor="image-model-select">
                选择图片模型
              </label>
              <select
                id="image-model-select"
                className="selectInput"
                value={selectedImageModel.id}
                onChange={(event) => onImageModelChange(event.target.value)}
                disabled={activeProgress.isGenerating}
              >
                {imageModelOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label} · {selectedPlatform.generationSize}
                  </option>
                ))}
              </select>
              <p>
                当前平台生成尺寸 {selectedPlatform.generationSize}，图片请求按平台尺寸提交。
              </p>
              <label className="fieldLabel" htmlFor="generation-mode-select">
                生成模式
              </label>
              <select
                id="generation-mode-select"
                className="selectInput"
                value={generationMode}
                onChange={(event) => onGenerationModeChange(event.target.value as GenerationMode)}
                disabled={activeProgress.isGenerating}
              >
                <option value="reference_generate">AI 参考生成（整图）</option>
                <option value="fixed_product_composite">固定产品合成</option>
              </select>
              <p>
                默认使用 AI 参考生成：模型根据提示词和产品图一次性生成整张图。需要严格复用原产品母版时，再切换固定产品合成。
              </p>
            </article>
          </div>
          <div className="rightNote">
            <Lock size={18} />
            <span>API Key 只由后端环境变量读取，前端不保存密钥。</span>
          </div>
        </aside>
      </div>

      <footer className="bottomActions">
        <button className="ghostButton" onClick={onBack} type="button">
          上一步
        </button>
        <button className="primaryButton" onClick={() => onGenerate()} disabled={activeProgress.isGenerating} type="button">
          <ImageIcon size={22} />
          {activeProgress.isGenerating ? `${copy.buttonLabel}生成中...` : `生成 ${enabledCount} 张${copy.buttonLabel}`}
        </button>
      </footer>
    </>
  );
}
