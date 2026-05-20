# Targeted Style Reference Images Design

## Goal

Add per-image targeting for benchmark/reference images in the style step so users can upload up to 20 reference images, set each image to affect all outputs or specific screens, and keep each generation request small enough for the image model to follow reliably.

## Current Behavior

The current style step accepts multiple benchmark images through `styleReferenceFiles`. These images are treated as one shared style reference pool. Style analysis uses the uploaded reference images to create an AI custom style, and generation sends a flat `style_reference_images: string[]` list to the backend when the active custom style came from image benchmarking.

There is no stored relationship between a reference image and a specific output module, so the same set of reference images is eligible for every generated image.

## User Experience

In the `图片对标` area, each uploaded reference image becomes a card with:

- Thumbnail preview and filename.
- `上移` and `下移` controls to adjust priority.
- `删除` control.
- A multi-select scope control.

The upload limit increases from 4 to 20 reference images. New images are appended in upload order. The list order is the priority order; earlier images are preferred when selecting references for a generation request.

Each image can select any number of scopes:

- `全局参考`
- `详情图`
- `店铺主图`
- `活动主图`

The category groups expand to concrete screen/module options. The detail group shows only the modules for the currently selected detail layout:

- `detail_evidence_chain_16` shows the 16 evidence-chain detail screens, such as `第一屏--首屏爆点` and `第二屏--痛点放大`.
- `detail_standard_conversion_10` shows the 10 standard conversion detail screens.

Store main-image and campaign-image scopes from their current module lists, for example `店铺主图 > 第一屏--白底图` and `活动主图 > 第一屏--活动白底图`.

An image with `全局参考` affects all generations lightly. An image with a specific screen scope affects that screen strongly. If an image has both global and specific scopes, it is used as a light global reference for all images and a strong reference for the selected screens.

## Data Model

Extend `UploadedFileInfo` with optional style-reference metadata:

```ts
type StyleReferenceScope =
  | { type: "global" }
  | { type: "module"; moduleId: string };

type UploadedFileInfo = {
  id: string;
  slot: UploadSlot;
  name: string;
  size: number;
  type: string;
  lastModified: number;
  dataUrl?: string;
  text?: string;
  styleReferenceScopes?: StyleReferenceScope[];
};
```

Old saved projects may have `styleReferenceFiles` without scopes. During restore, treat those files as `全局参考` so existing projects keep working.

## Reference Selection Rules

Generation still runs one module at a time through the existing parallel generation helper. For each module:

1. Find targeted references whose scopes include `{ type: "module", moduleId }`.
2. Find global references whose scopes include `{ type: "global" }`.
3. Keep original list order.
4. If targeted references exist:
   - Send up to 2 targeted references.
   - Send up to 1 global reference that is not already selected.
5. If no targeted references exist:
   - Send up to 2 global references.
6. Ignore reference entries without an image data URL.

This means a project can store 20 reference images, but a single image generation request gets at most 3 benchmark reference images. Product reference images continue using the existing product image limit.

## API Contract

Keep `style_reference_images: string[]` as the flat image list used by the model so existing backend generation flow remains compatible.

Add optional structured metadata for prompt context and future backend diagnostics:

```ts
type StyleReferenceSelection = {
  url: string;
  fileId?: string;
  filename?: string;
  scopes: StyleReferenceScope[];
  strength: "global" | "targeted";
};
```

Frontend generation requests send:

- `style_reference_images`: the selected URLs for the current module.
- `style_reference_selections`: the selected structured metadata for the current module.

The backend accepts this field as optional. If absent, behavior stays the same.

## Backend Prompt Behavior

When structured selections exist, backend prompt construction should receive whether style references are present and whether any selected references are targeted to the current module.

The prompt should keep the current global style-reference instruction and add a concise current-screen instruction when targeted references are present:

```text
本次上传的对标图中，有图片被指定为当前屏重点参考。优先学习这些图片的构图、信息层级、视觉节奏和版式比例；全局参考图只用于统一色彩、光影和质感，不要照搬其他屏的文案或模块内容。
```

White background modules keep current behavior: they return the product reference image directly and ignore style references.

## Components And Files

Frontend:

- `frontend/lib/types.ts`: add `StyleReferenceScope` and optional `styleReferenceScopes`.
- `frontend/lib/api.ts`: add optional `styleReferenceSelections` to generation calls and payload.
- `frontend/app/page.tsx`: manage scope changes, ordering, restore defaults, and per-module reference selection.
- `frontend/components/StyleStep.tsx`: render reference-image cards with scope multi-select, up/down controls, and deletion.
- `frontend/app/globals.css`: add stable styles for the expanded reference image cards and scope controls.
- `frontend/tests/static-ui-contract.test.cjs` and focused business tests: cover UI contract and reference selection rules.

Backend:

- `backend/app/routers/projects.py`: accept `style_reference_selections` in direct generation and job payloads, pass through to generation.
- `backend/app/services/prompt_builder.py` or router prompt integration: add targeted-reference prompt context.
- `backend/tests/test_api_contracts.py` and/or `backend/tests/test_material_analysis.py`: cover optional metadata and targeted-reference prompt behavior.

## Testing

Add frontend tests for:

- The style step exposes per-image scope controls and up/down controls.
- Detail scope options are derived from the selected detail layout.
- Old `styleReferenceFiles` without scopes restore as global references.
- Per-module selection picks up to 2 targeted references plus 1 global reference.
- Per-module selection picks up to 2 global references when no targeted references exist.
- Selection honors list order.

Add backend tests for:

- Generation request accepts `style_reference_selections`.
- Job payload preserves structured reference metadata.
- Prompt context includes the targeted-reference instruction when current-module targeted references are present.
- Existing flat `style_reference_images` requests continue to work.

## Out Of Scope

- Drag-and-drop sorting. Use upload order plus up/down buttons.
- Sending all 20 reference images to one model call.
- Full visual similarity scoring or automatic reference-to-screen assignment.
- Matrix-style batch assignment UI.

## Open Decisions Resolved

- Maximum uploaded benchmark images: 20.
- Single request benchmark reference limit: at most 3.
- Priority: current list order.
- A reference image may be both global and targeted.
- Detail screen options follow the currently selected detail layout.
