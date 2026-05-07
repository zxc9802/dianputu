const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), "utf8");
}

function assertIncludes(file, needle, message) {
  assert.ok(read(file).includes(needle), `${file}: ${message}`);
}

function assertNotIncludes(file, needle, message) {
  assert.ok(!read(file).includes(needle), `${file}: ${message}`);
}

assertIncludes("components/UploadStep.tsx", 'type="file"', "upload step must include a native file input");
assertIncludes("components/UploadStep.tsx", "onDrop", "upload step must support drag and drop");
assertIncludes("components/UploadStep.tsx", "uploadedFiles", "upload step must render selected file state");
assertIncludes("components/UploadStep.tsx", "product-image-upload", "upload step must expose a separate product image input");
assertIncludes("components/UploadStep.tsx", "report-file-upload", "upload step must expose a separate report input");
assertIncludes("components/UploadStep.tsx", "document-file-upload", "upload step must expose a separate document input");
assertIncludes("components/UploadStep.tsx", "onAnalyze", "upload step must trigger AI material analysis");
assertIncludes("components/UploadStep.tsx", "手动补充信息（可不填）", "upload sidebar must expose optional manual product fields");
assertIncludes("components/UploadStep.tsx", "onManualFieldChange", "upload sidebar must propagate manual field edits");
assertIncludes("components/UploadStep.tsx", "manualFieldKeys", "upload sidebar must show which fields are manually prioritized");
assertIncludes("app/page.tsx", "uploadedFiles={uploadedFiles}", "style step must receive uploaded file state");
assertIncludes("app/page.tsx", "onStyleFilesAdded={addUploadedFiles}", "style step must reuse the upload handler for reference images");
assertIncludes("app/page.tsx", "onStyleFileRemove", "style step must be able to remove uploaded reference images");
assertIncludes("lib/api.ts", "analyzeUploadedMaterials", "frontend API must send uploaded materials for AI analysis");
assertIncludes("lib/productInfo.ts", "mergeProductInfoWithManualPriority", "product info helper must preserve manual fields when AI returns data");
assertIncludes("app/page.tsx", "mergeProductInfoWithManualPriority", "page must merge AI analysis results without overwriting manual fields");
assertIncludes("lib/api.ts", "http://127.0.0.1:8000", "frontend API should default to the backend bind address");
assertIncludes("lib/api.ts", "AbortController", "frontend API requests must time out instead of leaving the app loading forever");
assertIncludes("lib/api.ts", "timeoutMs: 600000", "image generation must keep the request open long enough for real model output");
assertIncludes("lib/api.ts", "timeoutMs: 180000", "material analysis must keep the request open long enough for model output");

assertIncludes("components/ReviewStep.tsx", "textarea", "review step must allow editing extracted fields");
assertIncludes("components/ReviewStep.tsx", "onUpdateProductInfo", "review step must propagate edits to page state");
assertIncludes("components/ReviewStep.tsx", "confirmedFields", "review step must track field confirmation");
assertIncludes("components/ReviewStep.tsx", "暂无 AI 提炼结果", "review step must be empty until real AI extraction succeeds");
assertNotIncludes("app/page.tsx", "setProductInfo(defaults.product_info)", "page must not prefill review fields with demo product information");
assertIncludes("app/page.tsx", "hasAiProductInfo ? productInfo : null", "review step must render extracted fields only after a model result");
assertIncludes("app/page.tsx", 'result.source === "model" && result.product_info', "page must require a real model product_info before filling review fields");
assertNotIncludes("lib/api.ts", "DEFAULT_PRODUCT_INFO", "frontend API must not fall back to demo product information");
assertNotIncludes("lib/constants.ts", "DEFAULT_PRODUCT_INFO", "frontend constants must not ship demo product information");

