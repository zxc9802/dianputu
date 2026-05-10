# Image Prompt Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved detail-page and store-main-image optimization docs to the image prompt builder without changing the existing module structure.

**Architecture:** Keep all module definitions and API flow intact. Strengthen `backend/app/services/prompt_builder.py` by adding conversion-oriented prompt sections, module-specific layout rules, visual-conflict guidance, and stricter forbidden elements; cover the behavior with focused prompt text tests.

**Tech Stack:** Python, unittest/pytest, existing prompt builder service.

---

### Task 1: Add Prompt Coverage Tests

**Files:**
- Modify: `backend/tests/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert prompts include the new store-main-image formula, detail-page visual-conflict rule, pain-scene problem visualization, competitor contrast, ingredient overview vs single ingredient separation, and activity promotion constraints.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=backend pytest backend/tests/test_prompt_builder.py -q
```

Expected before implementation: at least one assertion fails because the new optimization phrases are not yet emitted.

### Task 2: Implement Prompt Builder Rules

**Files:**
- Modify: `backend/app/services/prompt_builder.py`

- [ ] **Step 1: Add store-main-image optimization rules**

Add a reusable main-image prompt section covering click-rate tasking, product ratio, short headline, evidence-short guidance, and per-module roles for white background, hero, ingredient, effect, and usage-scene images.

- [ ] **Step 2: Add detail-page optimization rules**

Add a reusable detail prompt section covering page task, visual contradiction, lighting role, pain visualization, effect proof, competitor contrast, ingredient-system overview, single-ingredient separation, and usage simplification.

- [ ] **Step 3: Keep compliance constraints intact**

Preserve existing restrictions around unverified data, medicalized claims, platform compliance, product packaging fidelity, and visible text boundaries.

### Task 3: Verify

**Files:**
- Test: `backend/tests/test_prompt_builder.py`
- Test: `backend/tests/test_material_analysis.py`

- [ ] **Step 1: Run focused tests**

```bash
PYTHONPATH=backend pytest backend/tests/test_prompt_builder.py backend/tests/test_material_analysis.py -q
```

- [ ] **Step 2: Run broader backend tests if focused tests pass**

```bash
PYTHONPATH=backend pytest backend/tests -q
```

- [ ] **Step 3: Review diff**

```bash
git diff -- backend/app/services/prompt_builder.py backend/tests/test_prompt_builder.py docs/superpowers/plans/2026-05-10-image-prompt-optimization.md
```

