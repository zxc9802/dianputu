import type {
  ComplianceReport,
  DetailLayoutId,
  GeneratedImageVersion,
  GeneratedImageVersionState,
  LanguageCode,
  LanguageVersion,
  ModuleConfig,
  ProjectTemplate,
  UploadedFileInfo
} from "@/lib/types";
import { DEFAULT_DETAIL_LAYOUT_ID, DETAIL_LAYOUTS } from "@/lib/constants";

const MAX_IMAGE_VERSIONS = 3;
const DEFAULT_IMAGE_GENERATION_CONCURRENCY_LIMIT = 2;
const MAX_IMAGE_GENERATION_CONCURRENCY_LIMIT = 20;
const DEFAULT_IMAGE_GENERATION_RETRY_ATTEMPTS = 2;
const DEFAULT_IMAGE_GENERATION_RETRY_DELAYS_MS = [3000, 8000];
const DEFAULT_IMAGE_GENERATION_RETRY_JITTER_MS = 1000;
const STANDARD_DETAIL_LAYOUT_ID: DetailLayoutId = "detail_standard_conversion_10";

type GeneratedImageInput = { module_id: string; url: string; compliance?: ComplianceReport };
type DetailDownloadItem = { module: ModuleConfig; url: string };
type LayeredGeneratedImageInput = GeneratedImageInput & {
  base_url?: string;
  text_layers?: GeneratedImageVersion["textLayers"];
  language_versions?: GeneratedImageVersion["languageVersions"];
};
type ImageGenerationResult = { source: string; images: LayeredGeneratedImageInput[]; errors?: string[] };
type ParallelGenerationProgress = { completed: number; total: number; errorCount: number; errors: string[] };
type ParallelGenerationRetryCallback<TModule> = (
  module: TModule,
  attempt: number,
  retryAttempts: number,
  delayMs: number,
  errors: string[]
) => void;
type ParallelGenerationOptions<TModule> = {
  concurrencyLimit?: number;
  retryAttempts?: number;
  retryDelaysMs?: number[];
  retryJitterMs?: number;
  wait?: (delayMs: number) => Promise<void>;
  onRetry?: ParallelGenerationRetryCallback<TModule>;
};
type ImageVersionSelection = Record<string, string>;
type UploadedMaterialUrl = { id?: string; slot?: string; filename?: string; content_type?: string; url?: string };

