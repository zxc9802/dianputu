const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const constantsPath = path.join(root, "lib", "constants.ts");
const constantsSource = fs.readFileSync(constantsPath, "utf8");
const compiledConstants = ts.transpileModule(constantsSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019,
    esModuleInterop: true
  }
}).outputText;
const constantsSandbox = {
  exports: {},
  module: { exports: {} },
  require(request) {
    if (request === "@/lib/types" || request === "./types") return {};
    throw new Error(`Unexpected require: ${request}`);
  }
};
constantsSandbox.exports = constantsSandbox.module.exports;
vm.runInNewContext(compiledConstants, constantsSandbox, { filename: constantsPath });

const sourcePath = path.join(root, "lib", "projectEnhancements.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019,
    esModuleInterop: true
  }
}).outputText;

const sandbox = {
  exports: {},
  module: { exports: {} },
  process: { env: {} },
  require(request) {
    if (request === "@/lib/types") return {};
    if (request === "@/lib/constants") return constantsSandbox.module.exports;
    throw new Error(`Unexpected require: ${request}`);
  },
  Date,
  Math
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

const {
  appendImageVersions,
  applyTemplateToModules,
  applyDetailLayoutToModules,
  detailLayoutModules,
  inferDetailLayoutIdFromModules,
  enableModuleForSingleGeneration,
  resolveReusableHistoryId,
  resolveHistoryIdAfterSave,
  getSelectedGeneratedImages,
  buildDetailDownloadState,
  formatImageGenerationSummaryStatus,
  isRetryableImageGenerationError,
  normalizeDetailIngredientModuleOrder,
  normalizeDetailModuleOrder,
  resolveImageGenerationConcurrencyLimit,
  runParallelImageGeneration
  ,
  addLanguageVersion,
  selectLanguageVersion,
  replaceUploadedFileDataUrlsWithMaterialUrls
} = sandbox.module.exports;
const { DEFAULT_DETAIL_LAYOUT_ID, DEFAULT_MODULES, DETAIL_LAYOUTS, OFFICIAL_PROJECT_TEMPLATES } = constantsSandbox.module.exports;

const evidenceChainDetailIds = [
  "detail_ec_hero",
  "detail_ec_pain_matrix",
  "detail_ec_solution",
  "detail_ec_competitor_comparison",
  "detail_ec_real_trial",
  "detail_ec_effect_validation",
  "detail_ec_research_system",
  "detail_ec_ingredient_1_mechanism",
  "detail_ec_ingredient_1_proof",
  "detail_ec_ingredient_2_mechanism",
  "detail_ec_auxiliary_mechanism",
  "detail_ec_auxiliary_validation",
  "detail_ec_real_feedback",
  "detail_ec_texture",
  "detail_ec_brand_sensory",
  "detail_ec_usage"
];
const standardDetailIds = [
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
];

assert.equal(DEFAULT_DETAIL_LAYOUT_ID, "detail_evidence_chain_16");
assert.equal(DETAIL_LAYOUTS.find((layout) => layout.id === "detail_evidence_chain_16").modules.length, 16);
assert.deepEqual(JSON.parse(JSON.stringify(detailLayoutModules("detail_evidence_chain_16").map((module) => module.id))), evidenceChainDetailIds);
assert.deepEqual(JSON.parse(JSON.stringify(detailLayoutModules("detail_standard_conversion_10").map((module) => module.id))), standardDetailIds);
assert.equal(inferDetailLayoutIdFromModules(DEFAULT_MODULES), "detail_evidence_chain_16");
assert.equal(inferDetailLayoutIdFromModules([{ id: "hero", image_group: "detail" }]), "detail_standard_conversion_10");

const versionState = { versions: {}, selectedVersionIds: {} };
const first = appendImageVersions(versionState, [{ module_id: "hero", url: "v1.png" }], "model", 1000);
const second = appendImageVersions(first, [{ module_id: "hero", url: "v2.png" }], "model", 2000);
const third = appendImageVersions(second, [{ module_id: "hero", url: "v3.png" }], "model", 3000);
const fourth = appendImageVersions(third, [{ module_id: "hero", url: "v4.png" }], "model", 4000);

assert.deepEqual(
  [...fourth.versions.hero.map((version) => version.url)],
  ["v2.png", "v3.png", "v4.png"]
);
assert.equal(fourth.selectedVersionIds.hero, fourth.versions.hero[2].id);

const selected = getSelectedGeneratedImages(fourth.versions, { hero: fourth.versions.hero[0].id });
assert.deepEqual(JSON.parse(JSON.stringify(selected)), [{ module_id: "hero", url: "v2.png" }]);

const generatedDetailImages = DEFAULT_MODULES
  .filter((module) => module.image_group === "detail")
  .map((module) => ({ module_id: module.id, url: `https://img.example.com/${module.id}.png` }));
const detailDownloadState = buildDetailDownloadState(DEFAULT_MODULES, generatedDetailImages);
assert.deepEqual(
  JSON.parse(JSON.stringify(detailDownloadState.manifest.map((item) => item.module_id))),
  evidenceChainDetailIds
);
assert.deepEqual(
  JSON.parse(JSON.stringify(detailDownloadState.items.map((item) => item.module.id))),
  evidenceChainDetailIds
);
assert.equal(detailDownloadState.missingModules.length, 0);
const missingProductInfoDownloadState = buildDetailDownloadState(
  DEFAULT_MODULES,
  generatedDetailImages.filter((image) => image.module_id !== "detail_ec_usage")
);
assert.deepEqual(JSON.parse(JSON.stringify(missingProductInfoDownloadState.missingModules.map((module) => module.id))), ["detail_ec_usage"]);

const layered = appendImageVersions(
  { versions: {}, selectedVersionIds: {} },
  [
    {
      module_id: "hero",
      url: "hero-zh.png",
      base_url: "hero-base.png",
      text_layers: [{ id: "title", role: "title", text: "深层补水", x: 0.1, y: 0.1, width: 0.5, height: 0.1, font_size: 0.06 }],
      language_versions: {
        "zh-CN": {
          language: "zh-CN",
          language_label: "中文",
          url: "hero-zh.png",
            compliance: { source: "gemini", summary: { status: "block", block_count: 1, warn_count: 0, review_count: 0 }, issues: [{ term: "治愈" }] }
        }
      },
        compliance: { source: "gemini", summary: { status: "block", block_count: 1, warn_count: 0, review_count: 0 }, issues: [{ term: "治愈" }] }
    }
  ],
  "model",
  5000
);
const layeredVersion = layered.versions.hero[0];
assert.equal(layeredVersion.baseUrl, "hero-base.png");
assert.equal(layeredVersion.selectedLanguage, "zh-CN");
assert.equal(layeredVersion.languageVersions["zh-CN"].url, "hero-zh.png");
assert.equal(layeredVersion.compliance.summary.status, "block");
assert.equal(layeredVersion.languageVersions["zh-CN"].compliance.summary.status, "block");

const uploadedFilesWithLocalImage = [
  {
    id: "file-1",
    slot: "product_image",
    name: "main.png",
    size: 4096,
    type: "image/png",
    lastModified: 1,
    dataUrl: "data:image/png;base64,abc"
  },
  {
    id: "file-2",
    slot: "documents",
    name: "report.pdf",
    size: 4096,
    type: "application/pdf",
    lastModified: 2,
    dataUrl: "data:application/pdf;base64,abc"
  }
];
const uploadedFilesWithRemoteImage = replaceUploadedFileDataUrlsWithMaterialUrls(uploadedFilesWithLocalImage, [
  {
    id: "file-1",
    slot: "product_image",
    filename: "main.png",
    content_type: "image/png",
    url: "https://img.example.com/prod/materials/main.png"
  }
]);
assert.equal(uploadedFilesWithRemoteImage[0].dataUrl, "https://img.example.com/prod/materials/main.png");
assert.equal(uploadedFilesWithRemoteImage[1].dataUrl, "data:application/pdf;base64,abc");

const withEnglish = addLanguageVersion(layered, "hero", layeredVersion.id, {
  language: "en",
  language_label: "English",
  url: "hero-en.png",
  layers: [{ id: "title", role: "title", text: "Deep Hydration", x: 0.1, y: 0.1, width: 0.5, height: 0.1, font_size: 0.06 }],
  compliance: { source: "gemini", summary: { status: "warn", block_count: 0, warn_count: 1, review_count: 0 }, issues: [{ term: "100%" }] }
}, 6000);
assert.equal(withEnglish.versions.hero[0].selectedLanguage, "en");
assert.equal(withEnglish.versions.hero[0].languageVersions.en.url, "hero-en.png");
assert.equal(withEnglish.versions.hero[0].languageVersions.en.compliance.summary.status, "warn");
assert.deepEqual(JSON.parse(JSON.stringify(getSelectedGeneratedImages(withEnglish.versions, withEnglish.selectedVersionIds))), [{ module_id: "hero", url: "hero-en.png" }]);

const backToChinese = selectLanguageVersion(withEnglish, "hero", layeredVersion.id, "zh-CN");
assert.equal(backToChinese.versions.hero[0].selectedLanguage, "zh-CN");
assert.deepEqual(JSON.parse(JSON.stringify(getSelectedGeneratedImages(backToChinese.versions, backToChinese.selectedVersionIds))), [{ module_id: "hero", url: "hero-zh.png" }]);

const vietnameseBase = appendImageVersions(
  { versions: {}, selectedVersionIds: {} },
  [{
    module_id: "hero",
    url: "hero-vi.png",
    language_versions: {
      vi: {
        language: "vi",
        language_label: "Tiếng Việt",
        url: "hero-vi.png"
      }
    }
  }],
  "model",
  6500
);
assert.equal(vietnameseBase.versions.hero[0].selectedLanguage, "vi");

const nonLayeredBase = appendImageVersions(
  { versions: {}, selectedVersionIds: {} },
  [{ module_id: "main_hero_selling_point", url: "main-zh.png" }],
  "model",
  7000
);
const nonLayeredVersion = nonLayeredBase.versions.main_hero_selling_point[0];
const nonLayeredEnglish = addLanguageVersion(nonLayeredBase, "main_hero_selling_point", nonLayeredVersion.id, {
  language: "en",
  language_label: "English",
  url: "main-en.png"
}, 8000);
assert.equal(nonLayeredEnglish.versions.main_hero_selling_point[0].url, "main-zh.png");
assert.deepEqual(JSON.parse(JSON.stringify(getSelectedGeneratedImages(nonLayeredEnglish.versions, nonLayeredEnglish.selectedVersionIds))), [{ module_id: "main_hero_selling_point", url: "main-en.png" }]);
const nonLayeredBackToChinese = selectLanguageVersion(nonLayeredEnglish, "main_hero_selling_point", nonLayeredVersion.id, "zh-CN");
assert.deepEqual(JSON.parse(JSON.stringify(getSelectedGeneratedImages(nonLayeredBackToChinese.versions, nonLayeredBackToChinese.selectedVersionIds))), [{ module_id: "main_hero_selling_point", url: "main-zh.png" }]);

assert.equal(resolveReusableHistoryId(null, null), undefined);
assert.equal(resolveReusableHistoryId(null, "history-1"), "history-1");
assert.equal(resolveReusableHistoryId("history-1", "history-2"), "history-1");
assert.equal(resolveHistoryIdAfterSave(null, "history-1"), "history-1");
assert.equal(resolveHistoryIdAfterSave("history-1", "history-2"), "history-1");
assert.equal(resolveHistoryIdAfterSave(null, "history-1", { trackSavedHistoryId: false }), null);
assert.equal(resolveHistoryIdAfterSave("copy-history", "original-history", { trackSavedHistoryId: false }), "copy-history");
assert.equal(
  formatImageGenerationSummaryStatus("主图", { completed: 1, total: 1, errorCount: 1, errors: ["hero: image model returned empty content"] }),
  "主图生成失败：hero: image model returned empty content"
);
assert.equal(
  formatImageGenerationSummaryStatus("详情图", { completed: 2, total: 3, errorCount: 1, errors: ["usage: timeout"] }),
  "详情图部分生成失败：1/3，usage: timeout"
);
assert.equal(resolveImageGenerationConcurrencyLimit(), 2);
assert.equal(isRetryableImageGenerationError("Server disconnected without sending a response."), true);
assert.equal(isRetryableImageGenerationError("missing product reference image"), false);
sandbox.process.env.NEXT_PUBLIC_IMAGE_GENERATION_CONCURRENCY = "7";
assert.equal(resolveImageGenerationConcurrencyLimit(), 7);
sandbox.process.env.NEXT_PUBLIC_IMAGE_GENERATION_CONCURRENCY = "invalid";
assert.equal(resolveImageGenerationConcurrencyLimit(), 2);
delete sandbox.process.env.NEXT_PUBLIC_IMAGE_GENERATION_CONCURRENCY;

const modules = [
  { id: "hero", name: "详情首图", description: "", enabled: false, order: 9, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "", enabled: true, order: 1, image_group: "detail" }
];
const templated = applyTemplateToModules(modules, {
  id: "template-serum",
  name: "精华类模板",
  category: "护肤精华",
  styleId: "green_repair",
  platformId: "tmall",
  modules: [
    { id: "hero", enabled: true, order: 1 },
    { id: "usage", enabled: false, order: 2 }
  ],
  source: "official"
});

assert.deepEqual(
  JSON.parse(JSON.stringify(templated.filter((module) => ["hero", "usage"].includes(module.id)).map((module) => ({ id: module.id, enabled: module.enabled, order: module.order })))),
  [
    { id: "hero", enabled: true, order: 1 },
    { id: "usage", enabled: false, order: 9 }
  ]
);
assert.equal(templated.filter((module) => module.image_group === "detail").length, 10);

for (const template of OFFICIAL_PROJECT_TEMPLATES) {
  const moduleIds = template.modules.map((module) => module.id);
  assert.equal(template.detailLayoutId, "detail_evidence_chain_16", `${template.id} must use the evidence-chain layout by default`);
  assert.ok(moduleIds.includes("detail_ec_competitor_comparison"), `${template.id} must keep the competitor comparison page`);
  assert.ok(moduleIds.includes("detail_ec_research_system"), `${template.id} must keep the research system page`);
  assert.ok(moduleIds.includes("detail_ec_auxiliary_mechanism"), `${template.id} must keep the generic auxiliary mechanism page`);
  assert.ok(moduleIds.includes("detail_ec_auxiliary_validation"), `${template.id} must keep the generic auxiliary validation page`);
  assert.ok(moduleIds.includes("detail_ec_usage"), `${template.id} must keep the usage page`);
  assert.ok(!moduleIds.includes("ingredient_1"), `${template.id} must not keep old ingredient explanation page 1`);
  assert.ok(!moduleIds.includes("ingredient_2"), `${template.id} must not keep old ingredient explanation page 2`);
  assert.ok(!moduleIds.includes("ingredient_3"), `${template.id} must not keep old ingredient explanation page 3`);
}

const restoredBadDetailOrder = normalizeDetailIngredientModuleOrder([
  { id: "hero", name: "详情首图", description: "", enabled: true, order: 1, image_group: "detail" },
  { id: "product_info", name: "产品信息", description: "", enabled: true, order: 2, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "", enabled: true, order: 3, image_group: "detail" },
  { id: "ingredient_overview", name: "成分总览", description: "", enabled: true, order: 4, image_group: "detail" },
  { id: "product_showcase", name: "产品大图强化", description: "", enabled: true, order: 5, image_group: "detail" },
  { id: "competitor_comparison", name: "竞品对比", description: "", enabled: true, order: 6, image_group: "detail" },
  { id: "effect_comparison", name: "效果对比", description: "", enabled: true, order: 7, image_group: "detail" },
  { id: "pain_scene", name: "痛点场景", description: "", enabled: true, order: 8, image_group: "detail" },
  { id: "research_strength", name: "研发实力", description: "", enabled: true, order: 9, image_group: "detail" },
  { id: "brand_qualification", name: "品牌与资质背书", description: "", enabled: true, order: 10, image_group: "detail" }
]);
assert.deepEqual(
  JSON.parse(JSON.stringify(restoredBadDetailOrder
    .filter((module) => module.image_group === "detail")
    .sort((a, b) => a.order - b.order)
    .map((module) => module.id))),
  standardDetailIds
);

const evidenceLayoutModules = applyDetailLayoutToModules(DEFAULT_MODULES, "detail_evidence_chain_16");
assert.equal(evidenceLayoutModules.filter((module) => module.image_group === "detail").length, 16);
assert.equal(evidenceLayoutModules.find((module) => module.id === "detail_ec_competitor_comparison").order, 4);
assert.equal(evidenceLayoutModules.find((module) => module.id === "detail_ec_auxiliary_mechanism").order, 11);

const standardLayoutModules = applyDetailLayoutToModules(DEFAULT_MODULES, "detail_standard_conversion_10");
assert.deepEqual(
  JSON.parse(JSON.stringify(standardLayoutModules
    .filter((module) => module.image_group === "detail")
    .sort((a, b) => a.order - b.order)
    .map((module) => module.id))),
  standardDetailIds
);

const staleEvidenceOrder = normalizeDetailModuleOrder([
  { id: "detail_ec_usage", name: "使用方法", description: "", enabled: true, order: 1, image_group: "detail" },
  { id: "detail_ec_hero", name: "首屏爆点", description: "", enabled: true, order: 16, image_group: "detail" },
  { id: "detail_ec_auxiliary_validation", name: "辅助功效验证", description: "", enabled: true, order: 2, image_group: "detail" }
], "detail_evidence_chain_16");
assert.deepEqual(
  JSON.parse(JSON.stringify(staleEvidenceOrder
    .filter((module) => module.image_group === "detail")
    .sort((a, b) => a.order - b.order)
    .map((module) => module.id))),
  ["detail_ec_hero", "detail_ec_auxiliary_validation", "detail_ec_usage"]
);

const singleGenerateModules = [
  { id: "main_ingredient", name: "次图-成分", description: "", enabled: false, order: 3, image_group: "main" },
  { id: "campaign_effect", name: "活动次图-效果", description: "", enabled: false, order: 4, image_group: "campaign" },
  { id: "pain_scene", name: "痛点场景", description: "", enabled: false, order: 4, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "", enabled: true, order: 9, image_group: "detail" }
];
const enabledMainSingle = enableModuleForSingleGeneration(singleGenerateModules, "main_ingredient");
const enabledCampaignSingle = enableModuleForSingleGeneration(singleGenerateModules, "campaign_effect");
const enabledDetailSingle = enableModuleForSingleGeneration(singleGenerateModules, "pain_scene");

assert.equal(enabledMainSingle.find((module) => module.id === "main_ingredient").enabled, true);
assert.equal(enabledCampaignSingle.find((module) => module.id === "campaign_effect").enabled, true);
assert.equal(enabledDetailSingle.find((module) => module.id === "pain_scene").enabled, true);
assert.equal(singleGenerateModules.find((module) => module.id === "main_ingredient").enabled, false);
assert.equal(singleGenerateModules.find((module) => module.id === "campaign_effect").enabled, false);
assert.equal(singleGenerateModules.find((module) => module.id === "pain_scene").enabled, false);

async function runAsyncChecks() {
  const releaseById = new Map();
  const started = [];
  const completed = [];
  let active = 0;
  let maxActive = 0;

  const generationPromise = runParallelImageGeneration(
    [
      { id: "hero" },
      { id: "usage" },
      { id: "pain" },
      { id: "effect" }
    ],
    async (module) => {
      started.push(module.id);
      active += 1;
      maxActive = Math.max(maxActive, active);
      await new Promise((resolve) => {
        releaseById.set(module.id, resolve);
      });
      active -= 1;
      return {
        source: "model",
        images: [{ module_id: module.id, url: `${module.id}.png` }],
        errors: module.id === "usage" ? ["minor fallback"] : []
      };
    },
    (module, result, progress) => {
      completed.push({
        id: module.id,
        completed: progress.completed,
        errorCount: progress.errorCount,
        imageUrl: result.images[0].url
      });
    }
  );

  await Promise.resolve();
  assert.deepEqual([...started], ["hero", "usage"]);
  assert.equal(maxActive, 2);
  releaseById.get("hero")();
  releaseById.get("usage")();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual([...started], ["hero", "usage", "pain", "effect"]);
  assert.equal(maxActive, 2);
  releaseById.get("pain")();
  releaseById.get("effect")();
  const summary = await generationPromise;
  assert.equal(summary.completed, 4);
  assert.equal(summary.errorCount, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(summary.errors)), ["usage: minor fallback"]);
  assert.equal(completed.length, 4);
}

