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

const { applyProductInfoDraft, createEmptyProductInfo, detailModuleFieldKey, mergeProductInfoWithManualPriority, productInfoFieldsForDetailLayout, productInfoValueFor, productInfoWithDetailLayoutFields } = sandbox.module.exports;

assert.equal(createEmptyProductInfo().category, "", "empty product info must not assume a fixed skincare category");

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

const evidenceFields = productInfoFieldsForDetailLayout("detail_evidence_chain_16");
const standardFields = productInfoFieldsForDetailLayout("detail_standard_conversion_10");

assert.equal(evidenceFields.filter((field) => field.key.startsWith("detail_module:")).length, 16, "evidence layout must expose one manual field per detail screen");
assert.equal(standardFields.filter((field) => field.key.startsWith("detail_module:")).length, 10, "standard layout must expose one manual field per detail screen");
assert.ok(evidenceFields.some((field) => field.key === detailModuleFieldKey("detail_ec_pain_matrix") && field.label === "第 2 屏：痛点放大"), "evidence layout must collect pain screen notes");
assert.ok(evidenceFields.some((field) => field.key === detailModuleFieldKey("detail_ec_auxiliary_validation") && field.label === "第 12 屏：辅助功效验证"), "evidence layout must collect auxiliary validation screen notes");
assert.ok(standardFields.some((field) => field.key === detailModuleFieldKey("product_info") && field.label === "第 10 屏：产品信息"), "standard layout should keep the tenth product info screen");

const competitorFieldKey = detailModuleFieldKey("detail_ec_competitor_comparison");
const manualEvidenceBrief = applyProductInfoDraft(current, competitorFieldKey, "普通竞品厚重闷肤 / 本品清爽不黏腻");
assert.deepEqual(JSON.parse(JSON.stringify(manualEvidenceBrief.detail_layout_brief.modules[0].manual_notes)), ["普通竞品厚重闷肤", "本品清爽不黏腻"]);
assert.match(productInfoValueFor(manualEvidenceBrief, competitorFieldKey), /普通竞品厚重闷肤/);

const mergedEvidenceBrief = mergeProductInfoWithManualPriority(
  manualEvidenceBrief,
  { ...aiResult, detail_layout_brief: { modules: [{ module_id: "detail_ec_competitor_comparison", required_content: ["AI 竞品对比"] }] } },
  [competitorFieldKey]
);
assert.deepEqual(JSON.parse(JSON.stringify(mergedEvidenceBrief.detail_layout_brief.modules[0].manual_notes)), ["普通竞品厚重闷肤", "本品清爽不黏腻"]);

const expandedEvidenceInfo = productInfoWithDetailLayoutFields(
  {
    ...current,
    detail_layout_brief: {
      modules: [
        {
          module_id: "detail_ec_competitor_comparison",
          required_content: ["普通竞品厚重闷肤", "本品清爽不黏腻"],
          manual_notes: ["普通竞品厚重闷肤", "本品清爽不黏腻"]
        }
      ]
    }
  },
  "detail_evidence_chain_16"
);
assert.equal(expandedEvidenceInfo.detail_layout_brief.modules.length, 16, "confirmed evidence-chain info must contain every screen module");
assert.ok(expandedEvidenceInfo.detail_layout_brief.modules.every((module) => module.required_content?.length), "each evidence-chain screen must have generation content");
assert.deepEqual(
  JSON.parse(JSON.stringify(expandedEvidenceInfo.detail_layout_brief.modules.find((module) => module.module_id === "detail_ec_competitor_comparison").manual_notes)),
  ["普通竞品厚重闷肤", "本品清爽不黏腻"]
);

const analysisExpandedInfo = productInfoWithDetailLayoutFields(
  {
    ...current,
    product_name: "AQUALUXE 水漾舒缓精华水",
    core_selling_points: ["清爽补水", "舒缓泛红"],
    functions: ["补水", "舒缓"],
    ingredients: [{ name: "透明质酸钠", benefit: "帮助提升水润肤感" }],
    detail_layout_brief: {
      layout_id: "detail_evidence_chain_16",
      module_focus: {
        detail_ec_competitor_comparison: ["普通竞品厚重黏腻", "本品清爽不黏腻"]
      }
    }
  },
  "detail_evidence_chain_16"
);
assert.equal(analysisExpandedInfo.detail_layout_brief.modules.length, 16, "analysis result should immediately expand to sixteen review rows");
assert.ok(analysisExpandedInfo.detail_layout_brief.modules.every((module) => module.required_content?.length), "analysis-expanded rows should not be blank");
assert.match(productInfoValueFor(analysisExpandedInfo, detailModuleFieldKey("detail_ec_hero")), /清爽补水|AQUALUXE/);

const emptyManual = applyProductInfoDraft(current, "product_name", "");
const filledFromAi = mergeProductInfoWithManualPriority(emptyManual, aiResult, ["product_name"]);

assert.equal(filledFromAi.product_name, "AI 识别名称");

assert.equal(
  productInfoValueFor(
    {
      ...current,
      ingredients: [
        { name: "透明质酸钠", benefit: "帮助提升水润肤感" },
        { name: "烟酰胺", benefit: "帮助提亮肤色观感" }
      ]
    },
    "ingredients"
  ),
  "透明质酸钠：帮助提升水润肤感 / 烟酰胺：帮助提亮肤色观感"
);

const ingredientDraft = applyProductInfoDraft(
  current,
  "ingredients",
  "透明质酸钠：帮助提升水润肤感 / 烟酰胺 - 帮助提亮肤色观感 / 积雪草提取物"
);

assert.deepEqual(JSON.parse(JSON.stringify(ingredientDraft.ingredients)), [
  { name: "透明质酸钠", benefit: "帮助提升水润肤感" },
  { name: "烟酰胺", benefit: "帮助提亮肤色观感" },
  { name: "积雪草提取物", benefit: "帮助舒缓干燥不适" }
]);

console.log("Product info merge checks passed.");
