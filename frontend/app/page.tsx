"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { ModulesStep } from "@/components/ModulesStep";
import { PreviewStep } from "@/components/PreviewStep";
import { ReviewStep } from "@/components/ReviewStep";
import { Stepper } from "@/components/Stepper";
import { StyleStep } from "@/components/StyleStep";
import { UploadStep } from "@/components/UploadStep";
import { DEMO_MODEL_CONFIG } from "@/lib/constants";
import { analyzeUploadedMaterials, fetchModelConfig, fetchProjectDefaults, generateImages } from "@/lib/api";
import {
  applyProductInfoDraft,
  createEmptyProductInfo,
  mergeProductInfoWithManualPriority,
  productInfoDraftHasValue,
  type ProductInfoFieldKey
} from "@/lib/productInfo";
import type { ImageGroup, MaterialPayload, ModuleConfig, ProductInfo, PublicModelConfig, StepId, StyleOption, UploadedFileInfo, UploadSlot } from "@/lib/types";

const order: StepId[] = ["upload", "review", "style", "modules", "preview"];
const PROJECT_STATE_STORAGE_KEY = "detail-image-agent-project-state-v1";

const groupLabel: Record<ImageGroup, string> = {
  main: "主图",
  campaign: "活动主图",
  detail: "详情图"
};

type GeneratedImage = { module_id: string; url: string };
type GenerationProgress = { isGenerating: boolean; completed: number; total: number; currentModuleId: string; errorCount: number };
type GenerationProgressMap = Record<ImageGroup, GenerationProgress>;

type PersistedProjectState = {
  productInfo: ProductInfo | null;
  hasAiProductInfo: boolean;
  selectedStyleId: string;
  selectedCategory: string;
  activeImageGroup: ImageGroup;
  promotionInfo: string;
  modules: ModuleConfig[];
  generatedImages: GeneratedImage[];
  statusText: string;
};

function createIdleGenerationProgress(): GenerationProgressMap {
  return {
    main: { isGenerating: false, completed: 0, total: 0, currentModuleId: "", errorCount: 0 },
    campaign: { isGenerating: false, completed: 0, total: 0, currentModuleId: "", errorCount: 0 },
    detail: { isGenerating: false, completed: 0, total: 0, currentModuleId: "", errorCount: 0 }
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
    return {
      productInfo: parsed.productInfo ?? null,
      hasAiProductInfo: Boolean(parsed.hasAiProductInfo && parsed.productInfo),
      selectedStyleId: parsed.selectedStyleId || "green_repair",
      selectedCategory: parsed.selectedCategory || "护肤精华",
      activeImageGroup,
      promotionInfo: parsed.promotionInfo || "",
      modules: Array.isArray(parsed.modules) ? parsed.modules : [],
      generatedImages: Array.isArray(parsed.generatedImages) ? parsed.generatedImages : [],
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

function upsertGeneratedImages(current: GeneratedImage[], nextImages: GeneratedImage[]) {
  const nextById = new Map(current.map((image) => [image.module_id, image]));
  nextImages.forEach((image) => nextById.set(image.module_id, image));
  return Array.from(nextById.values());
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
  const [selectedCategory, setSelectedCategory] = useState("护肤精华");
  const [modelConfig, setModelConfig] = useState<PublicModelConfig>(DEMO_MODEL_CONFIG);
  const [generatedImages, setGeneratedImages] = useState<GeneratedImage[]>([]);
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
        setSelectedCategory(restored.selectedCategory);
        setActiveImageGroup(restored.activeImageGroup);
        setPromotionInfo(restored.promotionInfo);
        setModules(mergeRestoredModules(defaults.modules, restored.modules));
        setGeneratedImages(restored.generatedImages);
        setStatusText(restored.generatedImages.length ? "已恢复生成结果" : restored.statusText);
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
      selectedCategory,
      activeImageGroup,
      promotionInfo,
      modules,
      generatedImages,
      statusText
    });
  }, [activeImageGroup, generatedImages, hasAiProductInfo, hasRestoredProjectState, modules, productInfo, promotionInfo, selectedCategory, selectedStyleId, statusText]);

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
    setStatusText("资料已加入");
  }

  function updateCategory(category: string) {
    setSelectedCategory(category);
    setProductInfo((current) => (current ? { ...current, category } : current));
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

    setGenerationProgress((current) => ({
      ...current,
      [group]: {
        isGenerating: true,
        completed: 0,
        total: modulesToGenerate.length,
        currentModuleId: modulesToGenerate[0]?.id ?? "",
        errorCount: 0
      }
    }));
    setStatusText(`${groupLabel[group]}生成中 0/${modulesToGenerate.length}`);

    let errorCount = 0;
    try {
      for (const [index, module] of modulesToGenerate.entries()) {
        setGenerationProgress((current) => ({
          ...current,
          [group]: { ...current[group], currentModuleId: module.id }
        }));
        const result = await generateImages([module.id], selectedStyleId, productInfo, referenceImages, group === "campaign" ? promotionInfo : "");
        errorCount += result.errors?.length ?? 0;
        if (result.images.length) {
          setGeneratedImages((current) => upsertGeneratedImages(current, result.images));
        }
        setGenerationProgress((current) => ({
          ...current,
          [group]: {
            ...current[group],
            completed: index + 1,
            currentModuleId: modulesToGenerate[index + 1]?.id ?? "",
            errorCount
          }
        }));
        setStatusText(`${groupLabel[group]}生成中 ${index + 1}/${modulesToGenerate.length}`);
      }
      setStatusText(errorCount ? `${groupLabel[group]}已生成，部分图片使用兜底` : `${groupLabel[group]}已生成`);
    } finally {
      setGenerationProgress((current) => ({
        ...current,
        [group]: { ...current[group], isGenerating: false, currentModuleId: "" }
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
        <div className="statusBadge">
          <span />
          {statusText}
        </div>
      </header>

      <div className="pageWrap">
        <Stepper activeStep={activeStep} onStepChange={go} />

        {activeStep === "upload" ? (
          <UploadStep
            uploadedFiles={uploadedFiles}
            productInfo={productInfo}
            productName={productInfo?.product_name ?? "待 AI 解析"}
            selectedStyleName={selectedStyle.name}
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
            selectedStyleId={selectedStyleId}
            onSelect={setSelectedStyleId}
            onCategoryChange={updateCategory}
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
            selectedStyle={selectedStyle}
            modelConfig={modelConfig}
            generatedImages={generatedImages}
            generationProgress={generationProgress}
            promotionInfo={promotionInfo}
            onPromotionInfoChange={setPromotionInfo}
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
            generationProgress={generationProgress}
            onGenerateModule={(group, moduleId) => handleGenerate(group, moduleId)}
            onImageGroupChange={setActiveImageGroup}
            onBack={() => go(previousStep(activeStep))}
          />
        ) : null}
      </div>
    </main>
  );
}