function isRemoteImageUrl(value: string | undefined) {
  return Boolean(value && /^https?:\/\//i.test(value));
}

function errorWithModuleId(moduleId: string, error: string) {
  return error.startsWith(`${moduleId}:`) ? error : `${moduleId}: ${error}`;
}

export function isRetryableImageGenerationError(error: string) {
  const normalized = error.toLowerCase();
  return [
    "server disconnected",
    "disconnected without sending a response",
    "timeout",
    "timed out",
    "network error",
    "networkerror",
    "fetch failed",
    "socket hang up",
    "econnreset",
    "rate limit",
    "too many requests",
    "429",
    "502",
    "503",
    "504"
  ].some((keyword) => normalized.includes(keyword));
}

function isRetryableImageGenerationFailure(result: ImageGenerationResult) {
  const resultErrors = result.errors ?? [];
  return result.images.length === 0 && resultErrors.some(isRetryableImageGenerationError);
}

function defaultRetryWait(delayMs: number) {
  if (delayMs <= 0) return Promise.resolve();
  return new Promise<void>((resolve) => globalThis.setTimeout(resolve, delayMs));
}

function resolveParallelGenerationOptions<TModule>(
  optionsOrConcurrencyLimit?: number | ParallelGenerationOptions<TModule>
): Required<ParallelGenerationOptions<TModule>> {
  const options = typeof optionsOrConcurrencyLimit === "number" ? { concurrencyLimit: optionsOrConcurrencyLimit } : optionsOrConcurrencyLimit ?? {};
  return {
    concurrencyLimit: options.concurrencyLimit ?? resolveImageGenerationConcurrencyLimit(),
    retryAttempts: Math.max(0, options.retryAttempts ?? DEFAULT_IMAGE_GENERATION_RETRY_ATTEMPTS),
    retryDelaysMs: options.retryDelaysMs?.length ? options.retryDelaysMs : DEFAULT_IMAGE_GENERATION_RETRY_DELAYS_MS,
    retryJitterMs: Math.max(0, options.retryJitterMs ?? DEFAULT_IMAGE_GENERATION_RETRY_JITTER_MS),
    wait: options.wait ?? defaultRetryWait,
    onRetry: options.onRetry ?? (() => {})
  };
}

function retryDelayForAttempt(attempt: number, retryDelaysMs: number[], retryJitterMs: number) {
  const baseDelay = retryDelaysMs[Math.min(attempt - 1, retryDelaysMs.length - 1)] ?? 0;
  const jitter = retryJitterMs > 0 ? Math.floor(Math.random() * retryJitterMs) : 0;
  return baseDelay + jitter;
}

export function formatImageGenerationSummaryStatus(
  groupLabel: string,
  summary: { completed: number; total: number; errorCount: number; errors?: string[] }
) {
  const firstError = summary.errors?.[0];
  if (summary.completed === summary.errorCount) {
    return firstError ? `${groupLabel}生成失败：${firstError}` : `${groupLabel}生成失败，请查看后端日志`;
  }
  if (summary.errorCount) {
    return firstError ? `${groupLabel}部分生成失败：${summary.errorCount}/${summary.total}，${firstError}` : `${groupLabel}部分生成失败：${summary.errorCount}/${summary.total}`;
  }
  return `${groupLabel}已生成`;
}

export function appendImageVersions(
  current: { versions: GeneratedImageVersionState; selectedVersionIds: ImageVersionSelection },
  images: LayeredGeneratedImageInput[],
  source: string,
  now = Date.now(),
  editInstruction = ""
) {
  const versions: GeneratedImageVersionState = { ...current.versions };
  const selectedVersionIds: ImageVersionSelection = { ...current.selectedVersionIds };

  images.forEach((image) => {
    const existing = versions[image.module_id] ?? [];
    const languageVersionKeys = Object.keys(image.language_versions ?? {}) as LanguageCode[];
    const selectedLanguage = languageVersionKeys.includes("zh-CN" as LanguageCode) ? "zh-CN" as LanguageCode : languageVersionKeys[0];
    const nextVersion: GeneratedImageVersion = {
      id: `${image.module_id}-${now}-${existing.length + 1}`,
      module_id: image.module_id,
      url: image.url,
      ...(image.base_url ? { baseUrl: image.base_url } : {}),
      ...(image.text_layers?.length ? { textLayers: image.text_layers } : {}),
      ...(image.language_versions ? { languageVersions: image.language_versions, ...(selectedLanguage ? { selectedLanguage } : {}) } : {}),
      ...(image.compliance ? { compliance: image.compliance } : {}),
      label: `v${existing.length + 1}`,
      source,
      createdAt: now,
      ...(editInstruction ? { editInstruction } : {})
    };
    const retained = [...existing, nextVersion].slice(-MAX_IMAGE_VERSIONS).map((version, index) => ({
      ...version,
      label: `v${index + 1}`
    }));
    versions[image.module_id] = retained;
    selectedVersionIds[image.module_id] = retained[retained.length - 1]?.id ?? nextVersion.id;
  });

  return { versions, selectedVersionIds };
}

export function replaceUploadedFileDataUrlsWithMaterialUrls(uploadedFiles: UploadedFileInfo[], uploadedMaterials: UploadedMaterialUrl[] = []) {
  if (!uploadedMaterials.length) return uploadedFiles;
  return uploadedFiles.map((file) => {
    const replacement = uploadedMaterials.find((material) => {
      if (!isRemoteImageUrl(material.url)) return false;
      if (material.id && material.id === file.id) return true;
      return material.slot === file.slot && material.filename === file.name && material.content_type === file.type;
    });
    return replacement?.url ? { ...file, dataUrl: replacement.url } : file;
  });
}

export function selectImageVersion(selectedVersionIds: ImageVersionSelection, moduleId: string, versionId: string) {
  return { ...selectedVersionIds, [moduleId]: versionId };
}

export function getSelectedGeneratedImages(versions: GeneratedImageVersionState, selectedVersionIds: ImageVersionSelection) {
  return Object.keys(versions)
    .sort()
    .map((moduleId) => {
      const moduleVersions = versions[moduleId] ?? [];
      const selected = moduleVersions.find((version) => version.id === selectedVersionIds[moduleId]) ?? moduleVersions[moduleVersions.length - 1];
      if (!selected) return null;
      const languageUrl = selected.selectedLanguage ? selected.languageVersions?.[selected.selectedLanguage]?.url : "";
      return { module_id: moduleId, url: languageUrl || selected.url };
    })
    .filter((image): image is GeneratedImageInput => Boolean(image));
}

export function selectLanguageVersion(
  current: { versions: GeneratedImageVersionState; selectedVersionIds: ImageVersionSelection },
  moduleId: string,
  versionId: string,
  language: LanguageCode
) {
  return {
    ...current,
    versions: {
      ...current.versions,
      [moduleId]: (current.versions[moduleId] ?? []).map((version) =>
        version.id === versionId ? { ...version, selectedLanguage: language } : version
      )
    },
    selectedVersionIds: selectImageVersion(current.selectedVersionIds, moduleId, versionId)
  };
}

export function addLanguageVersion(
  current: { versions: GeneratedImageVersionState; selectedVersionIds: ImageVersionSelection },
  moduleId: string,
  versionId: string,
  languageVersion: LanguageVersion,
  now = Date.now()
) {
  return {
    ...current,
    versions: {
      ...current.versions,
      [moduleId]: (current.versions[moduleId] ?? []).map((version) =>
        version.id === versionId
          ? {
              ...version,
              languageVersions: {
                ...(version.languageVersions ?? {}),
                [languageVersion.language]: { ...languageVersion, createdAt: languageVersion.createdAt ?? now }
              },
              selectedLanguage: languageVersion.language
            }
          : version
      )
    },
    selectedVersionIds: selectImageVersion(current.selectedVersionIds, moduleId, versionId)
  };
}

export function resolveReusableHistoryId(currentHistoryId: string | null, savedHistoryId: string | null) {
  return currentHistoryId ?? savedHistoryId ?? undefined;
}

export function resolveHistoryIdAfterSave(
  currentHistoryId: string | null,
  savedHistoryId: string | null,
  options: { trackSavedHistoryId?: boolean } = {}
) {
  if (options.trackSavedHistoryId === false) {
    return currentHistoryId;
  }
  return resolveReusableHistoryId(currentHistoryId, savedHistoryId) ?? null;
}

export function resolveImageGenerationConcurrencyLimit(
  rawValue = process.env.NEXT_PUBLIC_IMAGE_GENERATION_CONCURRENCY
) {
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return DEFAULT_IMAGE_GENERATION_CONCURRENCY_LIMIT;
  }
  return Math.min(parsed, MAX_IMAGE_GENERATION_CONCURRENCY_LIMIT);
}

