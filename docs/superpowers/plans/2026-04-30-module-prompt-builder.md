# Module Prompt Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build backend-only module-aware hidden prompts for detail image generation.

**Architecture:** Add a pure prompt builder service and call it from the existing project generation route. Tests cover prompt content and route integration.

**Tech Stack:** Python, FastAPI route helpers, unittest.

---

### Task 1: Prompt Builder Unit Tests

**Files:**
- Modify: `backend/tests/test_material_analysis.py`
- Create: `backend/app/services/prompt_builder.py`

- [ ] Add tests that import `build_module_image_prompt`.
- [ ] Assert the authority module prompt contains module-only constraints and complete authority details.
- [ ] Assert the effect comparison module prompt contains each metric, value, source type, and compliance wording.
- [ ] Run `python -m unittest backend.tests.test_material_analysis -v` and confirm the new tests fail because the function does not exist.

### Task 2: Prompt Builder Implementation

**Files:**
- Create: `backend/app/services/prompt_builder.py`
- Modify: `backend/app/routers/projects.py`

- [ ] Implement `build_module_image_prompt(product_info, style, module, module_index, total_modules)`.
- [ ] Include the product brief, fixed module structure, module-specific content requirements, and visual constraints.
- [ ] Replace the inline prompt in `generate_detail_images()` with the builder.
- [ ] Run `python -m unittest backend.tests.test_material_analysis -v` and confirm the prompt tests pass.

### Task 3: Full Verification

**Files:**
- No additional files.

- [ ] Run `python -m unittest discover backend/tests -v`.
- [ ] Run `npm test` from `frontend` if Node scripts are available.
