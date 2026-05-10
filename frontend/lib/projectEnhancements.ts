import type {
  ComplianceReport,
  GeneratedImageVersion,
  GeneratedImageVersionState,
  LanguageCode,
  LanguageVersion,
  ModuleConfig,
  ProjectTemplate,
  UploadedFileInfo
} from "@/lib/types";

const MAX_IMAGE_VERSIONS = 3;
const DEFAULT_IMAGE_GENERATION_CONCURRENCY_LIMIT = 2;
const MAX_IMAGE_GENERATION_CONCURRENCY_LIMIT = 20;
const DETAIL_INGREDIENT_BLOCK_IDS = ["ingredient_overview", "ingredient_1", "ingredient_2", "ingredient_3"];

type GeneratedImageInput = { module_id: string; url: string; compliance?: ComplianceReport };
type LayeredGeneratedImageInput = GeneratedImageInput & {
  base_url?: string;
  text_layers?: GeneratedImageVersion["textLayers"];
  language_versions?: GeneratedImageVersion["languageVersions"];
};
type ImageGenerationResult = { source: string; images: LayeredGeneratedImageInput[]; errors?: string[] };
type ParallelGenerationProgress = { completed: number; total: number; errorCount: number; errors: string[] };
type ImageVersionSelection = Record<string, string>;
type UploadedMaterialUrl = { id?: string; slot?: string; filename?: string; content_type?: string; url?: string };

function isRemoteImageUrl(value: string | undefined) {
  return Boolean(value && /^https?:\/\//i.test(value));
}

function errorWithModuleId(moduleId: string, error: string) {
  return error.startsWith(`${moduleId}:`) ? error : `${moduleId}: ${error}`;
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
    const nextVersion: GeneratedImageVersion = {
      id: `${image.module_id}-${now}-${existing.length + 1}`,
      module_id: image.module_id,
      url: image.url,
      ...(image.base_url ? { baseUrl: image.base_url } : {}),
      ...(image.text_layers?.length ? { textLayers: image.text_layers } : {}),
      ...(image.language_versions ? { languageVersions: image.language_versions, selectedLanguage: "zh-CN" as LanguageCode } : {}),
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
  concurrencyLimit = resolveImageGenerationConcurrencyLimit()
) {
  let completed = 0;
  let errorCount = 0;
  const errors: string[] = [];
  const total = modules.length;
  const limit = Math.max(1, Math.min(concurrencyLimit, total || 1));
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < modules.length) {
      const module = modules[nextIndex];
      nextIndex += 1;
      const result = await generateOne(module);
      completed += 1;
      const resultErrors = result.errors ?? [];
      errorCount += resultErrors.length;
      errors.push(...resultErrors.map((error) => errorWithModuleId(module.id, error)));
      onComplete(module, result, { completed, total, errorCount, errors: [...errors] });
    }
  }

  await Promise.all(Array.from({ length: limit }, () => worker()));

  return { completed, total, errorCount, errors };
}

function moduleGroup(module: ModuleConfig) {
  return module.image_group ?? "detail";
}

export function normalizeDetailIngredientModuleOrder(modules: ModuleConfig[]) {
  const indexed = modules.map((module, index) => ({ module, index }));
  const detailEntries = indexed
    .filter((entry) => moduleGroup(entry.module) === "detail")
    .sort((a, b) => a.module.order - b.module.order || a.index - b.index);
  const overviewIndex = detailEntries.findIndex((entry) => entry.module.id === "ingredient_overview");
  if (overviewIndex < 0) return modules;

  const blockEntries = DETAIL_INGREDIENT_BLOCK_IDS
    .map((moduleId) => detailEntries.find((entry) => entry.module.id === moduleId))
    .filter((entry): entry is { module: ModuleConfig; index: number } => Boolean(entry));
  if (blockEntries.length < DETAIL_INGREDIENT_BLOCK_IDS.length) return modules;

  const ingredientBlockIds = new Set(DETAIL_INGREDIENT_BLOCK_IDS);
  const nonBlockEntries = detailEntries.filter((entry) => !ingredientBlockIds.has(entry.module.id));
  const insertIndex = detailEntries
    .slice(0, overviewIndex)
    .filter((entry) => !ingredientBlockIds.has(entry.module.id)).length;
  const orderedDetailEntries = [
    ...nonBlockEntries.slice(0, insertIndex),
    ...blockEntries,
    ...nonBlockEntries.slice(insertIndex)
  ];

  const lastIngredientIndex = orderedDetailEntries.findIndex((entry) => entry.module.id === "ingredient_3");
  const usageIndex = orderedDetailEntries.findIndex((entry) => entry.module.id === "usage");
  if (usageIndex >= 0 && usageIndex < lastIngredientIndex) {
    const [usageEntry] = orderedDetailEntries.splice(usageIndex, 1);
    const nextLastIngredientIndex = orderedDetailEntries.findIndex((entry) => entry.module.id === "ingredient_3");
    orderedDetailEntries.splice(nextLastIngredientIndex + 1, 0, usageEntry);
  }

  const orderById = new Map(
    orderedDetailEntries.map((entry, index) => [entry.module.id, index + 1])
  );
  return modules.map((module) => {
    const normalizedOrder = orderById.get(module.id);
    return normalizedOrder && moduleGroup(module) === "detail" ? { ...module, order: normalizedOrder } : module;
  });
}

export function applyTemplateToModules(modules: ModuleConfig[], template: ProjectTemplate) {
  const templateById = new Map(template.modules.map((module) => [module.id, module]));
  return normalizeDetailIngredientModuleOrder(modules.map((module) => {
    const templateModule = templateById.get(module.id);
    if (!templateModule) return { ...module, enabled: false };
    return { ...module, enabled: templateModule.enabled, order: templateModule.order };
  }));
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
  modules: ModuleConfig[];
}): ProjectTemplate {
  return {
    id: input.id,
    name: input.name,
    category: input.category,
    styleId: input.styleId,
    platformId: input.platformId,
    source: "user",
    modules: normalizeDetailIngredientModuleOrder(input.modules).map((module) => ({ id: module.id, enabled: module.enabled, order: module.order }))
  };
}
