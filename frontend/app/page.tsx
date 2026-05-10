"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, CheckCircle2, Clock, CornerUpLeft, Save } from "lucide-react";
import { HistoryDrawer } from "@/components/HistoryDrawer";
import { ModulesStep } from "@/components/ModulesStep";
import { PreviewStep } from "@/components/PreviewStep";
import { ReviewStep } from "@/components/ReviewStep";
import { Stepper } from "@/components/Stepper";
import { StyleStep } from "@/components/StyleStep";
import { UploadStep } from "@/components/UploadStep";
import { COMMERCE_PLATFORMS, DEMO_MODEL_CONFIG, OFFICIAL_PROJECT_TEMPLATES } from "@/lib/constants";
import {
  analyzeUploadedMaterials,
  checkImageCompliance,
  checkTextCompliance,
  editGeneratedImage,
  fetchModelConfig,
  fetchProjectDefaults,
  generateAiCustomStyleSample,
  generateImages,
  planAiCustomStyle
} from "@/lib/api";
import { buildProductInfoComplianceItems } from "@/lib/compliance";
import { useAppViewer } from "@/lib/client/app-session";
import { saveHistory } from "@/lib/historyApi";
import {
  applyProductInfoDraft,
  createEmptyProductInfo,
  mergeProductInfoWithManualPriority,
  productInfoDraftHasValue,
  type ProductInfoFieldKey
} from "@/lib/productInfo";
import {
  appendImageVersions,
  addLanguageVersion,
  applyTemplateToModules,
  createTemplateFromProject,
  enableModuleForSingleGeneration,
  formatImageGenerationSummaryStatus,
  getSelectedGeneratedImages,
  replaceUploadedFileDataUrlsWithMaterialUrls,
  resolveHistoryIdAfterSave,
  resolveReusableHistoryId,
  runParallelImageGeneration,
  selectLanguageVersion,
  selectImageVersion
} from "@/lib/projectEnhancements";
import type {
  CommercePlatformId,
  ComplianceReport,
  GenerationMode,
  GeneratedImage,
  GeneratedImageVersionState,
  ImageGroup,
  LanguageCode,
  MaterialPayload,
  ModuleConfig,
  PersistedProjectState,
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
const PROJECT_STATE_SCHEMA_VERSION = 2;
const DEFAULT_CATEGORY = "";
const DEFAULT_STYLE_ID = "green_repair";
const DEFAULT_PLATFORM_ID: CommercePlatformId = "tmall";
const DEFAULT_GENERATION_MODE: GenerationMode = "reference_generate";
const LANGUAGE_LABELS: Record<LanguageCode, string> = {
  "zh-CN": "中文",
  en: "English",
  th: "ไทย",
  ms: "Malay"
};

const groupLabel: Record<ImageGroup, string> = {
  main: "主图",
  campaign: "活动主图",
  detail: "详情图"
};

type GenerationProgress = { isGenerating: boolean; completed: number; total: number; runningModuleIds: string[]; errorCount: number };
type GenerationProgressMap = Record<ImageGroup, GenerationProgress>;
type ImageVersionStore = { versions: GeneratedImageVersionState; selectedVersionIds: Record<string, string> };
type LanguageGenerationState = { moduleId: string; versionId: string; language: LanguageCode } | null;
type WorkspaceSnapshot = {
  state: PersistedProjectState;
  historyId: string | null;
  uploadedFiles: UploadedFileInfo[];
  manualFieldKeys: ProductInfoFieldKey[];
  analysisSource: string;
  activeStep: StepId;
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

function normalizeGenerationMode(rawMode: unknown, schemaVersion?: number): GenerationMode {
  const mode =
    rawMode === "reference_generate" || rawMode === "fixed_product_composite"
      ? rawMode
      : DEFAULT_GENERATION_MODE;
  if (schemaVersion !== PROJECT_STATE_SCHEMA_VERSION && mode === "fixed_product_composite") {
    return DEFAULT_GENERATION_MODE;
  }
  return mode;
}

function readPersistedProjectState(): PersistedProjectState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(PROJECT_STATE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PersistedProjectState>;
    const schemaVersion = typeof parsed.projectStateSchemaVersion === "number" ? parsed.projectStateSchemaVersion : undefined;
    const activeImageGroup = ["main", "campaign", "detail"].includes(parsed.activeImageGroup ?? "") ? (parsed.activeImageGroup as ImageGroup) : "main";
    const styleSource: StyleSource = parsed.styleSource === "ai_custom" ? parsed.styleSource : "preset";
    return {
      projectStateSchemaVersion: PROJECT_STATE_SCHEMA_VERSION,
      productInfo: parsed.productInfo ?? null,
      hasAiProductInfo: Boolean(parsed.hasAiProductInfo && parsed.productInfo),
      uploadedFiles: Array.isArray(parsed.uploadedFiles) ? parsed.uploadedFiles : [],
      selectedStyleId: parsed.selectedStyleId || DEFAULT_STYLE_ID,
      customStyle: parsed.customStyle && typeof parsed.customStyle === "object" ? (parsed.customStyle as StyleOption) : null,
      styleSource,
      selectedCategory: parsed.selectedCategory || DEFAULT_CATEGORY,
      activeImageGroup,
      selectedPlatformId: COMMERCE_PLATFORMS.some((platform) => platform.id === parsed.selectedPlatformId) ? (parsed.selectedPlatformId as CommercePlatformId) : DEFAULT_PLATFORM_ID,
      selectedImageModelId: parsed.selectedImageModelId || "primary",
      generationMode: normalizeGenerationMode(parsed.generationMode, schemaVersion),
      promotionInfo: parsed.promotionInfo || "",
      modules: Array.isArray(parsed.modules) ? parsed.modules : [],
      generatedImages: Array.isArray(parsed.generatedImages) ? parsed.generatedImages : [],
      generatedImageVersions: parsed.generatedImageVersions && typeof parsed.generatedImageVersions === "object" ? parsed.generatedImageVersions : {},
      selectedVersionIds: parsed.selectedVersionIds && typeof parsed.selectedVersionIds === "object" ? parsed.selectedVersionIds : {},
      userTemplates: Array.isArray(parsed.userTemplates) ? parsed.userTemplates : [],
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

function createProjectStateSnapshot(input: {
  productInfo: ProductInfo | null;
  hasAiProductInfo: boolean;
  uploadedFiles: UploadedFileInfo[];
  selectedStyleId: string;
  customStyle: StyleOption | null;
  styleSource: StyleSource;
  selectedCategory: string;
  selectedPlatformId: CommercePlatformId;
  selectedImageModelId: string;
  generationMode: GenerationMode;
  activeImageGroup: ImageGroup;
  promotionInfo: string;
  modules: ModuleConfig[];
  imageVersionStore: ImageVersionStore;
  userTemplates: ProjectTemplate[];
  statusText: string;
}): PersistedProjectState {
  return {
    projectStateSchemaVersion: PROJECT_STATE_SCHEMA_VERSION,
    productInfo: input.productInfo,
    hasAiProductInfo: input.hasAiProductInfo,
    uploadedFiles: input.uploadedFiles,
    selectedStyleId: input.selectedStyleId,
    customStyle: input.customStyle,
    styleSource: input.styleSource,
    selectedCategory: input.selectedCategory,
    selectedPlatformId: input.selectedPlatformId,
    selectedImageModelId: input.selectedImageModelId,
    generationMode: input.generationMode,
    activeImageGroup: input.activeImageGroup,
    promotionInfo: input.promotionInfo,
    modules: input.modules,
    generatedImages: getSelectedGeneratedImages(input.imageVersionStore.versions, input.imageVersionStore.selectedVersionIds),
    generatedImageVersions: input.imageVersionStore.versions,
    selectedVersionIds: input.imageVersionStore.selectedVersionIds,
    userTemplates: input.userTemplates,
    statusText: input.statusText
  };
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
  const { viewer: appViewer } = useAppViewer();
  const [activeStep, setActiveStep] = useState<StepId>("upload");
  const [productInfo, setProductInfo] = useState<ProductInfo | null>(null);
  const [hasAiProductInfo, setHasAiProductInfo] = useState(false);
  const [styles, setStyles] = useState<StyleOption[]>([]);
  const [modules, setModules] = useState<ModuleConfig[]>([]);
  const [activeImageGroup, setActiveImageGroup] = useState<ImageGroup>("main");
  const [promotionInfo, setPromotionInfo] = useState("");
  const [selectedStyleId, setSelectedStyleId] = useState(DEFAULT_STYLE_ID);
  const [customStyle, setCustomStyle] = useState<StyleOption | null>(null);
  const [styleSource, setStyleSource] = useState<StyleSource>("preset");
  const [isPlanningCustomStyle, setIsPlanningCustomStyle] = useState(false);
  const [isGeneratingStyleSample, setIsGeneratingStyleSample] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState(DEFAULT_CATEGORY);
  const [selectedPlatformId, setSelectedPlatformId] = useState<CommercePlatformId>(DEFAULT_PLATFORM_ID);
  const [selectedImageModelId, setSelectedImageModelId] = useState("primary");
  const [selectedGenerationMode, setSelectedGenerationMode] = useState<GenerationMode>(DEFAULT_GENERATION_MODE);
  const [modelConfig, setModelConfig] = useState<PublicModelConfig>(DEMO_MODEL_CONFIG);
  const [imageVersionStore, setImageVersionStore] = useState<ImageVersionStore>(() => createEmptyImageVersionStore());
  const [userTemplates, setUserTemplates] = useState<ProjectTemplate[]>([]);
  const [generationProgress, setGenerationProgress] = useState<GenerationProgressMap>(() => createIdleGenerationProgress());
  const [languageGeneration, setLanguageGeneration] = useState<LanguageGenerationState>(null);
  const [statusText, setStatusText] = useState("原型预览");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFileInfo[]>([]);
  const [manualFieldKeys, setManualFieldKeys] = useState<ProductInfoFieldKey[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisSource, setAnalysisSource] = useState("");
  const [reviewCompliance, setReviewCompliance] = useState<ComplianceReport | null>(null);
  const [promotionCompliance, setPromotionCompliance] = useState<ComplianceReport | null>(null);
  const [imageComplianceReport, setImageComplianceReport] = useState<ComplianceReport | null>(null);
  const [isCheckingImageCompliance, setIsCheckingImageCompliance] = useState(false);
  const [hasRestoredProjectState, setHasRestoredProjectState] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [currentHistoryId, setCurrentHistoryId] = useState<string | null>(null);
  const [isSavingHistory, setIsSavingHistory] = useState(false);
  const [returnWorkspaceSnapshot, setReturnWorkspaceSnapshot] = useState<WorkspaceSnapshot | null>(null);
  const hasUnsavedImages = useRef(false);
  const [defaultModules, setDefaultModules] = useState<ModuleConfig[]>([]);

  useEffect(() => {
    async function loadDefaults() {
      const [defaults, models] = await Promise.all([fetchProjectDefaults(), fetchModelConfig()]);
      const restored = readPersistedProjectState();
      setStyles(defaults.styles);
      setModelConfig(models);
      setDefaultModules(defaults.modules);
      if (restored) {
        setProductInfo(restored.productInfo);
        setHasAiProductInfo(restored.hasAiProductInfo);
        setUploadedFiles(restored.uploadedFiles ?? []);
        setSelectedStyleId(restored.selectedStyleId);
        setCustomStyle(restored.customStyle);
        setStyleSource(restored.styleSource);
        setSelectedCategory(restored.selectedCategory);
        setSelectedPlatformId(restored.selectedPlatformId);
        setSelectedImageModelId(restored.selectedImageModelId || models.imageGeneration.defaultOptionId || "primary");
        setSelectedGenerationMode(normalizeGenerationMode(restored.generationMode, restored.projectStateSchemaVersion));
        setActiveImageGroup(restored.activeImageGroup);
        setPromotionInfo(restored.promotionInfo);
        setModules(mergeRestoredModules(defaults.modules, restored.modules));
        if (Object.keys(restored.generatedImageVersions).length) {
          setImageVersionStore({ versions: restored.generatedImageVersions, selectedVersionIds: restored.selectedVersionIds });
        } else if (restored.generatedImages.length) {
          setImageVersionStore(appendImageVersions(createEmptyImageVersionStore(), restored.generatedImages, "restored", Date.now()));
        }
        setUserTemplates(restored.userTemplates);
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
    persistProjectState(createProjectStateSnapshot({
      productInfo,
      hasAiProductInfo,
      uploadedFiles,
      selectedStyleId,
      customStyle,
      styleSource,
      selectedCategory,
      selectedPlatformId,
      selectedImageModelId,
      generationMode: selectedGenerationMode,
      activeImageGroup,
      promotionInfo,
      modules,
      imageVersionStore,
      userTemplates,
      statusText
    }));
  }, [activeImageGroup, customStyle, hasAiProductInfo, hasRestoredProjectState, imageVersionStore, modules, productInfo, promotionInfo, selectedCategory, selectedGenerationMode, selectedImageModelId, selectedPlatformId, selectedStyleId, statusText, styleSource, uploadedFiles, userTemplates]);

  useEffect(() => {
    if (!hasAiProductInfo || !productInfo) {
      setReviewCompliance(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void checkTextCompliance(buildProductInfoComplianceItems(productInfo), selectedPlatformId, productInfo).then(setReviewCompliance);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [hasAiProductInfo, productInfo, selectedPlatformId]);

  useEffect(() => {
    setImageComplianceReport(null);
  }, [activeImageGroup, imageVersionStore, selectedPlatformId]);

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
  const viewerLabel = appViewer?.nickname || appViewer?.account || "";
  const generatedImages = useMemo(
    () => getSelectedGeneratedImages(imageVersionStore.versions, imageVersionStore.selectedVersionIds),
    [imageVersionStore]
  );
  const allTemplates = useMemo(() => [...OFFICIAL_PROJECT_TEMPLATES, ...userTemplates], [userTemplates]);

  function createCurrentProjectState(status = statusText): PersistedProjectState {
    return createProjectStateSnapshot({
      productInfo,
      hasAiProductInfo,
      uploadedFiles,
      selectedStyleId,
      customStyle,
      styleSource,
      selectedCategory,
      selectedPlatformId,
      selectedImageModelId,
      generationMode: selectedGenerationMode,
      activeImageGroup,
      promotionInfo,
      modules,
      imageVersionStore,
      userTemplates,
      statusText: status
    });
  }

  function applyProjectState(state: PersistedProjectState, options?: { exactModules?: boolean; statusText?: string }) {
    setProductInfo(state.productInfo);
    setHasAiProductInfo(state.hasAiProductInfo);
    setUploadedFiles(state.uploadedFiles ?? []);
    setSelectedStyleId(state.selectedStyleId);
    setCustomStyle(state.customStyle);
    setStyleSource(state.styleSource);
    setSelectedCategory(state.selectedCategory);
    setSelectedPlatformId(state.selectedPlatformId);
    setSelectedImageModelId(state.selectedImageModelId || modelConfig.imageGeneration.defaultOptionId || "primary");
    setSelectedGenerationMode(normalizeGenerationMode(state.generationMode, state.projectStateSchemaVersion));
    setActiveImageGroup(state.activeImageGroup);
    setPromotionInfo(state.promotionInfo);
    if (state.modules?.length) {
      setModules((current) => (options?.exactModules ? state.modules : mergeRestoredModules(current, state.modules)));
    }
    if (Object.keys(state.generatedImageVersions || {}).length) {
      setImageVersionStore({ versions: state.generatedImageVersions, selectedVersionIds: state.selectedVersionIds || {} });
    } else if (state.generatedImages?.length) {
      setImageVersionStore(appendImageVersions(createEmptyImageVersionStore(), state.generatedImages, "restored", Date.now()));
    } else {
      setImageVersionStore(createEmptyImageVersionStore());
    }
    setUserTemplates(state.userTemplates ?? []);
    setStatusText(options?.statusText ?? state.statusText);
  }

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

  function startNewProject() {
    setCurrentHistoryId(null);
    setReturnWorkspaceSnapshot(null);
    setProductInfo(null);
    setHasAiProductInfo(false);
    setUploadedFiles([]);
    setManualFieldKeys([]);
    setAnalysisSource("");
    setActiveImageGroup("main");
    setPromotionInfo("");
    setSelectedStyleId(styles[0]?.id ?? "green_repair");
    setCustomStyle(null);
    setStyleSource("preset");
    setSelectedCategory(DEFAULT_CATEGORY);
    setSelectedPlatformId("tmall");
    setSelectedImageModelId(modelConfig.imageGeneration.defaultOptionId || "primary");
    setSelectedGenerationMode(DEFAULT_GENERATION_MODE);
    setModules(defaultModules.map((module) => ({ ...module })));
    setImageVersionStore(createEmptyImageVersionStore());
    setGenerationProgress(createIdleGenerationProgress());
    setIsAnalyzing(false);
    setIsPlanningCustomStyle(false);
    setIsGeneratingStyleSample(false);
    setIsHistoryOpen(false);
    setStatusText("已新建项目");
    go("upload");
  }

  function selectVersion(moduleId: string, versionId: string) {
    setImageVersionStore((current) => ({
      ...current,
      selectedVersionIds: selectImageVersion(current.selectedVersionIds, moduleId, versionId)
    }));
  }

  function selectImageLanguage(moduleId: string, versionId: string, language: LanguageCode) {
    setImageVersionStore((current) => selectLanguageVersion(current, moduleId, versionId, language));
  }

  async function handleGenerateLanguage(moduleId: string, versionId: string, language: LanguageCode) {
    if (languageGeneration) return;
    const module = modules.find((item) => item.id === moduleId);
    if (!module) {
      setStatusText("未找到要生成语言版本的模块");
      return;
    }
    const referenceImages = uploadedFiles
      .filter((file) => file.slot === "product_image" && file.type.startsWith("image/") && file.dataUrl)
      .map((file) => file.dataUrl as string)
      .slice(0, 4);
    if (referenceImages.length === 0) {
      setStatusText("请先上传产品图，避免生成结果与原产品不一致");
      return;
    }
    const activeCustomStyle = styleSource === "ai_custom" && customStyle ? customStyle : undefined;
    const group = moduleGroup(module);
    const languageRequest = { targetLanguage: language };
    setLanguageGeneration({ moduleId, versionId, language });
    setStatusText(`正在重新生成 ${LANGUAGE_LABELS[language]} 整图版本`);
    try {
      const result = await generateImages(
        [moduleId],
        selectedStyleId,
        productInfo ?? undefined,
        referenceImages,
        group === "campaign" ? promotionInfo : "",
        selectedPlatform.generationSize,
        [],
        activeCustomStyle,
        selectedImageModelId,
        selectedGenerationMode,
        selectedPlatformId,
        false,
        languageRequest.targetLanguage
      );
      const generated = result.images[0];
      if (result.source !== "error" && generated?.url) {
        setImageVersionStore((current) =>
          addLanguageVersion(current, moduleId, versionId, {
            language,
            language_label: LANGUAGE_LABELS[language],
            url: generated.url,
            compliance: generated.compliance,
            createdAt: Date.now()
          })
        );
        setStatusText(`已重新生成 ${LANGUAGE_LABELS[language]} 整图版本`);
      } else {
        setStatusText(`多语言整图生成失败：${result.errors?.[0] ?? "模型未返回图片"}`);
      }
    } finally {
      setLanguageGeneration(null);
    }
  }

  async function handleCheckImageCompliance(imageUrls: string[]) {
    if (!imageUrls.length) {
      setStatusText("当前预览区暂无可检查图片");
      return;
    }
    setIsCheckingImageCompliance(true);
    setStatusText("正在进行图片 OCR 合规复查");
    try {
      const report = await checkImageCompliance(imageUrls, selectedPlatformId, productInfo);
      setImageComplianceReport(report);
      setStatusText(`图片 OCR 合规复查：${report.summary.status === "pass" ? "通过" : "需查看风险提示"}`);
    } finally {
      setIsCheckingImageCompliance(false);
    }
  }

  async function handleEditImage(moduleId: string, imageUrl: string, instruction: string) {
    const trimmed = instruction.trim();
    if (!trimmed) {
      setStatusText("请先填写微调指令");
      return;
    }
    setStatusText("AI 微调中");
    const result = await editGeneratedImage(imageUrl, trimmed, selectedPlatform.generationSize, selectedImageModelId, selectedPlatformId);
    if (result.source === "model" && result.url) {
      setImageVersionStore((current) =>
        appendImageVersions(current, [{ module_id: moduleId, url: result.url as string, compliance: result.compliance }], "edit", Date.now(), trimmed)
      );
      setStatusText("微调完成，已加入新版本");
    } else {
      setStatusText(`微调失败：${result.error ?? "模型未返回图片"}`);
    }
  }

  function selectPresetStyle(styleId: string) {
    setSelectedStyleId(styleId);
    setStyleSource("preset");
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
      const productImages = uploadedFiles
        .filter((file) => file.slot === "product_image" && file.type.startsWith("image/") && file.dataUrl)
        .map((file) => ({
          slot: file.slot,
          filename: file.name,
          content_type: file.type,
          data_url: file.dataUrl
        }));
      const result = await planAiCustomStyle(productInfo, productImages);
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
      id: file.id,
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
        if (result.uploaded_materials?.length) {
          setUploadedFiles((current) => replaceUploadedFileDataUrlsWithMaterialUrls(current, result.uploaded_materials));
        }
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
    const activeCustomStyle = styleSource === "ai_custom" && customStyle ? customStyle : undefined;
    if (referenceImages.length === 0) {
      setStatusText("请先上传产品图，避免生成结果与原产品不一致");
      return;
    }
    if (styleSource === "ai_custom" && !activeCustomStyle) {
      setStatusText("请先让 AI 规划自定义风格");
      return;
    }
    if (targetModule) {
      setModules((current) => enableModuleForSingleGeneration(current, targetModule.id));
    }
    if (group === "campaign") {
      const report = await checkTextCompliance(
        [{ text: promotionInfo, location: { source_type: "promotion", field: "promotion_info" } }],
        selectedPlatformId,
        productInfo
      );
      setPromotionCompliance(report);
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
            selectedPlatform.generationSize,
            [],
            activeCustomStyle,
            selectedImageModelId,
            selectedGenerationMode,
            selectedPlatformId,
            false
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
      setStatusText(formatImageGenerationSummaryStatus(groupLabel[group], summary));
    } finally {
      setGenerationProgress((current) => ({
        ...current,
        [group]: { ...current[group], isGenerating: false, runningModuleIds: [] }
      }));
    }
  }

  const saveToHistory = useCallback(async (options: { trackSavedHistoryId?: boolean } = {}) => {
    if (!productInfo || !hasAiProductInfo) {
      setStatusText("请先用 AI 解析产品信息后再保存");
      return;
    }
    const currentImages = getSelectedGeneratedImages(imageVersionStore.versions, imageVersionStore.selectedVersionIds);
    if (currentImages.length === 0) {
      setStatusText("暂无生成图片可保存");
      return;
    }
    setIsSavingHistory(true);
    try {
      const resolvedStyle = styleSource === "ai_custom" && customStyle ? customStyle : styles.find((s) => s.id === selectedStyleId);
      const thumbnail = currentImages[0]?.url ?? "";
      const saved = await saveHistory({
        id: resolveReusableHistoryId(currentHistoryId, null),
        product_name: productInfo.product_name || "未命名项目",
        category: productInfo.category || "",
        style_id: selectedStyleId,
        style_name: resolvedStyle?.name ?? selectedStyleId,
        platform_id: selectedPlatformId,
        thumbnail,
        image_count: currentImages.length,
        state: {
          productInfo,
          hasAiProductInfo,
          uploadedFiles,
          selectedStyleId,
          customStyle,
          styleSource,
          selectedCategory,
          selectedPlatformId,
          selectedImageModelId,
          generationMode: selectedGenerationMode,
          activeImageGroup,
          promotionInfo,
          modules,
          generatedImages: currentImages,
          generatedImageVersions: imageVersionStore.versions,
          selectedVersionIds: imageVersionStore.selectedVersionIds,
          userTemplates,
          statusText: "已从历史恢复"
        }
      });
      setCurrentHistoryId((existingId) => resolveHistoryIdAfterSave(existingId, saved?.id ?? null, options));
      hasUnsavedImages.current = false;
      setStatusText("已保存到历史记录");
    } catch {
      setStatusText("保存历史记录失败");
    } finally {
      setIsSavingHistory(false);
    }
  }, [activeImageGroup, currentHistoryId, customStyle, hasAiProductInfo, imageVersionStore, modules, productInfo, promotionInfo, selectedCategory, selectedGenerationMode, selectedImageModelId, selectedPlatformId, selectedStyleId, styleSource, styles, uploadedFiles, userTemplates]);

  // Mark dirty when new images are generated
  useEffect(() => {
    const currentImages = getSelectedGeneratedImages(imageVersionStore.versions, imageVersionStore.selectedVersionIds);
    if (currentImages.length > 0 && hasAiProductInfo) {
      hasUnsavedImages.current = true;
    }
  }, [imageVersionStore, hasAiProductInfo]);

  // Warn before leaving if there are unsaved generated images
  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (hasUnsavedImages.current) {
        event.preventDefault();
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

  async function restoreCopyFromHistory(state: PersistedProjectState, historyId?: string) {
    const originalState = createCurrentProjectState();
    setReturnWorkspaceSnapshot({
      state: originalState,
      historyId: currentHistoryId,
      uploadedFiles,
      manualFieldKeys,
      analysisSource,
      activeStep
    });
    void saveToHistory({ trackSavedHistoryId: false });
    setCurrentHistoryId(null);
    applyProjectState(state, { statusText: "已载入历史副本" });
    setManualFieldKeys([]);
    setAnalysisSource(historyId ? `正在编辑历史记录 ${historyId} 的副本，原工作区已保留。` : "正在编辑历史副本，原工作区已保留。");
    go("preview");
  }

  function returnToOriginalWorkspace() {
    if (!returnWorkspaceSnapshot) return;
    applyProjectState(returnWorkspaceSnapshot.state, { exactModules: true, statusText: "已返回原工作区" });
    setCurrentHistoryId(returnWorkspaceSnapshot.historyId);
    setUploadedFiles(returnWorkspaceSnapshot.uploadedFiles);
    setManualFieldKeys(returnWorkspaceSnapshot.manualFieldKeys);
    setAnalysisSource(returnWorkspaceSnapshot.analysisSource);
    setGenerationProgress(createIdleGenerationProgress());
    setReturnWorkspaceSnapshot(null);
    go(returnWorkspaceSnapshot.activeStep);
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
          {returnWorkspaceSnapshot ? (
            <button className="returnWorkspaceButton" onClick={returnToOriginalWorkspace} type="button">
              <CornerUpLeft size={16} />
              返回原工作区
            </button>
          ) : null}
          <button className="historyButton" onClick={() => setIsHistoryOpen(true)} type="button">
            <Clock size={16} />
            历史记录
          </button>
          <button className="historyButton" onClick={() => void saveToHistory()} disabled={isSavingHistory || generatedImages.length === 0 || !hasAiProductInfo} type="button">
            <Save size={16} />
            {isSavingHistory ? "保存中..." : "保存"}
          </button>
          <button className="backButton" onClick={startNewProject} type="button">
            新建项目
          </button>
          {viewerLabel ? (
            <div className="statusBadge">
              <span />
              {viewerLabel}
            </div>
          ) : null}
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
            selectedStyleName={styleSource === "ai_custom" ? customStyle?.name ?? "AI 自定义风格" : selectedStyle.name}
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
            styleSource={styleSource}
            selectedStyleId={selectedStyleId}
            customStyle={customStyle}
            isPlanningCustomStyle={isPlanningCustomStyle}
            isGeneratingStyleSample={isGeneratingStyleSample}
            recommendedStyleId=""
            onSelect={selectPresetStyle}
            onAiCustomStyleSelect={selectAiCustomStyle}
            onPlanAiCustomStyle={handlePlanAiCustomStyle}
            onGenerateAiStyleSample={handleGenerateAiStyleSample}
            onBack={() => go(previousStep(activeStep))}
            onNext={() => go(nextStep(activeStep))}
          />
        ) : null}

        {activeStep === "review" ? (
          <ReviewStep
            productInfo={hasAiProductInfo ? productInfo : null}
            complianceReport={reviewCompliance}
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
            selectedImageModelId={selectedImageModelId}
            generationMode={selectedGenerationMode}
            promotionCompliance={promotionCompliance}
            onPromotionInfoChange={setPromotionInfo}
            onPlatformChange={setSelectedPlatformId}
            onImageModelChange={setSelectedImageModelId}
            onGenerationModeChange={setSelectedGenerationMode}
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
            isSavingHistory={isSavingHistory}
            canSaveHistory={Boolean(productInfo && hasAiProductInfo && generatedImages.length)}
            languageGeneration={languageGeneration}
            imageComplianceReport={imageComplianceReport}
            isCheckingImageCompliance={isCheckingImageCompliance}
            onGenerateModule={(group, moduleId) => handleGenerate(group, moduleId)}
            onSelectVersion={selectVersion}
            onSelectLanguage={selectImageLanguage}
            onGenerateLanguage={(moduleId, versionId, language) => void handleGenerateLanguage(moduleId, versionId, language)}
            onCheckImagesCompliance={(imageUrls) => void handleCheckImageCompliance(imageUrls)}
            onEditImage={handleEditImage}
            onImageGroupChange={setActiveImageGroup}
            onSaveToHistory={() => void saveToHistory()}
            onBack={() => go(previousStep(activeStep))}
          />
        ) : null}
      </div>

      <HistoryDrawer
        open={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onRestoreCopy={restoreCopyFromHistory}
      />
    </main>
  );
}
