# Targeted Style Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users upload up to 20 benchmark images, bind each image to global and/or specific output screens, and send only the most relevant references for each generated screen.

**Architecture:** Add typed style-reference scopes to uploaded file state, isolate per-module selection logic in a small frontend helper, render scope controls in `StyleStep`, and extend the generation API with optional structured metadata. Backend remains compatible with the flat `style_reference_images` list while using optional selection metadata to add targeted-reference prompt guidance.

**Tech Stack:** Next.js App Router, React, TypeScript, Node static tests, FastAPI/Pydantic, Python unittest/pytest.

---

## File Structure

- Create `frontend/lib/styleReferenceTargeting.ts`: pure helper functions for default scopes, module scope options, ordering, and per-module selected references.
- Modify `frontend/lib/types.ts`: add `StyleReferenceScope` and `StyleReferenceSelection`, extend `UploadedFileInfo`.
- Modify `frontend/tests/project-enhancements.test.cjs`: load and assert helper behavior.
- Modify `frontend/tests/static-ui-contract.test.cjs`: assert the UI and API contract strings exist.
- Modify `frontend/components/StyleStep.tsx`: render 20-card reference library, up/down controls, and grouped multi-select scopes.
- Modify `frontend/app/page.tsx`: preserve scopes, reorder references, pass scope options, and select per-module references at generation time.
- Modify `frontend/lib/api.ts`: accept and send optional `style_reference_selections`.
- Modify `frontend/app/globals.css`: style the card list and scope controls.
- Modify `backend/app/services/prompt_builder.py`: accept `has_targeted_style_reference` and add the current-screen prompt instruction.
- Modify `backend/app/routers/projects.py`: accept `style_reference_selections`, pass it through jobs, detect targeted references for each module, and keep existing flat-image behavior.
- Modify `backend/tests/test_prompt_builder.py` and `backend/tests/test_material_analysis.py`: assert targeted prompt behavior and generation contract.

### Task 1: Frontend Targeting Helper

**Files:**
- Create: `frontend/lib/styleReferenceTargeting.ts`
- Modify: `frontend/lib/types.ts`
- Test: `frontend/tests/project-enhancements.test.cjs`

- [ ] **Step 1: Write failing helper tests**

Append a TypeScript transpile block to `frontend/tests/project-enhancements.test.cjs` that loads `lib/styleReferenceTargeting.ts` and asserts:

```js
const targetingPath = path.join(root, "lib", "styleReferenceTargeting.ts");
const targetingSource = fs.readFileSync(targetingPath, "utf8");
const compiledTargeting = ts.transpileModule(targetingSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2019, esModuleInterop: true }
}).outputText;
const targetingSandbox = {
  exports: {},
  module: { exports: {} },
  require(request) {
    if (request === "@/lib/types" || request === "./types") return {};
    if (request === "@/lib/constants" || request === "./constants") return constantsSandbox.module.exports;
    throw new Error(`Unexpected require: ${request}`);
  }
};
targetingSandbox.exports = targetingSandbox.module.exports;
vm.runInNewContext(compiledTargeting, targetingSandbox, { filename: targetingPath });
const {
  GLOBAL_STYLE_REFERENCE_SCOPE,
  normalizeStyleReferenceScopes,
  buildStyleReferenceScopeOptions,
  moveStyleReferenceFile,
  selectStyleReferencesForModule
} = targetingSandbox.module.exports;

assert.deepEqual(normalizeStyleReferenceScopes(undefined), [GLOBAL_STYLE_REFERENCE_SCOPE]);
assert.equal(buildStyleReferenceScopeOptions(DEFAULT_MODULES, "detail_evidence_chain_16").detail[0].moduleId, "detail_ec_hero");
assert.equal(buildStyleReferenceScopeOptions(DEFAULT_MODULES, "detail_standard_conversion_10").detail[0].moduleId, "hero");
assert.deepEqual(moveStyleReferenceFile([{ id: "a" }, { id: "b" }, { id: "c" }], "c", -1).map((item) => item.id), ["a", "c", "b"]);

const refFiles = [
  { id: "t1", name: "target one", slot: "style_reference", type: "image/png", dataUrl: "target-1", styleReferenceScopes: [{ type: "module", moduleId: "detail_ec_hero" }] },
  { id: "g1", name: "global one", slot: "style_reference", type: "image/png", dataUrl: "global-1", styleReferenceScopes: [{ type: "global" }] },
  { id: "t2", name: "target two", slot: "style_reference", type: "image/png", dataUrl: "target-2", styleReferenceScopes: [{ type: "module", moduleId: "detail_ec_hero" }] },
  { id: "t3", name: "target three", slot: "style_reference", type: "image/png", dataUrl: "target-3", styleReferenceScopes: [{ type: "module", moduleId: "detail_ec_hero" }] },
  { id: "g2", name: "global two", slot: "style_reference", type: "image/png", dataUrl: "global-2", styleReferenceScopes: [{ type: "global" }] }
];
assert.deepEqual(selectStyleReferencesForModule(refFiles, "detail_ec_hero").images, ["target-1", "target-2", "global-1"]);
assert.deepEqual(selectStyleReferencesForModule(refFiles, "detail_ec_usage").images, ["global-1", "global-2"]);
```

