const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib", "productInfo.ts");
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
  }
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

const { applyProductInfoDraft, mergeProductInfoWithManualPriority } = sandbox.module.exports;

const current = {
  product_name: "手填精华名称",
  category: "护肤精华",
  spec: "30ml",
  core_selling_points: ["手填舒缓卖点"],
  functions: ["旧功效"],
  ingredients: [{ name: "旧成分", benefit: "旧说明" }],
  target_users: ["旧人群"],
  usage_method: ["旧用法"],
  authority_assets: ["旧资质"],
  effect_claims: [{ claim: "旧数据", value: "70%", source_type: "ai_generated" }],
  confirmation_status: "pending"
};

const aiResult = {
  product_name: "AI 识别名称",
  category: "护肤精华",
  spec: "50ml",
  core_selling_points: ["AI 舒缓卖点"],
  functions: ["AI 舒缓", "AI 补水"],
  ingredients: [{ name: "AI 成分", benefit: "AI 说明" }],
  target_users: ["AI 人群"],
  usage_method: ["AI 用法"],
  authority_assets: ["AI 资质"],
  effect_claims: [{ claim: "AI 数据", value: "92%", source_type: "ai_generated" }],
  confirmation_status: "pending"
};

const merged = mergeProductInfoWithManualPriority(current, aiResult, ["product_name", "core_selling_points"]);

assert.equal(merged.product_name, "手填精华名称");
assert.deepEqual(merged.core_selling_points, ["手填舒缓卖点"]);
assert.deepEqual(merged.functions, ["AI 舒缓", "AI 补水"]);
assert.deepEqual(merged.ingredients, [{ name: "AI 成分", benefit: "AI 说明" }]);
assert.equal(merged.spec, "50ml");

const emptyManual = applyProductInfoDraft(current, "product_name", "");
const filledFromAi = mergeProductInfoWithManualPriority(emptyManual, aiResult, ["product_name"]);

assert.equal(filledFromAi.product_name, "AI 识别名称");

console.log("Product info merge checks passed.");
