"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { ModulesStep } from "@/components/ModulesStep";
import { PreviewStep } from "@/components/PreviewStep";
import { ReviewStep } from "@/components/ReviewStep";
import { Stepper } from "@/components/Stepper";
import { StyleStep } from "@/components/StyleStep";
import { UploadStep } from "@/components/UploadStep";
import { COMMERCE_PLATFORMS, DEMO_MODEL_CONFIG, OFFICIAL_PROJECT_TEMPLATES } from "@/lib/constants";
import {
  analyzeUploadedMaterials,
  editGeneratedImage,
  fetchModelConfig,
  fetchProjectDefaults,
  generateAiCustomStyleSample,
  generateImages,
  planAiCustomStyle
} from "@/lib/api";
import {
  applyProductInfoDraft,
  createEmptyProductInfo,
  mergeProductInfoWithManualPriority,
  productInfoDraftHasValue,
  type ProductInfoFieldKey
} from "@/lib/productInfo";
import {
  appendImageVersions,
  applyTemplateToModules,
  createTemplateFromProject,
  extractDominantColorsFromRgba,
  getSelectedGeneratedImages,
  recommendStyleFromBrandColors,
  runParallelImageGeneration,
  selectImageVersion
} from "@/lib/projectEnhancements";
import type {
  CommercePlatformId,
  GeneratedImageVersionState,
  ImageGroup,
  MaterialPayload,
  ModuleConfig,
  ProductInfo,
  ProjectTemplate,
  PublicModelConfig,
  StepId,
  StyleOption,
  StyleSource,
  UploadedFileInfo,
  UploadSlot
} from "@/lib/types";

const order: StepId[] = ["upload", "review", "style", "modules", "preview"];
const PROJECT_STATE_STORAGE_KEY = "detail-image-agent-project-state-v1";
const WHITE_BACKGROUND_MODULE_IDS = new Set(["main_white_bg", "campaign_white_bg"]);

const groupLabel: Record<ImageGroup, string> = {
  main: "主图",
  campaign: "活动主图",
  detail: "详情图"
};

type GeneratedImage = { module_id: string; url: string };
type GenerationProgress = { isGenerating: boolean; completed: number; total: number; runningModuleIds: string[]; errorCount: number };
type GenerationProgressMap = Record<ImageGroup, GenerationProgress>;
type ImageVersionStore = { versions: GeneratedImageVersionState; selectedVersionIds: Record<string, string> };

type PersistedProjectState = {
  productInfo: ProductInfo | null;
  hasAiProductInfo: boolean;
  selectedStyleId: string;
  customStyle: StyleOption | null;
  styleSource: StyleSource;
  selectedCategory: string;
  selectedPlatformId: CommercePlatformId;
  activeImageGroup: ImageGroup;
  promotionInfo: string;
  modules: ModuleConfig[];
  generatedImages: GeneratedImage[];
  generatedImageVersions: GeneratedImageVersionState;
  selectedVersionIds: Record<string, string>;
  userTemplates: ProjectTemplate[];
  brandColors: string[];
  statusText: string;
};

function createEmptyImageVersionStore(): ImageVersionStore {
  return { versions: {}, selectedVersionIds: {} };
}

function createIdleGenerationProgress(): GenerationProgressMap {
  return {
    main: { isGenerating: false, completed: 0, total: 0, runningModuleIds: [], errorCount: 0 },
    campaign: { isGenerating: false, completed: 0, total: 0, runningModuleIds: [], errorCount: 0 },
    detail: { isGenerating: false, completed: 0, total: 0, runningModuleIds: [], errorCount: 0 }
  };
}

function moduleGroup(module: ModuleConfig): ImageGroup {
  return module.image_group ?? "detail";
}

function nextStep(current: StepId) {
  return order[Math.min(order.indexOf(current) + 1, order.length - 1)];
}

function previousStep(current: StepId) {
  return order[Math.max(order.indexOf(current) - 1, 0)];
}

