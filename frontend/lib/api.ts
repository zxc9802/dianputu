import { DEFAULT_MODULES, DEMO_MODEL_CONFIG, STYLE_OPTIONS } from "./constants";
import { MainAppRedirectError, extractApiErrorMessage, readJsonSafely, redirectToMainAppIfNeeded } from "./client/api-response";
import type { CommercePlatformId, ComplianceReport, ComplianceTextItem, DetailLayoutId, GenerationMode, LanguageCode, LanguageVersion, MaterialPayload, ModuleConfig, ProductInfo, PromptBranch, PublicModelConfig, SavedStyleRecord, StyleOption, StyleReferenceSelection, TextLayer } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const LOCAL_SAVED_STYLES_STORAGE_KEY = "detail-image-agent-saved-styles";
const LOCAL_DEV_SAVED_STYLES_USER_ID = "detail-image-agent-local-dev-user";
const LOCAL_SAVED_STYLE_HOSTNAMES = new Set(["localhost", "127.0.0.1", "0.0.0.0"]);

let currentSavedStyleUserIdPromise: Promise<string> | null = null;

function isLocalSavedStyleFallbackEnabled() {
  return typeof window !== "undefined" && LOCAL_SAVED_STYLE_HOSTNAMES.has(window.location.hostname);
}

function getScopedLocalSavedStyleStorageKey(userId: string) {
  return `${LOCAL_SAVED_STYLES_STORAGE_KEY}:${userId || LOCAL_DEV_SAVED_STYLES_USER_ID}`;
}

async function fetchCurrentSavedStyleUserId(): Promise<string> {
  if (currentSavedStyleUserIdPromise) {
    return currentSavedStyleUserIdPromise;
  }

  currentSavedStyleUserIdPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/session`, {
        method: "GET",
        cache: "no-store",
        credentials: "include"
      });
      const payload = await readJsonSafely<{
        data?: { session?: { user?: { id?: unknown } | null } | null };
      }>(response);
      redirectToMainAppIfNeeded(response, payload);
      if (!response.ok) {
        throw new Error(extractApiErrorMessage(payload, "读取当前登录状态失败"));
      }

      const userId = payload?.data?.session?.user?.id;
      return typeof userId === "string" && userId.trim() ? userId.trim() : LOCAL_DEV_SAVED_STYLES_USER_ID;
    } catch (error) {
      if (error instanceof MainAppRedirectError) {
        throw error;
      }
      currentSavedStyleUserIdPromise = null;
      return LOCAL_DEV_SAVED_STYLES_USER_ID;
    }
  })();

  return currentSavedStyleUserIdPromise;
}

function readLocalSavedStyles(userId: string): SavedStyleRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(getScopedLocalSavedStyleStorageKey(userId)) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocalSavedStyles(userId: string, records: SavedStyleRecord[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(getScopedLocalSavedStyleStorageKey(userId), JSON.stringify(records.slice(0, 50)));
  } catch {
    // The current project can still continue if local fallback persistence is unavailable.
  }
}

function createLocalSavedStyleId() {
  const randomPart = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`;
  return `local-${randomPart}`;
}

function mergeSavedStyleRecords(localItems: SavedStyleRecord[], remoteItems: SavedStyleRecord[]) {
  const localIds = new Set(localItems.map((item) => item.id));
  return [...localItems, ...remoteItems.filter((item) => !localIds.has(item.id))];
}

function saveLocalSavedStyle(userId: string, style: StyleOption, name: string): SavedStyleRecord {
  const now = new Date().toISOString();
  const saved: SavedStyleRecord = {
    id: createLocalSavedStyleId(),
    name,
    style: { ...style, name },
    created_at: now,
    updated_at: now
  };
  writeLocalSavedStyles(userId, [saved, ...readLocalSavedStyles(userId)]);
  return saved;
}

function deleteLocalSavedStyle(userId: string, id: string) {
  const before = readLocalSavedStyles(userId);
  const after = before.filter((record) => record.id !== id);
  writeLocalSavedStyles(userId, after);
  return after.length !== before.length;
}