- [ ] **Step 2: Run helper test and verify RED**

Run: `npm.cmd run test` from `frontend`.

Expected: fails because `frontend/lib/styleReferenceTargeting.ts` does not exist or exports are missing.

- [ ] **Step 3: Implement helper and types**

Add these exports to `frontend/lib/types.ts`:

```ts
export type StyleReferenceScope = { type: "global" } | { type: "module"; moduleId: string };

export type StyleReferenceSelection = {
  url: string;
  fileId?: string;
  filename?: string;
  scopes: StyleReferenceScope[];
  strength: "global" | "targeted";
};
```

Extend `UploadedFileInfo` with:

```ts
styleReferenceScopes?: StyleReferenceScope[];
```

Create `frontend/lib/styleReferenceTargeting.ts` with pure functions:

```ts
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
  return file.slot === "style_reference" ? { ...file, styleReferenceScopes: normalizeStyleReferenceScopes(file.styleReferenceScopes) } : file;
}

function moduleLabel(module: ModuleConfig) {
  return `第${module.order}屏--${module.name}`;
}

export function buildStyleReferenceScopeOptions(modules: ModuleConfig[], detailLayoutId: DetailLayoutId): StyleReferenceScopeGroups {
  const detailIds = new Set((DETAIL_LAYOUTS.find((layout) => layout.id === detailLayoutId) ?? DETAIL_LAYOUTS[0]).modules.map((module) => module.id));
  const optionFor = (module: ModuleConfig) => ({ moduleId: module.id, label: moduleLabel(module), group: module.image_group ?? "detail" as ImageGroup });
  return {
    detail: modules.filter((module) => (module.image_group ?? "detail") === "detail" && detailIds.has(module.id)).sort((a, b) => a.order - b.order).map(optionFor),
    main: modules.filter((module) => module.image_group === "main").sort((a, b) => a.order - b.order).map(optionFor),
    campaign: modules.filter((module) => module.image_group === "campaign").sort((a, b) => a.order - b.order).map(optionFor)
  };
}

export function scopeKey(scope: StyleReferenceScope) {
  return scope.type === "global" ? "global" : `module:${scope.moduleId}`;
}

export function hasScope(scopes: StyleReferenceScope[] | undefined, target: StyleReferenceScope) {
  const key = scopeKey(target);
  return normalizeStyleReferenceScopes(scopes).some((scope) => scopeKey(scope) === key);
}

export function toggleStyleReferenceScope(file: UploadedFileInfo, target: StyleReferenceScope): UploadedFileInfo {
  const scopes = normalizeStyleReferenceScopes(file.styleReferenceScopes);
  const targetKey = scopeKey(target);
  const next = scopes.some((scope) => scopeKey(scope) === targetKey)
    ? scopes.filter((scope) => scopeKey(scope) !== targetKey)
    : [...scopes, target];
  return { ...file, styleReferenceScopes: next.length ? next : [GLOBAL_STYLE_REFERENCE_SCOPE] };
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
  const normalized = files.map(normalizeStyleReferenceFile);
  const targeted = normalized
    .filter((file) => hasScope(file.styleReferenceScopes, { type: "module", moduleId }))
    .map((file) => selectionFor(file, "targeted"))
    .filter((selection): selection is StyleReferenceSelection => Boolean(selection));
  const global = normalized
    .filter((file) => hasScope(file.styleReferenceScopes, GLOBAL_STYLE_REFERENCE_SCOPE))
    .map((file) => selectionFor(file, "global"))
    .filter((selection): selection is StyleReferenceSelection => Boolean(selection));
  const selected = targeted.length
    ? [
        ...targeted.slice(0, MAX_TARGETED_STYLE_REFERENCES_PER_REQUEST),
        ...global.filter((item) => !targeted.slice(0, MAX_TARGETED_STYLE_REFERENCES_PER_REQUEST).some((selectedItem) => selectedItem.fileId === item.fileId)).slice(0, MAX_GLOBAL_STYLE_REFERENCES_WITH_TARGETED)
      ]
    : global.slice(0, MAX_GLOBAL_STYLE_REFERENCES_WITHOUT_TARGETED);
  return { images: selected.map((item) => item.url), selections: selected };
}
```

- [ ] **Step 4: Run helper test and verify GREEN**

Run: `npm.cmd run test` from `frontend`.

