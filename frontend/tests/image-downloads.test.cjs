const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib", "imageDownloads.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019
  }
}).outputText;

let fetchCount = 0;
const sandbox = {
  atob,
  Blob,
  Uint8Array,
  exports: {},
  module: { exports: {} },
  fetch: async () => {
    fetchCount += 1;
    throw new Error("data URLs must not be fetched over the network");
  }
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled, sandbox, { filename: sourcePath });

const { fetchImageBlob, isDataImageUrl } = sandbox.module.exports;

async function run() {
  assert.equal(isDataImageUrl("data:image/png;base64,AAECAw=="), true);
  assert.equal(isDataImageUrl("https://example.com/image.png"), false);

  let proxyCount = 0;
  const blob = await fetchImageBlob("data:image/png;base64,AAECAw==", async () => {
    proxyCount += 1;
    throw new Error("base64 data must not be posted to the backend download proxy");
  });

  assert.equal(fetchCount, 0, "base64 image downloads must stay entirely in the browser");
  assert.equal(proxyCount, 0, "base64 image downloads must not call the backend proxy");
  assert.equal(blob.type, "image/png");
  assert.deepEqual([...new Uint8Array(await blob.arrayBuffer())], [0, 1, 2, 3]);

  console.log("Image download checks passed.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