assertIncludes("components/PreviewStep.tsx", "download", "preview step must expose downloadable outputs");
assertIncludes("components/PreviewStep.tsx", "groupedItems.detail.map", "preview step must render every generated detail image in the long preview");
assertNotIncludes("components/PreviewStep.tsx", "generatedImages[0]?.url", "preview step must not use only the first generated image as the full long preview");
assertIncludes("components/PreviewStep.tsx", "createComposeLongImageJob", "preview step must start backend JPEG composition for the full long image");
assertIncludes("components/PreviewStep.tsx", "fetchComposeLongImageJob", "preview step must poll backend JPEG composition progress");
assertIncludes("components/PreviewStep.tsx", "composeStatus", "preview step must show backend progress during composition");
assertIncludes("components/PreviewStep.tsx", "full-detail.jpg", "full long image export must download a JPG file");
assertNotIncludes("components/PreviewStep.tsx", "full-detail.svg", "full long image export must not download SVG");
assertIncludes("lib/api.ts", "/api/projects/compose-long-image", "frontend API must expose backend long image composition");
assertIncludes("app/page.tsx", "PROJECT_STATE_STORAGE_KEY", "page must define a storage key for preserving generated results");
assertIncludes("app/page.tsx", "localStorage", "page must persist generated results across reloads and step changes");
assertIncludes("app/page.tsx", "restored.generatedImages", "page must restore generated images from saved state");
assertIncludes("app/page.tsx", "window.location.hash", "page must restore active step from the URL hash");
assertIncludes("app/page.tsx", "hashchange", "page must stay in sync when the URL hash changes");
assertIncludes("app/page.tsx", "generationProgress", "page must track generation progress by image group");
assertIncludes("app/page.tsx", "promotionInfo", "page must persist campaign promotion text");
assertIncludes("lib/api.ts", "promotion_info", "frontend API must send campaign promotion text to backend generation");
assertIncludes("lib/api.ts", "style_reference_images", "frontend API must send uploaded style reference images separately");
assertIncludes("app/page.tsx", 'file.slot === "style_reference"', "page generation handler must collect style reference uploads");
assertIncludes("lib/types.ts", 'StyleSource = "preset" | "reference" | "ai_custom"', "frontend must model preset, reference image, and AI custom style as exclusive style sources");
assertIncludes("app/page.tsx", "styleSource === \"reference\" ? styleReferenceImages : []", "generation must only send style reference uploads when reference mode is selected");
assertIncludes("app/page.tsx", "请先上传并选择风格参考图", "reference mode generation must stop when no reference image is available");
assertNotIncludes("app/page.tsx", "go(\"style\")", "missing reference image must not kick users out of modules or preview during regeneration");
assertIncludes("app/page.tsx", "setStyleSource(\"preset\")", "preset style selection must leave reference style mode");
assertIncludes("app/page.tsx", "setStyleSource(\"reference\")", "reference style selection must leave preset style mode");
assertIncludes("components/StyleStep.tsx", "styleSource === \"preset\" && style.id === selectedStyleId", "preset cards must only be selected in preset style mode");
assertIncludes("components/StyleStep.tsx", "styleSource === \"reference\"", "style reference card must expose its own selected state");
assertIncludes("components/StyleStep.tsx", "onStyleReferenceSelect", "style step must expose a handler for selecting the uploaded reference style");
assertIncludes("lib/api.ts", "planAiCustomStyle", "frontend API must expose Gemini custom style planning");
assertIncludes("lib/api.ts", "/api/projects/plan-style", "frontend API must call the backend style planning endpoint");
assertIncludes("app/page.tsx", "customStyle", "page must store the Gemini-planned custom style");
assertIncludes("app/page.tsx", "planAiCustomStyle", "page must call Gemini only from the AI custom style action");
assertIncludes("app/page.tsx", "styleSource === \"ai_custom\" ? customStyle", "generation must send the selected AI custom style brief");
assertIncludes("components/StyleStep.tsx", "customStyle.asset", "AI custom style card must render the generated GPT image sample when available");
assertIncludes("components/StyleStep.tsx", "规划并生成样例", "AI custom style action must communicate that it creates a sample image");
assertIncludes("app/page.tsx", "WHITE_BACKGROUND_MODULE_IDS", "page must recognize white background modules");
assertIncludes("app/page.tsx", "白底图需要先上传产品图", "white background regeneration must stop when the original product image is unavailable");
assertIncludes("components/StyleStep.tsx", "AI 自定义风格", "style step must show an AI custom style option");
assertIncludes("components/StyleStep.tsx", "onPlanAiCustomStyle", "style step must expose a click handler for Gemini style planning");
assertIncludes("components/StyleStep.tsx", "让 AI 规划并生成样例", "style step must let the user explicitly trigger AI planning and sample generation");
assertIncludes("components/ModulesStep.tsx", "促销方式", "modules step must let users enter campaign promotion text");
assertIncludes("components/ModulesStep.tsx", "campaign", "modules step must expose campaign image generation group");
assertIncludes("components/PreviewStep.tsx", "campaign", "preview step must expose campaign image results");
assertIncludes("components/ModulesStep.tsx", "disabled={activeProgress.isGenerating}", "generation button must prevent duplicate submissions per image group");
assertIncludes("app/page.tsx", "runningModuleIds", "page generation progress must track every concurrently running module");
assertIncludes("components/ModulesStep.tsx", "(activeProgress.runningModuleIds ?? []).includes(module.id)", "modules step must show every concurrently running module as generating and tolerate restored progress state");
assertIncludes("components/PreviewStep.tsx", "(activeProgress.runningModuleIds ?? []).includes(module.id)", "preview step must show every concurrently running module as generating and tolerate restored progress state");
assertIncludes("app/page.tsx", "targetModuleId", "page generation handler must support a single target module");
assertIncludes("components/ModulesStep.tsx", "stopPropagation", "per-module generation buttons must not toggle module selection");
assertIncludes("components/ModulesStep.tsx", "重新生成", "modules step must expose regenerate actions");
assertIncludes("components/PreviewStep.tsx", "onGenerateModule", "preview step must trigger per-module regeneration");
assertIncludes("components/ModulesStep.tsx", "role=\"button\"", "module rows must remain keyboard-accessible after adding nested action buttons");
assertIncludes("components/ModulesStep.tsx", "preventDefault", "keyboard module toggles must not scroll the page");
assertIncludes("components/PreviewStep.tsx", "重新生成", "preview step must expose regenerate actions");

console.log("Static UI contract checks passed.");
