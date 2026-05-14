import type { PublicModelConfig } from "./types";

type ResolveInitialImageModelIdInput = {
  restoredImageModelId?: string;
  modelConfig: PublicModelConfig;
  fallbackImageModelId: string;
  persistedSchemaVersion?: number;
  currentSchemaVersion: number;
};

function normalizeCandidate(value: string | undefined) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function resolveDefaultImageModelId(modelConfig: PublicModelConfig, fallbackImageModelId: string) {
  const optionIds = new Set((modelConfig.imageGeneration.options ?? []).map((option) => option.id));
  const backendDefaultId = normalizeCandidate(modelConfig.imageGeneration.defaultOptionId);
  const fallbackId = normalizeCandidate(fallbackImageModelId);

  if (backendDefaultId && (!optionIds.size || optionIds.has(backendDefaultId))) {
    return backendDefaultId;
  }
  if (fallbackId && (!optionIds.size || optionIds.has(fallbackId))) {
    return fallbackId;
  }
  return modelConfig.imageGeneration.options?.[0]?.id ?? (fallbackId || backendDefaultId);
}

export function resolveInitialImageModelId({
  restoredImageModelId,
  modelConfig,
  fallbackImageModelId,
  persistedSchemaVersion,
  currentSchemaVersion,
}: ResolveInitialImageModelIdInput) {
  const optionIds = new Set((modelConfig.imageGeneration.options ?? []).map((option) => option.id));
  const defaultImageModelId = resolveDefaultImageModelId(modelConfig, fallbackImageModelId);
  const restoredId = normalizeCandidate(restoredImageModelId);
  const restoredStateIsCurrent = persistedSchemaVersion === currentSchemaVersion;

  if (restoredStateIsCurrent && restoredId && (!optionIds.size || optionIds.has(restoredId))) {
    return restoredId;
  }
  return defaultImageModelId;
}