async function requestJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 8000);
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    signal: controller.signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  }).finally(() => window.clearTimeout(timeout));
  const payload = await readJsonSafely<T>(response);
  redirectToMainAppIfNeeded(response, payload);
  if (!response.ok) {
    throw new Error(extractApiErrorMessage(payload, `API request failed: ${response.status}`));
  }
  return payload as T;
}

async function requestBlob(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<Blob> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 180000);
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    signal: controller.signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  }).finally(() => window.clearTimeout(timeout));
  if (!response.ok) {
    const payload = await readJsonSafely(response);
    redirectToMainAppIfNeeded(response, payload);
    throw new Error(extractApiErrorMessage(payload, `API request failed: ${response.status}`));
  }
  return response.blob();
}

function rethrowMainAppRedirect(error: unknown) {
  if (error instanceof MainAppRedirectError) {
    throw error;
  }
}

export async function fetchModelConfig(): Promise<PublicModelConfig> {
  try {
    return await requestJson<PublicModelConfig>("/api/models/config");
  } catch (error) {
    rethrowMainAppRedirect(error);
    return DEMO_MODEL_CONFIG;
  }
}

export async function fetchProjectDefaults(): Promise<{
  product_info?: ProductInfo;
  styles: StyleOption[];
  modules: ModuleConfig[];
}> {
  try {
    return await requestJson("/api/projects/defaults");
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      styles: STYLE_OPTIONS,
      modules: DEFAULT_MODULES
    };
  }
}

export async function generateImages(
  moduleIds: string[],
  styleId: string,
  productInfo?: ProductInfo,
  referenceImages: string[] = [],
  promotionInfo = "",
  platformSize = "",
  styleReferenceImages: string[] = [],
  styleReferenceSelections: StyleReferenceSelection[] = [],
  customStyle?: StyleOption,
  imageModelId = "",
  generationMode: GenerationMode = "reference_generate",
  platformId: CommercePlatformId = "tmall",
  layeredText = false,
  targetLanguage = "",
  promptBranch: PromptBranch = "current",
  detailLayoutId?: DetailLayoutId
) {
  try {
    const { job_id: jobId } = await createGenerateImageJob(
      moduleIds,
      styleId,
      productInfo,
      referenceImages,
      promotionInfo,
      platformSize,
      styleReferenceImages,
      styleReferenceSelections,
      customStyle,
      imageModelId,
      generationMode,
      platformId,
      layeredText,
      targetLanguage,
      promptBranch,
      detailLayoutId
    );
    return await pollGenerateImageJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      images: [],
      errors: [error instanceof Error ? error.message : "前端请求后端生成接口失败。"]
    };
  }
}

type GenerateImagesResult = {
  source: string;
  images: Array<{
    module_id: string;
    url: string;
    base_url?: string;
    text_layers?: TextLayer[];
    language_versions?: Record<string, LanguageVersion>;
    compliance?: ComplianceReport;
  }>;
  errors?: string[];
};

type GenerateImageJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
  result?: GenerateImagesResult;
};

type EditImageResult = { source: string; url?: string; error?: string; compliance?: ComplianceReport };
type EditImageJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
  result?: EditImageResult;
};
type StyleResult = {
  source: string;
  style?: StyleOption;
  error?: string;
  raw?: string;
  warnings?: string[];
  uploaded_style_references?: Array<{ id: string; slot: string; filename: string; content_type: string; url: string }>;
};
type StyleJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
  result?: StyleResult;
};

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function createGenerateImageJob(
  moduleIds: string[],
  styleId: string,
  productInfo?: ProductInfo,
  referenceImages: string[] = [],
  promotionInfo = "",
  platformSize = "",
  styleReferenceImages: string[] = [],
  styleReferenceSelections: StyleReferenceSelection[] = [],
  customStyle?: StyleOption,
  imageModelId = "",
  generationMode: GenerationMode = "reference_generate",
  platformId: CommercePlatformId = "tmall",
  layeredText = false,
  targetLanguage = "",
  promptBranch: PromptBranch = "current",
  detailLayoutId?: DetailLayoutId
) {
  return requestJson<{ job_id: string }>("/api/projects/generate/jobs", {
    method: "POST",
    body: JSON.stringify({
      module_ids: moduleIds,
      style_id: styleId,
      product_info: productInfo,
      reference_images: referenceImages,
      style_reference_images: styleReferenceImages,
      style_reference_selections: styleReferenceSelections,
      custom_style: customStyle,
      promotion_info: promotionInfo,
      platform_size: platformSize,
      platform_id: platformId,
      image_model_id: imageModelId,
      generation_mode: generationMode,
      layered_text: layeredText,
      target_language: targetLanguage,
      prompt_branch: promptBranch,
      detail_layout_id: detailLayoutId
    }),
    timeoutMs: 15000
  });
}