async function runRetryChecks() {
  const attempts = [];
  const retries = [];
  const completed = [];
  const summary = await runParallelImageGeneration(
    [
      { id: "detail_ec_hero" },
      { id: "detail_ec_usage" }
    ],
    async (module) => {
      attempts.push(module.id);
      const moduleAttempts = attempts.filter((id) => id === module.id).length;
      if (module.id === "detail_ec_hero" && moduleAttempts === 1) {
        return {
          source: "error",
          images: [],
          errors: ["primary gpt image failed: Server disconnected without sending a response."]
        };
      }
      return {
        source: "model",
        images: [{ module_id: module.id, url: `${module.id}.png` }],
        errors: []
      };
    },
    (module, result, progress) => {
      completed.push({
        id: module.id,
        completed: progress.completed,
        errorCount: progress.errorCount,
        imageCount: result.images.length
      });
    },
    {
      concurrencyLimit: 2,
      retryAttempts: 2,
      retryDelaysMs: [0, 0],
      retryJitterMs: 0,
      wait: async () => {},
      onRetry: (module, attempt, retryAttempts, delayMs, errors) => {
        retries.push({ id: module.id, attempt, retryAttempts, delayMs, error: errors[0] });
      }
    }
  );

  assert.deepEqual(JSON.parse(JSON.stringify(retries)), [
    {
      id: "detail_ec_hero",
      attempt: 1,
      retryAttempts: 2,
      delayMs: 0,
      error: "primary gpt image failed: Server disconnected without sending a response."
    }
  ]);
  assert.equal(attempts.filter((id) => id === "detail_ec_hero").length, 2);
  assert.equal(summary.completed, 2);
  assert.equal(summary.errorCount, 0);
  assert.deepEqual(JSON.parse(JSON.stringify(summary.errors)), []);
  assert.equal(completed.length, 2);
  assert.ok(completed.some((item) => item.id === "detail_ec_hero" && item.imageCount === 1));

  const nonRetryAttempts = [];
  const nonRetrySummary = await runParallelImageGeneration(
    [{ id: "detail_ec_solution" }],
    async (module) => {
      nonRetryAttempts.push(module.id);
      return { source: "error", images: [], errors: ["missing product reference image"] };
    },
    () => {},
    { concurrencyLimit: 1, retryAttempts: 2, retryDelaysMs: [0, 0], retryJitterMs: 0, wait: async () => {} }
  );
  assert.equal(nonRetryAttempts.length, 1);
  assert.equal(nonRetrySummary.errorCount, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(nonRetrySummary.errors)), ["detail_ec_solution: missing product reference image"]);
}

