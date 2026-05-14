const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib", "modelSelection.ts");
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
    if (request === "./types" || request === "@/lib/types") return {};
    throw new Error(`Unexpected require: ${request}`);
  }
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

const { resolveInitialImageModelId } = sandbox.module.exports;

const modelConfig = {
  imageGeneration: {
    defaultOptionId: "fallback",
    options: [
      { id: "primary" },
      { id: "fallback" },
      { id: "gemini_flash_image" }
    ]
  }
};

assert.equal(
  resolveInitialImageModelId({
    restoredImageModelId: "primary",
    modelConfig,
    fallbackImageModelId: "fallback",
    persistedSchemaVersion: 2,
    currentSchemaVersion: 3
  }),
  "fallback",
  "stale restored model choices must migrate to the current backend default"
);

assert.equal(
  resolveInitialImageModelId({
    restoredImageModelId: "primary",
    modelConfig,
    fallbackImageModelId: "fallback",
    persistedSchemaVersion: 3,
    currentSchemaVersion: 3
  }),
  "primary",
  "current-schema restored model choices should still preserve the user's selection"
);

assert.equal(
  resolveInitialImageModelId({
    restoredImageModelId: "removed_model",
    modelConfig,
    fallbackImageModelId: "fallback",
    persistedSchemaVersion: 3,
    currentSchemaVersion: 3
  }),
  "fallback",
  "unknown restored model ids must fall back to the backend default"
);

console.log("Model selection checks passed.");