export async function renderLanguageVersion(baseUrl: string, textLayers: TextLayer[], language: LanguageCode, platformId: CommercePlatformId, productInfo?: ProductInfo | null) {
  try {
    return await requestJson<
      { source: "model" } & LanguageVersion
      | { source: "error"; error?: string }
    >("/api/projects/render-language", {
      method: "POST",
      body: JSON.stringify({
        base_url: baseUrl,
        text_layers: textLayers,
        language,
        platform_id: platformId,
        product_info: productInfo
      }),
      timeoutMs: 180000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error" as const,
      error: error instanceof Error ? error.message : "多语言版本生成失败"
    };
  }
}

export async function fetchGenerateImageJob(jobId: string) {
  return requestJson<GenerateImageJobStatus>(`/api/projects/generate/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollGenerateImageJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchGenerateImageJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("图片生成任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "图片生成任务失败");
    }
    await sleep(3000);
  }
  throw new Error("图片生成任务超时，请稍后重试");
}

export async function planAiCustomStyle(productInfo?: ProductInfo, productImages: MaterialPayload[] = []) {
  try {
    const { job_id: jobId } = await createPlanStyleJob(productInfo, productImages);
    return await pollPlanStyleJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 风格规划请求失败"
    };
  }
}

export async function createPlanStyleJob(productInfo?: ProductInfo, productImages: MaterialPayload[] = []) {
  return requestJson<{ job_id: string }>("/api/projects/plan-style/jobs", {
    method: "POST",
    body: JSON.stringify({
      product_info: productInfo,
      product_images: productImages
    }),
    timeoutMs: 15000
  });
}

export async function fetchPlanStyleJob(jobId: string) {
  return requestJson<StyleJobStatus>(`/api/projects/plan-style/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollPlanStyleJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchPlanStyleJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("AI 风格规划任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "AI 风格规划任务失败");
    }
    await sleep(3000);
  }
  throw new Error("AI 风格规划任务超时，请稍后重试");
}

export async function analyzeStyleReference(productInfo?: ProductInfo, styleReferenceImages: MaterialPayload[] = []) {
  try {
    const { job_id: jobId } = await createAnalyzeStyleReferenceJob(productInfo, styleReferenceImages);
    return await pollAnalyzeStyleReferenceJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "Gemini 图片对标分析请求失败"
    };
  }
}

export async function createAnalyzeStyleReferenceJob(productInfo?: ProductInfo, styleReferenceImages: MaterialPayload[] = []) {
  return requestJson<{ job_id: string }>("/api/projects/analyze-style-reference/jobs", {
    method: "POST",
    body: JSON.stringify({
      product_info: productInfo,
      style_reference_images: styleReferenceImages
    }),
    timeoutMs: 15000
  });
}

export async function fetchAnalyzeStyleReferenceJob(jobId: string) {
  return requestJson<StyleJobStatus>(`/api/projects/analyze-style-reference/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollAnalyzeStyleReferenceJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchAnalyzeStyleReferenceJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("图片对标分析任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "图片对标分析任务失败");
    }
    await sleep(3000);
  }
  throw new Error("图片对标分析任务超时，请稍后重试");
}

export async function generateAiCustomStyleSample(style: StyleOption, productInfo?: ProductInfo) {
  try {
    const { job_id: jobId } = await createPlanStyleSampleJob(style, productInfo);
    return await pollPlanStyleSampleJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 风格样例图请求失败"
    };
  }
}

export async function createPlanStyleSampleJob(style: StyleOption, productInfo?: ProductInfo) {
  return requestJson<{ job_id: string }>("/api/projects/plan-style-sample/jobs", {
    method: "POST",
    body: JSON.stringify({
      style,
      product_info: productInfo
    }),
    timeoutMs: 15000
  });
}

export async function fetchPlanStyleSampleJob(jobId: string) {
  return requestJson<StyleJobStatus>(`/api/projects/plan-style-sample/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollPlanStyleSampleJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchPlanStyleSampleJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("AI 风格样例图任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "AI 风格样例图任务失败");
    }
    await sleep(3000);
  }
  throw new Error("AI 风格样例图任务超时，请稍后重试");
}

