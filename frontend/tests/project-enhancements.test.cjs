const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
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
    throw new Error(`Unexpected require: ${request}`);
  },
  Date,
  Math
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

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

const {
  appendImageVersions,
  applyTemplateToModules,
  enableModuleForSingleGeneration,
  resolveReusableHistoryId,
  resolveHistoryIdAfterSave,
  getSelectedGeneratedImages,
  formatImageGenerationSummaryStatus,
  normalizeDetailIngredientModuleOrder,
  resolveImageGenerationConcurrencyLimit,
  runParallelImageGeneration
  ,
  addLanguageVersion,
  selectLanguageVersion,
  replaceUploadedFileDataUrlsWithMaterialUrls
} = sandbox.module.exports;
const { OFFICIAL_PROJECT_TEMPLATES } = constantsSandbox.module.exports;

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
          compliance: { source: "rules", summary: { status: "block", block_count: 1, warn_count: 0, review_count: 0 }, issues: [{ term: "治愈" }] }
        }
      },
      compliance: { source: "rules", summary: { status: "block", block_count: 1, warn_count: 0, review_count: 0 }, issues: [{ term: "治愈" }] }
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
  compliance: { source: "rules", summary: { status: "warn", block_count: 0, warn_count: 1, review_count: 0 }, issues: [{ term: "100%" }] }
}, 6000);
assert.equal(withEnglish.versions.hero[0].selectedLanguage, "en");
assert.equal(withEnglish.versions.hero[0].languageVersions.en.url, "hero-en.png");
assert.equal(withEnglish.versions.hero[0].languageVersions.en.compliance.summary.status, "warn");
assert.deepEqual(JSON.parse(JSON.stringify(getSelectedGeneratedImages(withEnglish.versions, withEnglish.selectedVersionIds))), [{ module_id: "hero", url: "hero-en.png" }]);

const backToChinese = selectLanguageVersion(withEnglish, "hero", layeredVersion.id, "zh-CN");
assert.equal(backToChinese.versions.hero[0].selectedLanguage, "zh-CN");
assert.deepEqual(JSON.parse(JSON.stringify(getSelectedGeneratedImages(backToChinese.versions, backToChinese.selectedVersionIds))), [{ module_id: "hero", url: "hero-zh.png" }]);

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
  JSON.parse(JSON.stringify(templated.map((module) => ({ id: module.id, enabled: module.enabled, order: module.order })))),
  [
    { id: "hero", enabled: true, order: 1 },
    { id: "usage", enabled: false, order: 2 }
  ]
);

for (const template of OFFICIAL_PROJECT_TEMPLATES) {
  const moduleIds = template.modules.map((module) => module.id);
  assert.ok(moduleIds.includes("ingredient_overview"), `${template.id} must keep the ingredient overview page`);
  assert.ok(moduleIds.includes("ingredient_1"), `${template.id} must keep ingredient explanation page 1`);
  assert.ok(moduleIds.includes("ingredient_2"), `${template.id} must keep ingredient explanation page 2`);
  assert.ok(moduleIds.includes("ingredient_3"), `${template.id} must keep ingredient explanation page 3`);
}

const restoredBadIngredientOrder = normalizeDetailIngredientModuleOrder([
  { id: "hero", name: "详情首图", description: "", enabled: true, order: 1, image_group: "detail" },
  { id: "authority", name: "权威资质展示", description: "", enabled: true, order: 2, image_group: "detail" },
  { id: "pain_scene", name: "痛点场景", description: "", enabled: true, order: 3, image_group: "detail" },
  { id: "effect_comparison", name: "效果对比", description: "", enabled: true, order: 4, image_group: "detail" },
  { id: "competitor_comparison", name: "竞品对比", description: "", enabled: true, order: 5, image_group: "detail" },
  { id: "ingredient_overview", name: "成分总览", description: "", enabled: true, order: 6, image_group: "detail" },
  { id: "ingredient_1", name: "成分 1 讲解", description: "", enabled: true, order: 7, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "", enabled: true, order: 8, image_group: "detail" },
  { id: "ingredient_2", name: "成分 2 讲解", description: "", enabled: true, order: 9, image_group: "detail" },
  { id: "ingredient_3", name: "成分 3 讲解", description: "", enabled: true, order: 10, image_group: "detail" }
]);
assert.deepEqual(
  restoredBadIngredientOrder
    .filter((module) => module.image_group === "detail")
    .sort((a, b) => a.order - b.order)
    .map((module) => module.id)
    .slice(5),
  ["ingredient_overview", "ingredient_1", "ingredient_2", "ingredient_3", "usage"]
);

const singleGenerateModules = [
  { id: "main_ingredient", name: "次图-成分", description: "", enabled: false, order: 3, image_group: "main" },
  { id: "campaign_effect", name: "活动次图-效果", description: "", enabled: false, order: 4, image_group: "campaign" },
  { id: "pain_scene", name: "痛点场景", description: "", enabled: false, order: 3, image_group: "detail" },
  { id: "usage", name: "使用方法", description: "", enabled: true, order: 7, image_group: "detail" }
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

runAsyncChecks()
  .then(() => {
    console.log("Project enhancement checks passed.");
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
