import { DETAIL_LAYOUTS } from "@/lib/constants";
import type { DetailLayoutId, ImageGroup, ModuleConfig, StyleReferenceScope, StyleReferenceSelection, UploadedFileInfo } from "@/lib/types";

export const GLOBAL_STYLE_REFERENCE_SCOPE: StyleReferenceScope = { type: "global" };
export const MAX_STYLE_REFERENCE_FILES = 20;
export const MAX_TARGETED_STYLE_REFERENCES_PER_REQUEST = 2;
export const MAX_GLOBAL_STYLE_REFERENCES_WITH_TARGETED = 1;
export const MAX_GLOBAL_STYLE_REFERENCES_WITHOUT_TARGETED = 2;

export type StyleReferenceScopeOption = {
  moduleId: string;
  label: string;
  group: ImageGroup;
};

export type StyleReferenceScopeGroups = {
  detail: StyleReferenceScopeOption[];
  main: StyleReferenceScopeOption[];
  campaign: StyleReferenceScopeOption[];
};

export function normalizeStyleReferenceScopes(scopes?: StyleReferenceScope[]) {
  return scopes?.length ? scopes : [GLOBAL_STYLE_REFERENCE_SCOPE];
}

export function normalizeStyleReferenceFile(file: UploadedFileInfo): UploadedFileInfo {
  return file.slot === "style_reference"
    ? { ...file, styleReferenceScopes: normalizeStyleReferenceScopes(file.styleReferenceScopes) }
    : file;
}

function moduleLabel(module: ModuleConfig) {
  return `第${module.order}屏--${module.name}`;
}

function moduleGroup(module: ModuleConfig): ImageGroup {
  return module.image_group ?? "detail";
}

function optionFor(module: ModuleConfig): StyleReferenceScopeOption {
  return { moduleId: module.id, label: moduleLabel(module), group: moduleGroup(module) };
}

export function buildStyleReferenceScopeOptions(modules: ModuleConfig[], detailLayoutId: DetailLayoutId): StyleReferenceScopeGroups {
  const detailLayout = DETAIL_LAYOUTS.find((layout) => layout.id === detailLayoutId) ?? DETAIL_LAYOUTS[0];
  const sorted = [...modules].sort((a, b) => a.order - b.order);

  return {
    detail: [...detailLayout.modules].sort((a, b) => a.order - b.order).map(optionFor),
    main: sorted.filter((module) => moduleGroup(module) === "main").map(optionFor),
    campaign: sorted.filter((module) => moduleGroup(module) === "campaign").map(optionFor)
  };
}

export function scopeKey(scope: StyleReferenceScope) {
  return scope.type === "global" ? "global" : `module:${scope.moduleId}`;
}

export function hasScope(scopes: StyleReferenceScope[] | undefined, target: StyleReferenceScope) {
  const targetKey = scopeKey(target);
  return normalizeStyleReferenceScopes(scopes).some((scope) => scopeKey(scope) === targetKey);
}

export function toggleStyleReferenceScope(file: UploadedFileInfo, target: StyleReferenceScope): UploadedFileInfo {
  const scopes = normalizeStyleReferenceScopes(file.styleReferenceScopes);
  const targetKey = scopeKey(target);
  const nextScopes = scopes.some((scope) => scopeKey(scope) === targetKey)
    ? scopes.filter((scope) => scopeKey(scope) !== targetKey)
    : [...scopes, target];

  return { ...file, styleReferenceScopes: nextScopes.length ? nextScopes : [GLOBAL_STYLE_REFERENCE_SCOPE] };
}

export function moveStyleReferenceFile<T extends { id: string }>(files: T[], id: string, direction: -1 | 1) {
  const index = files.findIndex((file) => file.id === id);
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || targetIndex >= files.length) return files;

  const next = [...files];
  const [file] = next.splice(index, 1);
  next.splice(targetIndex, 0, file);
  return next;
}

function selectionFor(file: UploadedFileInfo, strength: "global" | "targeted"): StyleReferenceSelection | null {
  if (!file.type.startsWith("image/") || !file.dataUrl) return null;

  return {
    url: file.dataUrl,
    fileId: file.id,
    filename: file.name,
    scopes: normalizeStyleReferenceScopes(file.styleReferenceScopes),
    strength
  };
}

export function selectStyleReferencesForModule(files: UploadedFileInfo[], moduleId: string) {
  const normalizedFiles = files.map(normalizeStyleReferenceFile);
  const targetedSelections = normalizedFiles
    .filter((file) => hasScope(file.styleReferenceScopes, { type: "module", moduleId }))
    .map((file) => selectionFor(file, "targeted"))
    .filter((selection): selection is StyleReferenceSelection => Boolean(selection));
  const selectedTargeted = targetedSelections.slice(0, MAX_TARGETED_STYLE_REFERENCES_PER_REQUEST);
  const globalSelections = normalizedFiles
    .filter((file) => hasScope(file.styleReferenceScopes, GLOBAL_STYLE_REFERENCE_SCOPE))
    .map((file) => selectionFor(file, "global"))
    .filter((selection): selection is StyleReferenceSelection => Boolean(selection));

  const selections = selectedTargeted.length
    ? [
        ...selectedTargeted,
        ...globalSelections
          .filter((selection) => !selectedTargeted.some((targeted) => targeted.fileId === selection.fileId))
          .slice(0, MAX_GLOBAL_STYLE_REFERENCES_WITH_TARGETED)
      ]
    : globalSelections.slice(0, MAX_GLOBAL_STYLE_REFERENCES_WITHOUT_TARGETED);

  return {
    images: selections.map((selection) => selection.url),
    selections
  };
}