export async function runParallelImageGeneration<TModule extends { id: string }>(
  modules: TModule[],
  generateOne: (module: TModule) => Promise<ImageGenerationResult>,
  onComplete: (module: TModule, result: ImageGenerationResult, progress: ParallelGenerationProgress) => void,
  optionsOrConcurrencyLimit?: number | ParallelGenerationOptions<TModule>
) {
  const options = resolveParallelGenerationOptions(optionsOrConcurrencyLimit);
  let completed = 0;
  let errorCount = 0;
  const errors: string[] = [];
  const retryQueue: Array<{ module: TModule; result: ImageGenerationResult }> = [];
  const total = modules.length;
  const limit = Math.max(1, Math.min(options.concurrencyLimit, total || 1));
  let nextIndex = 0;

  function complete(module: TModule, result: ImageGenerationResult) {
    completed += 1;
    const resultErrors = result.errors ?? [];
    errorCount += resultErrors.length;
    errors.push(...resultErrors.map((error) => errorWithModuleId(module.id, error)));
    onComplete(module, result, { completed, total, errorCount, errors: [...errors] });
  }

  async function worker() {
    while (nextIndex < modules.length) {
      const module = modules[nextIndex];
      nextIndex += 1;
      const result = await generateOne(module);
      if (options.retryAttempts > 0 && isRetryableImageGenerationFailure(result)) {
        retryQueue.push({ module, result });
      } else {
        complete(module, result);
      }
    }
  }

  await Promise.all(Array.from({ length: limit }, () => worker()));

  for (const retryItem of retryQueue) {
    let result = retryItem.result;
    for (let attempt = 1; attempt <= options.retryAttempts; attempt += 1) {
      const delayMs = retryDelayForAttempt(attempt, options.retryDelaysMs, options.retryJitterMs);
      options.onRetry(retryItem.module, attempt, options.retryAttempts, delayMs, result.errors ?? []);
      await options.wait(delayMs);
      result = await generateOne(retryItem.module);
      if (!isRetryableImageGenerationFailure(result)) break;
    }
    complete(retryItem.module, result);
  }

  return { completed, total, errorCount, errors };
}

