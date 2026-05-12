const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib", "compliance.ts");
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
    if (request === "./types") return {};
    throw new Error(`Unexpected require: ${request}`);
  }
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

const { complianceIssueLocationLabel } = sandbox.module.exports;

assert.equal(
  complianceIssueLocationLabel({ term: "100%", location: { source_type: "image_review", image_index: 1 } }),
  "第 2 张"
);
assert.equal(
  complianceIssueLocationLabel({ term: "治愈", location: { source_type: "text_layer", module_id: "hero" } }),
  ""
);

console.log("Compliance helper checks passed.");
