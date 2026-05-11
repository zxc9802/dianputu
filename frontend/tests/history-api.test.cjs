const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const ts = require("typescript");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "lib", "historyApi.ts");
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

async function loadHistoryApi({ fetch }) {
  const localStorage = createLocalStorage({
    "detail-image-agent-history:user-1": JSON.stringify([
      {
        id: "remote-1",
        product_name: "Stale local copy",
        category: "护肤品",
        style_id: "space_repair",
        style_name: "太空修护风",
        platform_id: "tmall",
        thumbnail: "",
        image_count: 15,
        state: {},
        created_at: "2026-05-09T00:43:00.000Z",
        updated_at: "2026-05-09T00:43:00.000Z"
      }
    ])
  });
  const sandbox = {
    exports: {},
    module: { exports: {} },
    process: { env: {} },
    window: {
      localStorage,
      setTimeout,
      clearTimeout
    },
    AbortController,
    fetch,
    require(request) {
      if (request === "./types") return {};
      if (request === "@/lib/client/api-response" || request === "./client/api-response") {
        class MainAppRedirectError extends Error {}
        return {
          MainAppRedirectError,
          extractApiErrorMessage: () => "request failed",
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
  return { historyApi: sandbox.module.exports, localStorage };
}

async function run() {
  const requests = [];
  const { historyApi, localStorage } = await loadHistoryApi({
    fetch: async (url, init = {}) => {
      requests.push({ url, init });
      if (url.endsWith("/api/session")) {
        return new TestResponse({
          data: { session: { user: { id: "user-1" } } }
        });
      }
      if (url.endsWith("/api/history/remote-1") && init.method === "DELETE") {
        return new TestResponse({ deleted: true });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }
  });

  const deleted = await historyApi.deleteHistoryRecord("remote-1");

  assert.equal(deleted, true);
  assert.equal(requests.filter((request) => request.url.endsWith("/api/history/remote-1")).length, 1);
  assert.deepEqual(JSON.parse(localStorage.getItem("detail-image-agent-history:user-1")), []);
}

run().then(
  () => console.log("History API checks passed."),
  (error) => {
    console.error(error);
    process.exitCode = 1;
  }
);