export async function fetchSavedStyles() {
  const useLocalFallback = isLocalSavedStyleFallbackEnabled();
  const localUserId = useLocalFallback ? await fetchCurrentSavedStyleUserId() : "";
  const localItems = useLocalFallback ? readLocalSavedStyles(localUserId) : [];
  try {
    const result = await requestJson<{ items: SavedStyleRecord[]; limit: number; offset: number }>("/api/styles/saved", {
      timeoutMs: 15000
    });
    return {
      ...result,
      items: mergeSavedStyleRecords(localItems, result.items)
    };
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    if (useLocalFallback) {
      return { items: localItems, limit: 50, offset: 0 };
    }
    return { items: [], limit: 50, offset: 0 };
  }
}

export async function saveSavedStyle(style: StyleOption, name: string) {
  try {
    return await requestJson<SavedStyleRecord>("/api/styles/saved", {
      method: "POST",
      body: JSON.stringify({ name, style }),
      timeoutMs: 15000
    });
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    if (isLocalSavedStyleFallbackEnabled()) {
      return saveLocalSavedStyle(await fetchCurrentSavedStyleUserId(), style, name);
    }
    throw error;
  }
}

export async function deleteSavedStyle(id: string) {
  const useLocalFallback = isLocalSavedStyleFallbackEnabled();
  const localUserId = useLocalFallback ? await fetchCurrentSavedStyleUserId() : "";
  if (useLocalFallback && id.startsWith("local-")) {
    deleteLocalSavedStyle(localUserId, id);
    return { deleted: true, id };
  }
  try {
    return await requestJson<{ deleted: boolean; id: string }>(`/api/styles/saved/${id}`, {
      method: "DELETE",
      timeoutMs: 15000
    });
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    if (useLocalFallback && deleteLocalSavedStyle(localUserId, id)) {
      return { deleted: true, id };
    }
    throw error;
  }
}

export async function editGeneratedImage(imageUrl: string, instruction: string, platformSize = "", imageModelId = "", platformId: CommercePlatformId = "tmall") {
  try {
    const { job_id: jobId } = await createEditImageJob(imageUrl, instruction, platformSize, imageModelId, platformId);
    return await pollEditImageJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 微调请求失败"
    };
  }
}

export async function createEditImageJob(imageUrl: string, instruction: string, platformSize = "", imageModelId = "", platformId: CommercePlatformId = "tmall") {
  return requestJson<{ job_id: string }>("/api/projects/edit-image/jobs", {
    method: "POST",
    body: JSON.stringify({
      image_url: imageUrl,
      instruction,
      platform_size: platformSize,
      image_model_id: imageModelId,
      platform_id: platformId
    }),
    timeoutMs: 15000
  });
}

