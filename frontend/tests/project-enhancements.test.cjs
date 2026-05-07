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
    if (request === "./constants") {
      return {
        STYLE_OPTIONS: [
          { id: "green_repair", name: "绿色修护风", keywords: [], primary_color: "#1F8C43", asset: "" },
          { id: "blue_hydration", name: "蓝色补水风", keywords: [], primary_color: "#347FB9", asset: "" },
          { id: "gold_antiaging", name: "金色抗老风", keywords: [], primary_color: "#B88727", asset: "" }
        ]
      };
    }
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
  extractDominantColorsFromRgba,
  getSelectedGeneratedImages,
  recommendStyleFromBrandColors,
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

const dominant = extractDominantColorsFromRgba([
  31, 140, 67, 255,
  31, 140, 67, 255,
  52, 127, 185, 255,
  255, 255, 255, 255
]);
assert.deepEqual([...dominant.slice(0, 2)], ["#1F8C43", "#347FB9"]);

const recommendation = recommendStyleFromBrandColors(["#208C40"]);
assert.equal(recommendation?.styleId, "green_repair");

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

async function runAsyncChecks() {
  let release;
  const releasePromise = new Promise((resolve) => {
    release = resolve;
  });
  const started = [];
  const completed = [];

  const generationPromise = runParallelImageGeneration(
    [
      { id: "hero" },
      { id: "usage" }
    ],
    async (module) => {
      started.push(module.id);
      await releasePromise;
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
  release();
  const summary = await generationPromise;
  assert.equal(summary.completed, 2);
  assert.equal(summary.errorCount, 1);
  assert.equal(completed.length, 2);
}

runAsyncChecks()
  .then(() => {
    console.log("Project enhancement checks passed.");
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