Expected: all existing frontend tests pass.

### Task 2: Frontend UI And Page Wiring

**Files:**
- Modify: `frontend/components/StyleStep.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/globals.css`
- Test: `frontend/tests/static-ui-contract.test.cjs`

- [ ] **Step 1: Write failing UI/API contract tests**

Append static assertions to `frontend/tests/static-ui-contract.test.cjs`:

```js
assertIncludes("components/StyleStep.tsx", "styleReferenceScopeGroups", "style step must receive grouped style reference scope options");
assertIncludes("components/StyleStep.tsx", "onStyleReferenceScopeToggle", "style step must let each reference image toggle scopes");
assertIncludes("components/StyleStep.tsx", "onStyleReferenceMove", "style step must expose up/down priority controls");
assertIncludes("components/StyleStep.tsx", "全局参考", "style reference controls must include global scope");
assertIncludes("components/StyleStep.tsx", "详情图", "style reference controls must include detail image scope group");
assertIncludes("components/StyleStep.tsx", "店铺主图", "style reference controls must include main image scope group");
assertIncludes("components/StyleStep.tsx", "活动主图", "style reference controls must include campaign image scope group");
assertIncludes("app/page.tsx", "MAX_STYLE_REFERENCE_FILES", "page must cap benchmark reference uploads at 20");
assertIncludes("app/page.tsx", "selectStyleReferencesForModule", "generation must select per-module benchmark references");
assertIncludes("lib/api.ts", "style_reference_selections", "frontend generation API must send structured selected style references");
```

- [ ] **Step 2: Run static test and verify RED**

Run: `npm.cmd run test:static` from `frontend`.

Expected: fails on missing new strings.

- [ ] **Step 3: Wire page state and API**

In `frontend/app/page.tsx`:

- Import `MAX_STYLE_REFERENCE_FILES`, `buildStyleReferenceScopeOptions`, `moveStyleReferenceFile`, `normalizeStyleReferenceFile`, `selectStyleReferencesForModule`, `toggleStyleReferenceScope`.
- Normalize restored `styleReferenceFiles` with `normalizeStyleReferenceFile`.
- Change upload cap from `.slice(-4)` to `.slice(-MAX_STYLE_REFERENCE_FILES)` and initialize new files with global scope.
- Add handlers:

```ts
function toggleStyleReferenceFileScope(fileId: string, scope: StyleReferenceScope) {
  setStyleReferenceFiles((current) => current.map((file) => file.id === fileId ? toggleStyleReferenceScope(file, scope) : file));
}

function moveStyleReference(fileId: string, direction: -1 | 1) {
  setStyleReferenceFiles((current) => moveStyleReferenceFile(current, fileId, direction));
}
```

- Replace `styleReferenceImages()` use in generation with `selectStyleReferencesForModule(styleReferenceFiles, module.id)` and pass both `images` and `selections`.

In `frontend/lib/api.ts`:

- Import `StyleReferenceSelection`.
- Add an optional `styleReferenceSelections: StyleReferenceSelection[] = []` parameter after `styleReferenceImages`.
- Send `style_reference_selections: styleReferenceSelections` in `createGenerateImageJob`.

- [ ] **Step 4: Render UI controls**

In `frontend/components/StyleStep.tsx`:

- Add props `styleReferenceScopeGroups`, `onStyleReferenceScopeToggle`, `onStyleReferenceMove`.
- Render each reference card with thumbnail, filename, delete, up/down buttons, and checkbox groups.
- Use `scopeKey`/`hasScope` from the helper to mark selected scopes.
- Disable up/down buttons at list boundaries.

Add CSS classes in `frontend/app/globals.css`: `.styleReferenceList`, `.styleReferenceCard`, `.styleReferenceCardPreview`, `.styleReferenceCardActions`, `.styleReferenceScopes`, `.styleReferenceScopeGroup`, `.styleReferenceScopeOption`.

- [ ] **Step 5: Run frontend tests and build**

Run from `frontend`:

```powershell
npm.cmd run test
npm.cmd run build
```

Expected: tests and build pass.

### Task 3: Backend Contract And Targeted Prompt

**Files:**
- Modify: `backend/app/routers/projects.py`
- Modify: `backend/app/services/prompt_builder.py`
- Test: `backend/tests/test_prompt_builder.py`
- Test: `backend/tests/test_material_analysis.py`

- [ ] **Step 1: Write failing backend tests**

Add prompt-builder test:

```py
def test_targeted_style_reference_prompt_guides_current_screen():
    prompt = build_module_image_prompt(
        product_info={"product_name": "积雪草精华"},
        style={"id": "style_reference", "name": "对标风格", "keywords": ["干净"], "primary_color": "#88AACC"},
        module={"id": "detail_ec_hero", "name": "首屏爆点", "description": "产品大图 + 核心功效", "image_group": "detail"},
        module_index=1,
        total_modules=16,
        has_style_reference=True,
        has_targeted_style_reference=True,
    )
    self.assertIn("当前屏重点参考", prompt)
    self.assertIn("全局参考图只用于统一色彩", prompt)
```