function moduleGroup(module: ModuleConfig) {
  return module.image_group ?? "detail";
}

function resolveDetailLayoutId(layoutId?: string | null): DetailLayoutId {
  return DETAIL_LAYOUTS.some((layout) => layout.id === layoutId) ? layoutId as DetailLayoutId : DEFAULT_DETAIL_LAYOUT_ID;
}

function detailLayoutById(layoutId?: string | null) {
  const resolvedId = resolveDetailLayoutId(layoutId);
  return DETAIL_LAYOUTS.find((layout) => layout.id === resolvedId) ?? DETAIL_LAYOUTS[0];
}

export function detailLayoutModules(layoutId?: string | null) {
  return detailLayoutById(layoutId).modules.map((module) => ({ ...module }));
}

export function inferDetailLayoutIdFromModules(modules: Array<Pick<ModuleConfig, "id"> & Partial<ModuleConfig>> = []): DetailLayoutId {
  const detailIds = new Set(modules.filter((module) => moduleGroup(module as ModuleConfig) === "detail").map((module) => module.id));
  const standardIds = new Set(detailLayoutModules(STANDARD_DETAIL_LAYOUT_ID).map((module) => module.id));
  const evidenceIds = new Set(detailLayoutModules(DEFAULT_DETAIL_LAYOUT_ID).map((module) => module.id));
  if ([...standardIds].some((id) => detailIds.has(id))) return STANDARD_DETAIL_LAYOUT_ID;
  if ([...evidenceIds].some((id) => detailIds.has(id))) return DEFAULT_DETAIL_LAYOUT_ID;
  return DEFAULT_DETAIL_LAYOUT_ID;
}

export function normalizeDetailModuleOrder(modules: ModuleConfig[], layoutId?: string | null) {
  const resolvedLayoutId = resolveDetailLayoutId(layoutId ?? inferDetailLayoutIdFromModules(modules));
  const detailOrder = new Map(detailLayoutModules(resolvedLayoutId).map((module, index) => [module.id, index + 1]));
  const detailEntries = modules
    .map((module, index) => ({ module, index }))
    .filter((entry) => moduleGroup(entry.module) === "detail")
    .sort((a, b) => a.module.order - b.module.order || a.index - b.index);
  if (!detailEntries.some((entry) => detailOrder.has(entry.module.id))) return modules;
  const fallbackStart = detailOrder.size + 1;
  const orderById = new Map(
    detailEntries.map((entry, index) => [entry.module.id, detailOrder.get(entry.module.id) ?? fallbackStart + index])
  );
  return modules.map((module) => {
    const normalizedOrder = orderById.get(module.id);
    return normalizedOrder && moduleGroup(module) === "detail" ? { ...module, order: normalizedOrder } : module;
  });
}

