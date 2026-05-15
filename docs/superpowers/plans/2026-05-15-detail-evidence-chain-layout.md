# Detail Evidence Chain Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a selectable detail image layout system with a new default 16-screen evidence-chain structure, early upload-step selection, structure-aware material analysis, and shared selling-point data for main/campaign images.

**Architecture:** Introduce layout configuration as a first-class frontend/backend contract. The frontend persists `selectedDetailLayoutId`, applies the selected layout to detail modules, sends `detail_layout_id` during material analysis and generation, and keeps main/campaign modules unchanged. The backend exposes both layout registries, produces layout-aware analysis prompts, normalizes `cross_image_brief` and `detail_layout_brief`, and builds prompts for new evidence-chain modules while using the shared brief for all image groups.

**Tech Stack:** Next.js React components, TypeScript helper modules/tests, FastAPI/Pydantic router code, Python prompt builder/unit tests.

---

### Task 1: Frontend Layout Contract

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/constants.ts`
- Modify: `frontend/lib/projectEnhancements.ts`
- Test: `frontend/tests/project-enhancements.test.cjs`
- Test: `frontend/tests/static-ui-contract.test.cjs`

- [ ] **Step 1: Write failing tests**

Add tests that expect:

```js
const { DETAIL_LAYOUTS, DEFAULT_DETAIL_LAYOUT_ID } = constantsSandbox.module.exports;
const {
  applyDetailLayoutToModules,
  detailLayoutModules,
  inferDetailLayoutIdFromModules,
  normalizeDetailModuleOrder
} = sandbox.module.exports;

assert.equal(DEFAULT_DETAIL_LAYOUT_ID, "detail_evidence_chain_16");
assert.equal(DETAIL_LAYOUTS.find((layout) => layout.id === "detail_evidence_chain_16").modules.length, 16);
assert.deepEqual(detailLayoutModules("detail_standard_conversion_10").map((module) => module.id), [
  "hero",
  "brand_qualification",
  "research_strength",
  "pain_scene",
  "effect_comparison",
  "competitor_comparison",
  "product_showcase",
  "ingredient_overview",
  "usage",
  "product_info"
]);
assert.equal(inferDetailLayoutIdFromModules(DEFAULT_MODULES), "detail_evidence_chain_16");
assert.equal(inferDetailLayoutIdFromModules([{ id: "hero", image_group: "detail" }]), "detail_standard_conversion_10");
```

Run: `node frontend/tests/project-enhancements.test.cjs`
Expected: FAIL because layout exports/helpers do not exist.

- [ ] **Step 2: Implement layout config and helpers**

Add `DetailLayoutId`, `DetailLayoutConfig`, `ProductInfo.detail_layout_brief`, `ProductInfo.cross_image_brief`, and `PersistedProjectState.selectedDetailLayoutId`. Add `DETAIL_LAYOUTS`, `DEFAULT_DETAIL_LAYOUT_ID`, 16 evidence-chain modules, and helpers to apply/normalize selected detail modules.

- [ ] **Step 3: Verify frontend helper tests pass**

Run: `node frontend/tests/project-enhancements.test.cjs`
Expected: PASS.

### Task 2: Upload-Step Selection and State Persistence

**Files:**
- Modify: `frontend/components/UploadStep.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/lib/api.ts`
- Test: `frontend/tests/static-ui-contract.test.cjs`

- [ ] **Step 1: Write failing static contract tests**

Add checks that expect upload-step layout selection and API payload wiring:

```js
assertIncludes("components/UploadStep.tsx", "详情图排版结构", "upload step must let users choose the detail layout before analysis");
assertIncludes("components/UploadStep.tsx", "onDetailLayoutChange", "upload step must propagate detail layout changes");
assertIncludes("app/page.tsx", "selectedDetailLayoutId", "page must persist the selected detail layout");
assertIncludes("app/page.tsx", "detailLayoutId: selectedDetailLayoutId", "material analysis must use the selected detail layout");
assertIncludes("lib/api.ts", "detail_layout_id: detailLayoutId", "analysis API must send the selected detail layout id");
```

Run: `node frontend/tests/static-ui-contract.test.cjs`
Expected: FAIL because upload selection and payload wiring do not exist.

- [ ] **Step 2: Implement state and UI**

Add selected detail layout state, snapshot persistence, history restore, new-project reset, upload-step selector, and re-application of detail modules when layout changes.

- [ ] **Step 3: Verify static contract tests pass**

Run: `node frontend/tests/static-ui-contract.test.cjs`
Expected: PASS.

### Task 3: Backend Layout Registry and Analysis Contract

**Files:**
- Modify: `backend/app/demo_data.py`
- Modify: `backend/app/routers/projects.py`
- Test: `backend/tests/test_api_contracts.py`

- [ ] **Step 1: Write failing backend API tests**

Add tests that expect:

```python
from app.demo_data import DEFAULT_DETAIL_LAYOUT_ID, DETAIL_LAYOUTS, ALL_MODULES

self.assertEqual(DEFAULT_DETAIL_LAYOUT_ID, "detail_evidence_chain_16")
self.assertEqual(len(DETAIL_LAYOUTS["detail_evidence_chain_16"]["modules"]), 16)
self.assertIn("detail_ec_auxiliary_mechanism", {module["id"] for module in ALL_MODULES})
self.assertIn("detail_layouts", self.make_client().get("/api/projects/defaults").json())
```

Also add a test for `build_material_analysis_messages(..., detail_layout_id="detail_evidence_chain_16")` containing `cross_image_brief`, `detail_layout_brief`, and `辅助功效机制`.

Run: `python -m pytest backend/tests/test_api_contracts.py -q`
Expected: FAIL because backend layout registry and analysis prompt do not exist.

- [ ] **Step 2: Implement backend registry and request plumbing**

Add backend layout constants, include layouts/default id in `/defaults`, accept `detail_layout_id` in analyze/generate requests, and pass it into material analysis messages.

- [ ] **Step 3: Verify backend API tests pass**

Run: `python -m pytest backend/tests/test_api_contracts.py -q`
Expected: PASS.

### Task 4: Prompt Builder Support for 16 Screens

**Files:**
- Modify: `backend/app/services/prompt_builder.py`
- Modify: `backend/app/routers/projects.py`
- Test: `backend/tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing prompt tests**

Add tests that build prompts for:

```python
detail_ec_competitor_comparison
detail_ec_auxiliary_mechanism
detail_ec_auxiliary_validation
```

Expect competitor prompt to include “普通同类产品” and not real competitor brands; expect modules 11/12 to include “辅助功效” and not hard-code “长效保湿” or “焕亮肤色”.

Run: `python -m pytest backend/tests/test_prompt_builder.py -q`
Expected: FAIL because new modules are not implemented in prompt builder.

- [ ] **Step 2: Implement prompt recipes**

Add module-specific prompt rules for the 16 evidence-chain modules and inject `cross_image_brief` / `detail_layout_brief` when present.

- [ ] **Step 3: Verify prompt tests pass**

Run: `python -m pytest backend/tests/test_prompt_builder.py -q`
Expected: PASS.

### Task 5: End-to-End Verification

**Files:**
- No production files unless tests reveal gaps.

- [ ] **Step 1: Run frontend tests**

Run:

```bash
npm --prefix frontend test
```

Expected: PASS.

- [ ] **Step 2: Run backend tests**

Run:

```bash
python -m pytest backend/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run targeted build/lint if available**

Run:

```bash
npm --prefix frontend run build
```

Expected: PASS or report the blocking error with exact output.