function readPersistedProjectState(): PersistedProjectState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PROJECT_STATE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PersistedProjectState>;
    const activeImageGroup = ["main", "campaign", "detail"].includes(parsed.activeImageGroup ?? "") ? (parsed.activeImageGroup as ImageGroup) : "main";
    const styleSource: StyleSource = parsed.styleSource === "reference" || parsed.styleSource === "ai_custom" ? parsed.styleSource : "preset";
    return {
      productInfo: parsed.productInfo ?? null,
      hasAiProductInfo: Boolean(parsed.hasAiProductInfo && parsed.productInfo),
      selectedStyleId: parsed.selectedStyleId || "green_repair",
      customStyle: parsed.customStyle && typeof parsed.customStyle === "object" ? (parsed.customStyle as StyleOption) : null,
      styleSource,
      selectedCategory: parsed.selectedCategory || "护肤精华",
      activeImageGroup,
      selectedPlatformId: COMMERCE_PLATFORMS.some((platform) => platform.id === parsed.selectedPlatformId) ? (parsed.selectedPlatformId as CommercePlatformId) : "tmall",
      promotionInfo: parsed.promotionInfo || "",
      modules: Array.isArray(parsed.modules) ? parsed.modules : [],
      generatedImages: Array.isArray(parsed.generatedImages) ? parsed.generatedImages : [],
      generatedImageVersions: parsed.generatedImageVersions && typeof parsed.generatedImageVersions === "object" ? parsed.generatedImageVersions : {},
      selectedVersionIds: parsed.selectedVersionIds && typeof parsed.selectedVersionIds === "object" ? parsed.selectedVersionIds : {},
      userTemplates: Array.isArray(parsed.userTemplates) ? parsed.userTemplates : [],
      brandColors: Array.isArray(parsed.brandColors) ? parsed.brandColors.filter((color): color is string => typeof color === "string") : [],
      statusText: parsed.statusText || "原型预览"
    };
  } catch {
    return null;
  }
}

function mergeRestoredModules(defaultModules: ModuleConfig[], restoredModules: ModuleConfig[]) {
  const restoredById = new Map(restoredModules.map((module) => [module.id, module]));
  return defaultModules.map((module) => {
    const restored = restoredById.get(module.id);
    return restored ? { ...module, enabled: restored.enabled, order: restored.order ?? module.order } : module;
  });
}

function persistProjectState(state: PersistedProjectState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PROJECT_STATE_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage may be full or disabled; the app can still run without persistence.
  }
}

function fileToDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function extractColorsFromImageDataUrl(dataUrl: string) {
  return new Promise<string[]>((resolve) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      const maxSide = 96;
      const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        resolve([]);
        return;
      }
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
      resolve(extractDominantColorsFromRgba(imageData.data));
    };
    image.onerror = () => resolve([]);
    image.src = dataUrl;
  });
}

