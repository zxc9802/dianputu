import type {
  GeneratedImageVersion,
  GeneratedImageVersionState,
  ModuleConfig,
  ProjectTemplate
} from "@/lib/types";

const MAX_IMAGE_VERSIONS = 3;

type GeneratedImageInput = { module_id: string; url: string };
type ImageGenerationResult = { source: string; images: GeneratedImageInput[]; errors?: string[] };
type ParallelGenerationProgress = { completed: number; total: number; errorCount: number };
type ImageVersionSelection = Record<string, string>;

export function appendImageVersions(
  current: { versions: GeneratedImageVersionState; selectedVersionIds: ImageVersionSelection },
  images: GeneratedImageInput[],
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

export function selectImageVersion(selectedVersionIds: ImageVersionSelection, moduleId: string, versionId: string) {
  return { ...selectedVersionIds, [moduleId]: versionId };
}

export function getSelectedGeneratedImages(versions: GeneratedImageVersionState, selectedVersionIds: ImageVersionSelection) {
  return Object.keys(versions)
    .sort()
    .map((moduleId) => {
      const moduleVersions = versions[moduleId] ?? [];
      const selected = moduleVersions.find((version) => version.id === selectedVersionIds[moduleId]) ?? moduleVersions[moduleVersions.length - 1];
      return selected ? { module_id: moduleId, url: selected.url } : null;
    })
    .filter((image): image is GeneratedImageInput => Boolean(image));
}

export function resolveReusableHistoryId(currentHistoryId: string | null, savedHistoryId: string | null) {
  return currentHistoryId ?? savedHistoryId ?? undefined;
}

export async function runParallelImageGeneration<TModule extends { id: string }>(
  modules: TModule[],
  generateOne: (module: TModule) => Promise<ImageGenerationResult>,
  onComplete: (module: TModule, result: ImageGenerationResult, progress: ParallelGenerationProgress) => void
) {
  let completed = 0;
  let errorCount = 0;
  const total = modules.length;

  await Promise.all(
    modules.map(async (module) => {
      const result = await generateOne(module);
      completed += 1;
      errorCount += result.errors?.length ?? 0;
      onComplete(module, result, { completed, total, errorCount });
    })
  );

  return { completed, total, errorCount };
}

export function applyTemplateToModules(modules: ModuleConfig[], template: ProjectTemplate) {
  const templateById = new Map(template.modules.map((module) => [module.id, module]));
  return modules.map((module) => {
    const templateModule = templateById.get(module.id);
    if (!templateModule) return { ...module, enabled: false };
    return { ...module, enabled: templateModule.enabled, order: templateModule.order };
  });
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
    modules: input.modules.map((module) => ({ id: module.id, enabled: module.enabled, order: module.order }))
  };
}