Add generation test:

```py
async def test_generation_accepts_targeted_style_reference_selections(self):
    previous_key = environ.get("IMAGE_GENERATION_API_KEY")
    environ["IMAGE_GENERATION_API_KEY"] = "test-key"
    try:
        with patch("app.routers.projects.call_image_model", new=AsyncMock(return_value=["https://example.com/hero.png"])) as mocked:
            result = await generate_detail_images(
                ["detail_ec_hero"],
                "green_repair",
                product_info={"product_name": "积雪草精华"},
                reference_images=["data:image/png;base64,product"],
                style_reference_images=["data:image/png;base64,target", "data:image/png;base64,global"],
                style_reference_selections=[
                    {"url": "data:image/png;base64,target", "strength": "targeted", "scopes": [{"type": "module", "moduleId": "detail_ec_hero"}]},
                    {"url": "data:image/png;base64,global", "strength": "global", "scopes": [{"type": "global"}]},
                ],
            )
    finally:
        if previous_key is None:
            environ.pop("IMAGE_GENERATION_API_KEY", None)
        else:
            environ["IMAGE_GENERATION_API_KEY"] = previous_key

    self.assertEqual(result["source"], "model")
    prompt = mocked.call_args.args[1] if len(mocked.call_args.args) > 1 else mocked.call_args.kwargs["prompt"]
    self.assertIn("当前屏重点参考", prompt)
```

- [ ] **Step 2: Run backend focused tests and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_prompt_builder.py backend/tests/test_material_analysis.py -q
```

Expected: fails because new parameter and contract are missing.

- [ ] **Step 3: Implement backend pass-through and prompt**

In `backend/app/services/prompt_builder.py`:

- Add `has_targeted_style_reference: bool = False` to `build_module_image_prompt`.
- Add targeted-reference instruction to the style reference section when true:

```py
targeted_style_reference_rule = (
    "- 本次上传的对标图中，有图片被指定为当前屏重点参考。优先学习这些图片的构图、信息层级、视觉节奏和版式比例；全局参考图只用于统一色彩、光影和质感，不要照搬其他屏的文案或模块内容。"
    if has_targeted_style_reference
    else ""
)
```

Include it in `style_section` after the existing uploaded-reference priority rule.

In `backend/app/routers/projects.py`:

- Add `style_reference_selections` optional parameters to `_generate_module_image` and `generate_detail_images`.
- Add a helper:

```py
def _has_targeted_style_reference_for_module(selections: list[dict[str, Any]] | None, module_id: str) -> bool:
    return any(str(item.get("strength")) == "targeted" and any(scope.get("type") == "module" and str(scope.get("moduleId")) == module_id for scope in item.get("scopes") or []) for item in selections or [])
```

- Pass `has_targeted_style_reference=_has_targeted_style_reference_for_module(style_reference_selections, module_id)` into `build_module_image_prompt`.
- Add `style_reference_selections: list[dict[str, Any]] = Field(default_factory=list)` to `GenerateRequest`, `_generation_payload_from_request`, `run_generation_job`, direct generation route, and generation call.

- [ ] **Step 4: Run backend focused tests and verify GREEN**

Run:

```powershell
python -m pytest backend/tests/test_prompt_builder.py backend/tests/test_material_analysis.py -q
```

Expected: focused backend tests pass.

### Task 4: Full Verification And Commit

**Files:**
- All modified frontend and backend files.

- [ ] **Step 1: Run frontend verification**

Run:

```powershell
npm.cmd run test
npm.cmd run build
```

from `frontend`.

Expected: test and build succeed.

- [ ] **Step 2: Run backend verification**

Run:

```powershell
python -m pytest backend/tests/test_prompt_builder.py backend/tests/test_material_analysis.py backend/tests/test_api_contracts.py -q
```

Expected: targeted backend suites pass.

- [ ] **Step 3: Check git diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: only files listed in this plan changed.

- [ ] **Step 4: Commit implementation**

Run:

```powershell
git add frontend/lib/types.ts frontend/lib/styleReferenceTargeting.ts frontend/tests/project-enhancements.test.cjs frontend/tests/static-ui-contract.test.cjs frontend/components/StyleStep.tsx frontend/app/page.tsx frontend/lib/api.ts frontend/app/globals.css backend/app/routers/projects.py backend/app/services/prompt_builder.py backend/tests/test_prompt_builder.py backend/tests/test_material_analysis.py
git commit -m "feat: target benchmark references by screen"
```

Expected: commit is created after verification.
