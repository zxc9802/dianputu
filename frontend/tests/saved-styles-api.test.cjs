const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib", "api.ts");
const source = fs.readFileSync(sourcePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2019,
    esModuleInterop: true
  }
}).outputText;

function createLocalStorage(initialEntries = {}) {
  const store = new Map(Object.entries(initialEntries));
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    },
    removeItem(key) {
      store.delete(key);
    }
  };
}

class TestResponse {
  constructor(body, status = 200) {
    this.body = body;
    this.status = status;
    this.ok = status >= 200 && status < 300;
  }

  async json() {
    return this.body;
  }
}

function loadApi({ fetch }) {
  const localStorage = createLocalStorage();
  const sandbox = {
    exports: {},
    module: { exports: {} },
    process: { env: {} },
    window: {
      localStorage,
      location: { hostname: "localhost" },
      setTimeout,
      clearTimeout
    },
    crypto: {
      randomUUID: () => "local-style-id"
    },
    AbortController,
    fetch,
    require(request) {
      if (request === "./constants") return { DEFAULT_MODULES: [], DEMO_MODEL_CONFIG: {}, STYLE_OPTIONS: [] };
      if (request === "./types") return {};
      if (request === "./client/api-response" || request === "@/lib/client/api-response") {
        class MainAppRedirectError extends Error {}
        return {
          MainAppRedirectError,
          extractApiErrorMessage: (payload, fallback) => payload?.detail || payload?.message || fallback,
          async readJsonSafely(response) {
            return response.json();
          },
          redirectToMainAppIfNeeded() {}
        };
      }
      throw new Error(`Unexpected require: ${request}`);
    }
  };
  sandbox.exports = sandbox.module.exports;
  vm.runInNewContext(compiled, sandbox, { filename: sourcePath });
  return { api: sandbox.module.exports, localStorage };
}

async function run() {
  const requests = [];
  const { api, localStorage } = loadApi({
    fetch: async (url, init = {}) => {
      requests.push({ url, init });
      if (url.endsWith("/api/session")) {
        return new TestResponse({
          data: { session: { user: { id: "user-1" } } }
        });
      }
      if (url.endsWith("/api/styles/saved") && init.method === "POST") {
        return new TestResponse({ detail: "database not configured" }, 503);
      }
      if (url.endsWith("/api/styles/saved")) {
        return new TestResponse({ detail: "database not configured" }, 503);
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }
  });

  const saved = await api.saveSavedStyle(
    { id: "style_reference", name: "旧名", keywords: ["冷感"], primary_color: "#A8DDE8", asset: "" },
    "冷萃晶透风"
  );
  assert.equal(saved.id, "local-local-style-id");
  assert.equal(saved.name, "冷萃晶透风");
  assert.equal(saved.style.name, "冷萃晶透风");

  const list = await api.fetchSavedStyles();
  assert.equal(list.items.length, 1);
  assert.equal(list.items[0].name, "冷萃晶透风");

  await api.deleteSavedStyle(saved.id);
  assert.deepEqual(JSON.parse(localStorage.getItem("detail-image-agent-saved-styles:user-1")), []);
  assert.equal(requests.filter((request) => request.url.endsWith("/api/styles/saved")).length, 2);
}

run().then(
  () => console.log("Saved styles API fallback checks passed."),
  (error) => {
    console.error(error);
    process.exitCode = 1;
  }
);