const targetingPath = path.join(root, "lib", "styleReferenceTargeting.ts");
const targetingSource = fs.readFileSync(targetingPath, "utf8");
const compiledTargeting = ts.transpileModule(targetingSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019,
    esModuleInterop: true
  }
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
const plainValue = (value) => JSON.parse(JSON.stringify(value));

assert.deepEqual(plainValue(normalizeStyleReferenceScopes(undefined)), [{ type: "global" }]);
assert.equal(buildStyleReferenceScopeOptions(DEFAULT_MODULES, "detail_evidence_chain_16").detail[0].moduleId, "detail_ec_hero");
assert.equal(buildStyleReferenceScopeOptions(DEFAULT_MODULES, "detail_standard_conversion_10").detail[0].moduleId, "hero");
assert.deepEqual(plainValue(moveStyleReferenceFile([{ id: "a" }, { id: "b" }, { id: "c" }], "c", -1).map((item) => item.id)), ["a", "c", "b"]);

const refFiles = [
  { id: "t1", name: "target one", slot: "style_reference", type: "image/png", dataUrl: "target-1", styleReferenceScopes: [{ type: "module", moduleId: "detail_ec_hero" }] },
  { id: "g1", name: "global one", slot: "style_reference", type: "image/png", dataUrl: "global-1", styleReferenceScopes: [{ type: "global" }] },
  { id: "t2", name: "target two", slot: "style_reference", type: "image/png", dataUrl: "target-2", styleReferenceScopes: [{ type: "module", moduleId: "detail_ec_hero" }] },
  { id: "t3", name: "target three", slot: "style_reference", type: "image/png", dataUrl: "target-3", styleReferenceScopes: [{ type: "module", moduleId: "detail_ec_hero" }] },
  { id: "g2", name: "global two", slot: "style_reference", type: "image/png", dataUrl: "global-2", styleReferenceScopes: [{ type: "global" }] }
];

assert.deepEqual(plainValue(selectStyleReferencesForModule(refFiles, "detail_ec_hero").images), ["target-1", "target-2", "global-1"]);
assert.deepEqual(plainValue(selectStyleReferencesForModule(refFiles, "detail_ec_usage").images), ["global-1", "global-2"]);

runAsyncChecks()
  .then(runRetryChecks)
  .then(() => {
    console.log("Project enhancement checks passed.");
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
