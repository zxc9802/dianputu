import { STYLE_OPTIONS } from "./constants";
import type {
  BrandColorRecommendation,
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
type Rgb = { r: number; g: number; b: number };

function padHex(value: number) {
  return Math.max(0, Math.min(255, Math.round(value))).toString(16).padStart(2, "0").toUpperCase();
}

function hexToRgb(hex: string): Rgb | null {
  const normalized = hex.replace("#", "").trim();
  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) return null;
  return {
    r: parseInt(normalized.slice(0, 2), 16),
    g: parseInt(normalized.slice(2, 4), 16),
    b: parseInt(normalized.slice(4, 6), 16)
  };
}

function colorDistance(leftHex: string, rightHex: string) {
  const left = hexToRgb(leftHex);
  const right = hexToRgb(rightHex);
  if (!left || !right) return Number.POSITIVE_INFINITY;
  const redMean = (left.r + right.r) / 2;
  const red = left.r - right.r;
  const green = left.g - right.g;
  const blue = left.b - right.b;
  return Math.sqrt((2 + redMean / 256) * red * red + 4 * green * green + (2 + (255 - redMean) / 256) * blue * blue);
}

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

export function extractDominantColorsFromRgba(rgba: ArrayLike<number>, maxColors = 3) {
  const buckets = new Map<string, { count: number; r: number; g: number; b: number }>();
  for (let index = 0; index < rgba.length; index += 4) {
    const alpha = rgba[index + 3] ?? 255;
    const r = rgba[index] ?? 0;
    const g = rgba[index + 1] ?? 0;
    const b = rgba[index + 2] ?? 0;
    if (alpha < 180) continue;
    if (r > 238 && g > 238 && b > 238) continue;
    if (r < 18 && g < 18 && b < 18) continue;
    const key = `${Math.round(r / 16)}-${Math.round(g / 16)}-${Math.round(b / 16)}`;
    const bucket = buckets.get(key) ?? { count: 0, r: 0, g: 0, b: 0 };
    bucket.count += 1;
    bucket.r += r;
    bucket.g += g;
    bucket.b += b;
    buckets.set(key, bucket);
  }

  return Array.from(buckets.values())
    .sort((left, right) => right.count - left.count)
    .slice(0, maxColors)
    .map((bucket) => `#${padHex(bucket.r / bucket.count)}${padHex(bucket.g / bucket.count)}${padHex(bucket.b / bucket.count)}`);
}

export function recommendStyleFromBrandColors(colors: string[]): BrandColorRecommendation | null {
  if (!colors.length) return null;
  let best: BrandColorRecommendation | null = null;
  STYLE_OPTIONS.forEach((style) => {
    const distance = Math.min(...colors.map((color) => colorDistance(color, style.primary_color)));
    if (!best || distance < best.distance) {
      best = { styleId: style.id, distance };
    }
  });
  return best;
}