export function normalizeDetailIngredientModuleOrder(modules: ModuleConfig[]) {
  return normalizeDetailModuleOrder(modules, STANDARD_DETAIL_LAYOUT_ID);
}

export function applyDetailLayoutToModules(modules: ModuleConfig[], layoutId?: string | null) {
  const detailModules = detailLayoutModules(layoutId);
  const currentById = new Map(modules.filter((module) => moduleGroup(module) === "detail").map((module) => [module.id, module]));
  return [
    ...modules.filter((module) => moduleGroup(module) !== "detail").map((module) => ({ ...module })),
    ...detailModules.map((module) => {
      const current = currentById.get(module.id);
      return { ...module, enabled: current?.enabled ?? module.enabled };
    })
  ];
}

export function buildDetailDownloadState(modules: ModuleConfig[], generatedImages: GeneratedImageInput[]) {
  const generatedByModule = new Map(
    generatedImages
      .filter((image) => Boolean(image.url))
      .map((image) => [image.module_id, image.url])
  );
  const detailModules = normalizeDetailModuleOrder(modules)
    .filter((module) => moduleGroup(module) === "detail" && module.enabled)
    .sort((a, b) => a.order - b.order);
  const items = detailModules
    .map((module) => {
      const url = generatedByModule.get(module.id);
      return url ? { module, url } : null;
    })
    .filter((item): item is DetailDownloadItem => Boolean(item));
  const missingModules = detailModules.filter((module) => !generatedByModule.get(module.id));
  const manifest = items.map((item) => ({
    module_id: item.module.id,
    module_name: item.module.name,
    url: item.url
  }));

  return { modules: detailModules, items, missingModules, manifest };
}

export function applyTemplateToModules(modules: ModuleConfig[], template: ProjectTemplate) {
  const templateById = new Map(template.modules.map((module) => [module.id, module]));
  const layoutId = template.detailLayoutId ?? inferDetailLayoutIdFromModules(template.modules as ModuleConfig[]);
  const layoutModules = applyDetailLayoutToModules(modules, layoutId);
  return normalizeDetailModuleOrder(layoutModules.map((module) => {
    const templateModule = templateById.get(module.id);
    if (!templateModule) return { ...module, enabled: false };
    return { ...module, enabled: templateModule.enabled, order: templateModule.order };
  }), layoutId);
}

export function enableModuleForSingleGeneration(modules: ModuleConfig[], moduleId: string) {
  let changed = false;
  const nextModules = modules.map((module) => {
    if (module.id !== moduleId || module.enabled) return module;
    changed = true;
    return { ...module, enabled: true };
  });

  return changed ? nextModules : modules;
}

export function createTemplateFromProject(input: {
  id: string;
  name: string;
  category: string;
  styleId: string;
  platformId: ProjectTemplate["platformId"];
  detailLayoutId?: DetailLayoutId;
  modules: ModuleConfig[];
}): ProjectTemplate {
  const detailLayoutId = input.detailLayoutId ?? inferDetailLayoutIdFromModules(input.modules);
  return {
    id: input.id,
    name: input.name,
    category: input.category,
    styleId: input.styleId,
    platformId: input.platformId,
    detailLayoutId,
    source: "user",
    modules: normalizeDetailModuleOrder(input.modules, detailLayoutId).map((module) => ({ id: module.id, enabled: module.enabled, order: module.order }))
  };
}
