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
  require(request) {
    if (request === "@/lib/types") return {};
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
  enableModuleForSingleGeneration,
  resolveReusableHistoryId,
  getSelectedGeneratedImages,
  runParallelImageGeneration
} = sandbox.module.exports;

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

assert.equal(resolveReusableHistoryId(null, null), undefined);
assert.equal(resolveReusableHistoryId(null, "history-1"), "history-1");
assert.equal(resolveReusableHistoryId("history-1", "history-2"), "history-1");

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