export async function fetchEditImageJob(jobId: string) {
  return requestJson<EditImageJobStatus>(`/api/projects/edit-image/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollEditImageJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchEditImageJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("图片微调任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "图片微调任务失败");
    }
    await sleep(1000);
  }
  throw new Error("图片微调任务超时，请稍后重试");
}

export async function editGeneratedImageDirect(imageUrl: string, instruction: string, platformSize = "", imageModelId = "", platformId: CommercePlatformId = "tmall") {
  try {
    return await requestJson<EditImageResult>("/api/projects/edit-image", {
      method: "POST",
      body: JSON.stringify({
        image_url: imageUrl,
        instruction,
        platform_size: platformSize,
        image_model_id: imageModelId,
        platform_id: platformId
      }),
      timeoutMs: 600000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 微调请求失败"
    };
  }
}

export async function checkTextCompliance(items: ComplianceTextItem[], platformId: CommercePlatformId, productInfo?: ProductInfo | null) {
  try {
    return await requestJson<ComplianceReport>("/api/projects/compliance/check-text", {
      method: "POST",
        body: JSON.stringify({
          items,
          platform_id: platformId,
          product_info: productInfo
        }),
        timeoutMs: 60000
      });
  } catch (error) {
    rethrowMainAppRedirect(error);
      return {
        source: "error",
        summary: { status: "review" as const, block_count: 0, warn_count: 0, review_count: 1 },
        issues: [
          {
            id: "text_compliance_request_failed",
            severity: "review" as const,
            category: "model_review",
            term: "文字合规检查失败",
            reason: error instanceof Error ? error.message : "文字合规检查请求失败",
            suggestion: "请重试文字合规复查，导出前建议人工核对确认信息和图片文案。"
          }
        ]
      };
  }
}

export async function checkImageCompliance(imageUrls: string[], platformId: CommercePlatformId, productInfo?: ProductInfo | null) {
  try {
    return await requestJson<ComplianceReport>("/api/projects/compliance/check-images", {
      method: "POST",
      body: JSON.stringify({
        image_urls: imageUrls,
        platform_id: platformId,
        product_info: productInfo
      }),
      timeoutMs: 180000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      summary: { status: "review" as const, block_count: 0, warn_count: 0, review_count: 1 },
      issues: [
        {
          id: "image_compliance_request_failed",
          severity: "review" as const,
          category: "image_review",
          term: "图片合规检查失败",
          reason: error instanceof Error ? error.message : "图片合规检查请求失败",
          suggestion: "请重试 Gemini 图片合规复查，导出前建议人工核对成图内容。"
        }
      ]
    };
  }
}

type AnalyzeMaterialsResult = {
  source: string;
  product_info?: ProductInfo;
  raw?: string;
  error?: string;
  uploaded_materials?: Array<{ id?: string; slot: string; filename: string; content_type: string; url: string }>;
};

type AnalyzeMaterialsJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
  result?: AnalyzeMaterialsResult;
};

export async function analyzeUploadedMaterials(materials: MaterialPayload[], options: { detailLayoutId?: DetailLayoutId } = {}) {
  try {
    const { job_id: jobId } = await createAnalyzeMaterialsJob(materials, options);
    return await pollAnalyzeMaterialsJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 解析请求失败"
    };
  }
}

export async function createAnalyzeMaterialsJob(materials: MaterialPayload[], options: { detailLayoutId?: DetailLayoutId } = {}) {
  return requestJson<{ job_id: string }>("/api/projects/analyze-materials/jobs", {
    method: "POST",
    body: JSON.stringify({ materials, detail_layout_id: options.detailLayoutId }),
    timeoutMs: 15000
  });
}

export async function fetchAnalyzeMaterialsJob(jobId: string) {
  return requestJson<AnalyzeMaterialsJobStatus>(`/api/projects/analyze-materials/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollAnalyzeMaterialsJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchAnalyzeMaterialsJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("资料解析任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "资料解析任务失败");
    }
    await sleep(3000);
  }
  throw new Error("资料解析任务超时，请稍后重试");
}

type ComposeImageInput = Array<{ module_id: string; module_name: string; url: string }>;
type ComposeJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
};

export async function createComposeLongImageJob(images: ComposeImageInput) {
  return requestJson<{ job_id: string }>("/api/projects/compose-long-image/jobs", {
    method: "POST",
    body: JSON.stringify({ images }),
    timeoutMs: 15000
  });
}

export async function prepareComposeLongImageSources(images: ComposeImageInput) {
  return requestJson<{ images: ComposeImageInput }>("/api/projects/compose-long-image/prepare", {
    method: "POST",
    body: JSON.stringify({ images }),
    timeoutMs: 600000
  });
}

export async function fetchComposeLongImageJob(jobId: string) {
  return requestJson<ComposeJobStatus>(`/api/projects/compose-long-image/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function downloadComposeLongImageJob(jobId: string) {
  return requestBlob(`/api/projects/compose-long-image/jobs/${jobId}/download`, { timeoutMs: 600000 });
}

export async function downloadImage(url: string, filename: string) {
  return requestBlob("/api/projects/download-image", {
    method: "POST",
    body: JSON.stringify({ url, filename }),
    timeoutMs: 600000
  });
}