async function fileToUploadInfo(slot: UploadSlot, file: File): Promise<UploadedFileInfo> {
  const base = {
    id: `${slot}-${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
    slot,
    name: file.name,
    size: file.size,
    type: file.type || "application/octet-stream",
    lastModified: file.lastModified
  };
  if (file.type.startsWith("text/") || /\.(txt|csv)$/i.test(file.name)) {
    return { ...base, text: await file.text() };
  }
  return { ...base, dataUrl: await fileToDataUrl(file) };
}

export default function Home() {
  const [activeStep, setActiveStep] = useState<StepId>("upload");
  const [productInfo, setProductInfo] = useState<ProductInfo | null>(null);
  const [hasAiProductInfo, setHasAiProductInfo] = useState(false);
  const [styles, setStyles] = useState<StyleOption[]>([]);
  const [modules, setModules] = useState<ModuleConfig[]>([]);
  const [activeImageGroup, setActiveImageGroup] = useState<ImageGroup>("main");
  const [promotionInfo, setPromotionInfo] = useState("");
  const [selectedStyleId, setSelectedStyleId] = useState("green_repair");
  const [customStyle, setCustomStyle] = useState<StyleOption | null>(null);
  const [styleSource, setStyleSource] = useState<StyleSource>("preset");
  const [isPlanningCustomStyle, setIsPlanningCustomStyle] = useState(false);
  const [isGeneratingStyleSample, setIsGeneratingStyleSample] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("护肤精华");
  const [selectedPlatformId, setSelectedPlatformId] = useState<CommercePlatformId>("tmall");
  const [modelConfig, setModelConfig] = useState<PublicModelConfig>(DEMO_MODEL_CONFIG);
  const [imageVersionStore, setImageVersionStore] = useState<ImageVersionStore>(() => createEmptyImageVersionStore());
  const [userTemplates, setUserTemplates] = useState<ProjectTemplate[]>([]);
  const [brandColors, setBrandColors] = useState<string[]>([]);
  const [generationProgress, setGenerationProgress] = useState<GenerationProgressMap>(() => createIdleGenerationProgress());
  const [statusText, setStatusText] = useState("原型预览");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileInfo[]>([]);
  const [manualFieldKeys, setManualFieldKeys] = useState<ProductInfoFieldKey[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisSource, setAnalysisSource] = useState("");
  const [hasRestoredProjectState, setHasRestoredProjectState] = useState(false);

  useEffect(() => {
    async function loadDefaults() {
      const [defaults, models] = await Promise.all([fetchProjectDefaults(), fetchModelConfig()]);
      const restored = readPersistedProjectState();
      setStyles(defaults.styles);
      setModelConfig(models);
      if (restored) {
        setProductInfo(restored.productInfo);
        setHasAiProductInfo(restored.hasAiProductInfo);
        setSelectedStyleId(restored.selectedStyleId);
        setCustomStyle(restored.customStyle);
        setStyleSource(restored.styleSource);
        setSelectedCategory(restored.selectedCategory);
        setSelectedPlatformId(restored.selectedPlatformId);
        setActiveImageGroup(restored.activeImageGroup);
        setPromotionInfo(restored.promotionInfo);
        setModules(mergeRestoredModules(defaults.modules, restored.modules));
        if (Object.keys(restored.generatedImageVersions).length) {
          setImageVersionStore({ versions: restored.generatedImageVersions, selectedVersionIds: restored.selectedVersionIds });
        } else if (restored.generatedImages.length) {
          setImageVersionStore(appendImageVersions(createEmptyImageVersionStore(), restored.generatedImages, "restored", Date.now()));
        }
        setUserTemplates(restored.userTemplates);
        setBrandColors(restored.brandColors);
        setStatusText(restored.generatedImages.length || Object.keys(restored.generatedImageVersions).length ? "已恢复生成结果" : restored.statusText);
      } else {
        setModules(defaults.modules);
      }
      setHasRestoredProjectState(true);
    }
    void loadDefaults();
  }, []);

  useEffect(() => {
    if (!hasRestoredProjectState) return;
    persistProjectState({
      productInfo,
      hasAiProductInfo,
      selectedStyleId,
      customStyle,
      styleSource,
      selectedCategory,
      selectedPlatformId,
      activeImageGroup,
      promotionInfo,
      modules,
      generatedImages: getSelectedGeneratedImages(imageVersionStore.versions, imageVersionStore.selectedVersionIds),
      generatedImageVersions: imageVersionStore.versions,
      selectedVersionIds: imageVersionStore.selectedVersionIds,
      userTemplates,
      brandColors,
      statusText
    });
  }, [activeImageGroup, brandColors, customStyle, hasAiProductInfo, hasRestoredProjectState, imageVersionStore, modules, productInfo, promotionInfo, selectedCategory, selectedPlatformId, selectedStyleId, statusText, styleSource, userTemplates]);

  useEffect(() => {
    function syncStepFromHash() {
      const hash = window.location.hash.replace("#", "") as StepId;
      if (order.includes(hash)) setActiveStep(hash);
    }

    syncStepFromHash();
    window.addEventListener("hashchange", syncStepFromHash);
    return () => window.removeEventListener("hashchange", syncStepFromHash);
  }, []);

  const selectedStyle = useMemo(
    () => styles.find((style) => style.id === selectedStyleId) ?? styles[0],
    [selectedStyleId, styles]
  );
  const selectedPlatform = useMemo(
    () => COMMERCE_PLATFORMS.find((platform) => platform.id === selectedPlatformId) ?? COMMERCE_PLATFORMS[0],
    [selectedPlatformId]
  );
  const generatedImages = useMemo(
    () => getSelectedGeneratedImages(imageVersionStore.versions, imageVersionStore.selectedVersionIds),
    [imageVersionStore]
  );
  const styleRecommendation = useMemo(() => recommendStyleFromBrandColors(brandColors), [brandColors]);
  const allTemplates = useMemo(() => [...OFFICIAL_PROJECT_TEMPLATES, ...userTemplates], [userTemplates]);

  function go(step: StepId) {
    setActiveStep(step);
    if (typeof window !== "undefined") {
      window.location.hash = step;
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function toggleModule(id: string) {
    setModules((current) =>
      current.map((module) => (module.id === id ? { ...module, enabled: !module.enabled } : module))
    );
  }

  async function addUploadedFiles(slot: UploadSlot, files: File[]) {
    setStatusText("读取上传文件");
    const nextFiles = await Promise.all(files.map((file) => fileToUploadInfo(slot, file)));
    setUploadedFiles((current) => [...current, ...nextFiles]);
    if (slot === "product_image") {
      const firstImage = nextFiles.find((file) => file.type.startsWith("image/") && file.dataUrl);
      if (firstImage?.dataUrl) {
        const colors = await extractColorsFromImageDataUrl(firstImage.dataUrl);
        if (colors.length) {
          setBrandColors(colors);
          const recommendation = recommendStyleFromBrandColors(colors);
          if (recommendation) {
            setSelectedStyleId(recommendation.styleId);
            setStatusText("已提取品牌色并推荐风格");
            return;
          }
        }
      }
    }
    setStatusText("资料已加入");
  }

  function applyProjectTemplate(template: ProjectTemplate) {
    setSelectedCategory(template.category);
    setSelectedStyleId(template.styleId);
    setStyleSource("preset");
    setSelectedPlatformId(template.platformId);
    setModules((current) => applyTemplateToModules(current, template));
    setStatusText(`已套用模板：${template.name}`);
  }

  function saveCurrentTemplate() {
    const template = createTemplateFromProject({
      id: `template-${Date.now()}`,
      name: `${selectedCategory || "项目"}模板 ${userTemplates.length + 1}`,
      category: selectedCategory,
      styleId: selectedStyleId,
      platformId: selectedPlatformId,
      modules
    });
    setUserTemplates((current) => [template, ...current].slice(0, 8));
    setStatusText("已保存为模板");
  }

  function duplicateProjectForNewProduct() {
    setProductInfo(null);
    setHasAiProductInfo(false);
    setUploadedFiles([]);
    setManualFieldKeys([]);
    setAnalysisSource("");
    setImageVersionStore(createEmptyImageVersionStore());
    setGenerationProgress(createIdleGenerationProgress());
    setStatusText("已复制配置，请替换新产品资料");
    go("upload");
  }

  function selectVersion(moduleId: string, versionId: string) {
    setImageVersionStore((current) => ({
      ...current,
      selectedVersionIds: selectImageVersion(current.selectedVersionIds, moduleId, versionId)
    }));
  }

  async function handleEditImage(moduleId: string, imageUrl: string, instruction: string) {
    const trimmed = instruction.trim();
    if (!trimmed) {
      setStatusText("请先填写微调指令");
      return;
    }
    setStatusText("AI 微调中");
    const result = await editGeneratedImage(imageUrl, trimmed, selectedPlatform.mainSize);
    if (result.source === "model" && result.url) {
      setImageVersionStore((current) =>
        appendImageVersions(current, [{ module_id: moduleId, url: result.url as string }], "edit", Date.now(), trimmed)
      );
      setStatusText("微调完成，已加入新版本");
    } else {
      setStatusText(`微调失败：${result.error ?? "模型未返回图片"}`);
    }
  }

  function updateCategory(category: string) {
    setSelectedCategory(category);
    setProductInfo((current) => (current ? { ...current, category } : current));
  }

  function selectPresetStyle(styleId: string) {
    setSelectedStyleId(styleId);
    setStyleSource("preset");
  }

  function selectStyleReference() {
    setStyleSource("reference");
  }

  function selectAiCustomStyle() {
    if (!customStyle) {
      setStatusText("请先点击让 AI 规划风格");
      return;
    }
    setStyleSource("ai_custom");
  }

  async function handlePlanAiCustomStyle() {
    if (isPlanningCustomStyle) return;
    if (!productInfo || !hasAiProductInfo) {
      setStatusText("请先用 AI 解析产品信息");
      go("upload");
      return;
    }
    setIsPlanningCustomStyle(true);
    setStatusText("Gemini 3.1 Pro 正在规划风格");
    try {
      const result = await planAiCustomStyle(productInfo, selectedCategory, brandColors);
      if (result.source === "model" && result.style) {
        setCustomStyle(result.style);
        setStyleSource("ai_custom");
        setStatusText(`已规划 AI 自定义风格：${result.style.name}`);
      } else {
        setStatusText(`AI 风格规划失败：${result.error ?? "模型未返回风格"}`);
      }
    } finally {
      setIsPlanningCustomStyle(false);
    }
  }

  async function handleGenerateAiStyleSample() {
    if (isGeneratingStyleSample) return;
    if (!customStyle) {
      setStatusText("请先让 AI 规划自定义风格");
      return;
    }
    setIsGeneratingStyleSample(true);
    setStatusText("AI 风格样例图生成中");
    try {
      const result = await generateAiCustomStyleSample(customStyle, productInfo ?? undefined);
      if (result.source === "model" && result.style) {
        setCustomStyle(result.style);
        setStyleSource("ai_custom");
        setStatusText(`已生成风格样例图：${result.style.name}`);
      } else {
        setStatusText(`风格样例图生成失败：${result.error ?? "模型未返回图片"}`);
      }
    } finally {
      setIsGeneratingStyleSample(false);
    }
  }

  function updateManualField(key: ProductInfoFieldKey, draft: string) {
    setProductInfo((current) => applyProductInfoDraft(current ?? createEmptyProductInfo(selectedCategory), key, draft));
    setManualFieldKeys((current) => {
      const hasManualValue = productInfoDraftHasValue(key, draft);
      if (hasManualValue && !current.includes(key)) return [...current, key];
      if (!hasManualValue) return current.filter((item) => item !== key);
      return current;
    });
  }

  async function handleAnalyzeMaterials() {
    if (isAnalyzing) return;
    if (uploadedFiles.length === 0) {
      setStatusText("请先上传资料");
      return;
    }
    const materials: MaterialPayload[] = uploadedFiles.map((file) => ({
      slot: file.slot,
      filename: file.name,
      content_type: file.type,
      data_url: file.dataUrl,
      text: file.text
    }));
    setIsAnalyzing(true);
    setStatusText("AI 解析中");
    try {
      const result = await analyzeUploadedMaterials(materials);
      setAnalysisSource(
        result.source === "model" && result.product_info
          ? "AI 已根据上传资料更新商品信息。"
          : `AI 暂未返回有效结果，请检查上传资料或稍后重试。${result.error ? `原因：${result.error}` : ""}`
      );
      if (result.source === "model" && result.product_info) {
        const mergedProductInfo = productInfo
          ? mergeProductInfoWithManualPriority(productInfo, result.product_info, manualFieldKeys)
          : result.product_info;
        setProductInfo(mergedProductInfo);
        setHasAiProductInfo(true);
        setSelectedCategory(mergedProductInfo.category || selectedCategory);
        setStatusText("AI 已解析资料");
        go("review");
      } else {
        setHasAiProductInfo(false);
        setStatusText("AI 未返回有效结果");
      }
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function handleGenerate(group: ImageGroup = activeImageGroup, targetModuleId?: string) {
    const groupProgress = generationProgress[group];
    if (groupProgress.isGenerating) return;
    const enabledModules = modules
      .filter((module) => module.enabled && moduleGroup(module) === group)
      .sort((a, b) => a.order - b.order);
    const targetModule = targetModuleId ? modules.find((module) => module.id === targetModuleId && moduleGroup(module) === group) : null;
    const modulesToGenerate = targetModule ? [targetModule] : enabledModules;
    if (modulesToGenerate.length === 0) {
      setStatusText(targetModuleId ? "未找到要生成的图片" : `请至少选择 1 张${groupLabel[group]}`);
      return;
    }
    if (!productInfo || !hasAiProductInfo) {
      setStatusText("请先用 AI 解析产品信息");
      go("upload");
      return;
    }

    const referenceImages = uploadedFiles
      .filter((file) => file.slot === "product_image" && file.type.startsWith("image/") && file.dataUrl)
      .map((file) => file.dataUrl as string)
      .slice(0, 4);
    const styleReferenceImages = uploadedFiles
      .filter((file) => file.slot === "style_reference" && file.type.startsWith("image/") && file.dataUrl)
      .map((file) => file.dataUrl as string)
      .slice(0, 4);
    const activeStyleReferenceImages = styleSource === "reference" ? styleReferenceImages : [];
    const activeCustomStyle = styleSource === "ai_custom" && customStyle ? customStyle : undefined;
    if (modulesToGenerate.some((module) => WHITE_BACKGROUND_MODULE_IDS.has(module.id)) && referenceImages.length === 0) {
      setStatusText("白底图需要先上传产品图，避免 AI 重绘导致包装或 Logo 变形");
      return;
    }
    if (styleSource === "reference" && activeStyleReferenceImages.length === 0) {
      setStatusText("请先上传并选择风格参考图");
      return;
    }
    if (styleSource === "ai_custom" && !activeCustomStyle) {
      setStatusText("请先让 AI 规划自定义风格");
      return;
    }

    setGenerationProgress((current) => ({
      ...current,
      [group]: {
        isGenerating: true,
        completed: 0,
        total: modulesToGenerate.length,
        runningModuleIds: modulesToGenerate.map((module) => module.id),
        errorCount: 0
      }
    }));
    setStatusText(`${groupLabel[group]}并行生成中 0/${modulesToGenerate.length}`);

    try {
      const summary = await runParallelImageGeneration(
        modulesToGenerate,
        (module) =>
          generateImages(
            [module.id],
            selectedStyleId,
            productInfo,
            referenceImages,
            group === "campaign" ? promotionInfo : "",
            selectedPlatform.mainSize,
            activeStyleReferenceImages,
            activeCustomStyle
          ),
        (module, result, progress) => {
          if (result.images.length) {
            setImageVersionStore((current) => appendImageVersions(current, result.images, result.source || "model"));
          }
          setGenerationProgress((current) => ({
            ...current,
            [group]: {
              ...current[group],
              completed: progress.completed,
              runningModuleIds: current[group].runningModuleIds.filter((moduleId) => moduleId !== module.id),
              errorCount: progress.errorCount
            }
          }));
          setStatusText(`${groupLabel[group]}并行生成中 ${progress.completed}/${progress.total}`);
        }
      );
      setStatusText(summary.errorCount ? `${groupLabel[group]}已生成，部分图片使用兜底` : `${groupLabel[group]}已生成`);
    } finally {
      setGenerationProgress((current) => ({
        ...current,
        [group]: { ...current[group], isGenerating: false, runningModuleIds: [] }
      }));
    }
  }

  if (!selectedStyle || modules.length === 0) {
    return (
      <main className="loading">
        <CheckCircle2 size={34} />
        <p>正在加载系统配置...</p>
      </main>
    );
  }

  return (
    <main className="appShell">
      <header className="topbar">
        <button className="backButton" onClick={() => go("upload")}>
          <ArrowLeft size={18} />
          返回项目
        </button>
        <h1>商品详情图生成智能体</h1>
        <div className="topbarActions">
          <button className="backButton" onClick={duplicateProjectForNewProduct} type="button">
            复制项目
          </button>
          <div className="statusBadge">
            <span />
            {statusText}
          </div>
        </div>
      </header>

      <div className="pageWrap">
        <Stepper activeStep={activeStep} onStepChange={go} />

        {activeStep === "upload" ? (
          <UploadStep
            uploadedFiles={uploadedFiles}
            productInfo={productInfo}
            productName={productInfo?.product_name ?? "待 AI 解析"}
            selectedStyleName={styleSource === "reference" ? "风格参考图" : styleSource === "ai_custom" ? customStyle?.name ?? "AI 自定义风格" : selectedStyle.name}
            moduleCount={modules.filter((module) => module.enabled).length}
            manualFieldKeys={manualFieldKeys}
            isAnalyzing={isAnalyzing}
            analysisSource={analysisSource}
            onFilesAdded={addUploadedFiles}
            onFileRemove={(id) => setUploadedFiles((current) => current.filter((file) => file.id !== id))}
            onManualFieldChange={updateManualField}
            onAnalyze={handleAnalyzeMaterials}
            onNext={() => go(nextStep(activeStep))}
          />
        ) : null}

        {activeStep === "style" ? (
          <StyleStep
            styles={styles}
            category={selectedCategory}
            styleSource={styleSource}
            selectedStyleId={selectedStyleId}
            customStyle={customStyle}
            isPlanningCustomStyle={isPlanningCustomStyle}
            isGeneratingStyleSample={isGeneratingStyleSample}
            uploadedFiles={uploadedFiles}
            brandColors={brandColors}
            recommendedStyleId={styleRecommendation?.styleId ?? ""}
            onSelect={selectPresetStyle}
            onAiCustomStyleSelect={selectAiCustomStyle}
            onPlanAiCustomStyle={handlePlanAiCustomStyle}
            onGenerateAiStyleSample={handleGenerateAiStyleSample}
            onStyleReferenceSelect={selectStyleReference}
            onCategoryChange={updateCategory}
            onStyleFilesAdded={addUploadedFiles}
            onStyleFileRemove={(id) => setUploadedFiles((current) => current.filter((file) => file.id !== id))}
            onBack={() => go(previousStep(activeStep))}
            onNext={() => go(nextStep(activeStep))}
          />
        ) : null}

        {activeStep === "review" ? (
          <ReviewStep
            productInfo={hasAiProductInfo ? productInfo : null}
            onUpdateProductInfo={setProductInfo}
            onBack={() => go(previousStep(activeStep))}
            onNext={() => go(nextStep(activeStep))}
          />
        ) : null}

        {activeStep === "modules" ? (
          <ModulesStep
            modules={modules}
            activeImageGroup={activeImageGroup}
            selectedStyle={styleSource === "ai_custom" && customStyle ? customStyle : selectedStyle}
            styleSource={styleSource}
            modelConfig={modelConfig}
            generatedImages={generatedImages}
            generationProgress={generationProgress}
            promotionInfo={promotionInfo}
            platforms={COMMERCE_PLATFORMS}
            selectedPlatformId={selectedPlatformId}
            templates={allTemplates}
            onPromotionInfoChange={setPromotionInfo}
            onPlatformChange={setSelectedPlatformId}
            onTemplateApply={applyProjectTemplate}
            onTemplateSave={saveCurrentTemplate}
            onImageGroupChange={setActiveImageGroup}
            onToggleModule={toggleModule}
            onBack={() => go(previousStep(activeStep))}
            onGenerate={(moduleId) => handleGenerate(activeImageGroup, moduleId)}
          />
        ) : null}

        {activeStep === "preview" ? (
          <PreviewStep
            modules={modules}
            activeImageGroup={activeImageGroup}
            generatedImages={generatedImages}
            imageVersions={imageVersionStore.versions}
            selectedVersionIds={imageVersionStore.selectedVersionIds}
            generationProgress={generationProgress}
            selectedPlatform={selectedPlatform}
            onGenerateModule={(group, moduleId) => handleGenerate(group, moduleId)}
            onSelectVersion={selectVersion}
            onEditImage={handleEditImage}
            onImageGroupChange={setActiveImageGroup}
            onBack={() => go(previousStep(activeStep))}
          />
        ) : null}
      </div>
    </main>
  );
}
