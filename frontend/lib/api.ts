import { DEFAULT_MODULES, DEMO_MODEL_CONFIG, STYLE_OPTIONS } from "./constants";
import { MainAppRedirectError, extractApiErrorMessage, readJsonSafely, redirectToMainAppIfNeeded } from "./client/api-response";
import type { GenerationMode, MaterialPayload, ModuleConfig, ProductInfo, PublicModelConfig, StyleOption } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function requestJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 8000);
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    signal: controller.signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  }).finally(() => window.clearTimeout(timeout));
  const payload = await readJsonSafely<T>(response);
  redirectToMainAppIfNeeded(response, payload);
  if (!response.ok) {
    throw new Error(extractApiErrorMessage(payload, `API request failed: ${response.status}`));
  }
  return payload as T;
}

async function requestBlob(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<Blob> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 180000);
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    signal: controller.signal,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  }).finally(() => window.clearTimeout(timeout));
  if (!response.ok) {
    const payload = await readJsonSafely(response);
    redirectToMainAppIfNeeded(response, payload);
    throw new Error(extractApiErrorMessage(payload, `API request failed: ${response.status}`));
  }
  return response.blob();
}

function rethrowMainAppRedirect(error: unknown) {
  if (error instanceof MainAppRedirectError) {
    throw error;
  }
}

export async function fetchModelConfig(): Promise<PublicModelConfig> {
  try {
    return await requestJson<PublicModelConfig>("/api/models/config");
  } catch (error) {
    rethrowMainAppRedirect(error);
    return DEMO_MODEL_CONFIG;
  }
}

export async function fetchProjectDefaults(): Promise<{
  product_info?: ProductInfo;
  styles: StyleOption[];
  modules: ModuleConfig[];
}> {
  try {
    return await requestJson("/api/projects/defaults");
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      styles: STYLE_OPTIONS,
      modules: DEFAULT_MODULES
    };
  }
}

export async function generateImages(
  moduleIds: string[],
  styleId: string,
  productInfo?: ProductInfo,
  referenceImages: string[] = [],
  promotionInfo = "",
  platformSize = "",
  styleReferenceImages: string[] = [],
  customStyle?: StyleOption,
  imageModelId = "",
  generationMode: GenerationMode = "reference_generate"
) {
  try {
    const { job_id: jobId } = await createGenerateImageJob(
      moduleIds,
      styleId,
      productInfo,
      referenceImages,
      promotionInfo,
      platformSize,
      styleReferenceImages,
      customStyle,
      imageModelId,
      generationMode
    );
    return await pollGenerateImageJob(jobId);
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      images: [],
      errors: [error instanceof Error ? error.message : "前端请求后端生成接口失败。"]
    };
  }
}

type GenerateImagesResult = {
  source: string;
  images: Array<{ module_id: string; url: string }>;
  errors?: string[];
};

type GenerateImageJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
  result?: GenerateImagesResult;
};

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function createGenerateImageJob(
  moduleIds: string[],
  styleId: string,
  productInfo?: ProductInfo,
  referenceImages: string[] = [],
  promotionInfo = "",
  platformSize = "",
  styleReferenceImages: string[] = [],
  customStyle?: StyleOption,
  imageModelId = "",
  generationMode: GenerationMode = "reference_generate"
) {
  return requestJson<{ job_id: string }>("/api/projects/generate/jobs", {
    method: "POST",
    body: JSON.stringify({
      module_ids: moduleIds,
      style_id: styleId,
      product_info: productInfo,
      reference_images: referenceImages,
      style_reference_images: styleReferenceImages,
      custom_style: customStyle,
      promotion_info: promotionInfo,
      platform_size: platformSize,
      image_model_id: imageModelId,
      generation_mode: generationMode
    }),
    timeoutMs: 15000
  });
}

export async function fetchGenerateImageJob(jobId: string) {
  return requestJson<GenerateImageJobStatus>(`/api/projects/generate/jobs/${jobId}`, { timeoutMs: 15000 });
}

export async function pollGenerateImageJob(jobId: string, timeoutMs = 600000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt <= timeoutMs) {
    const job = await fetchGenerateImageJob(jobId);
    if (job.status === "done") {
      if (!job.result) {
        throw new Error("图片生成任务完成但没有返回结果");
      }
      return job.result;
    }
    if (job.status === "error") {
      throw new Error(job.error || job.message || "图片生成任务失败");
    }
    await sleep(3000);
  }
  throw new Error("图片生成任务超时，请稍后重试");
}

export async function planAiCustomStyle(productInfo?: ProductInfo, productImages: MaterialPayload[] = []) {
  try {
    return await requestJson<{ source: string; style?: StyleOption; error?: string }>("/api/projects/plan-style", {
      method: "POST",
      body: JSON.stringify({
        product_info: productInfo,
        product_images: productImages
      }),
      timeoutMs: 180000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 风格规划请求失败"
    };
  }
}

export async function generateAiCustomStyleSample(style: StyleOption, productInfo?: ProductInfo) {
  try {
    return await requestJson<{ source: string; style?: StyleOption; error?: string }>("/api/projects/plan-style-sample", {
      method: "POST",
      body: JSON.stringify({
        style,
        product_info: productInfo
      }),
      timeoutMs: 600000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 风格样例图请求失败"
    };
  }
}

export async function editGeneratedImage(imageUrl: string, instruction: string, platformSize = "", imageModelId = "") {
  try {
    return await requestJson<{ source: string; url?: string; error?: string }>("/api/projects/edit-image", {
      method: "POST",
      body: JSON.stringify({
        image_url: imageUrl,
        instruction,
        platform_size: platformSize,
        image_model_id: imageModelId
      }),
      timeoutMs: 600000
    });
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 微调请求失败"
    };
  }
}

export async function analyzeUploadedMaterials(materials: MaterialPayload[]) {
  try {
    return await requestJson<{ source: string; product_info?: ProductInfo; raw?: string; error?: string }>(
      "/api/projects/analyze-materials",
      {
        method: "POST",
        body: JSON.stringify({ materials }),
        timeoutMs: 180000
      }
    );
  } catch (error) {
    rethrowMainAppRedirect(error);
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 解析请求失败"
    };
  }
}

type ComposeImageInput = Array<{ module_id: string; module_name: string; url: string }>;
type ComposeJobStatus = {
  status: "pending" | "running" | "done" | "error";
  stage: string;
  current: number;
  total: number;
  message: string;
  error?: string;
};

export async function composeLongImage(
  images: ComposeImageInput
) {
  return requestBlob("/api/projects/compose-long-image", {
    method: "POST",
    body: JSON.stringify({ images }),
    timeoutMs: 600000
  });
}

export async function createComposeLongImageJob(images: ComposeImageInput) {
  return requestJson<{ job_id: string }>("/api/projects/compose-long-image/jobs", {
    method: "POST",
    body: JSON.stringify({ images }),
    timeoutMs: 600000
  });
}

export async function prepareComposeLongImageSources(images: ComposeImageInput) {
  return requestJson<{ images: ComposeImageInput }>("/api/projects/compose-long-image/prepare", {
    method: "POST",
    body: JSON.stringify({ images }),
    timeoutMs: 600000
  });
}

export async function fetchComposeLongImageJob(jobId: string) {
  return requestJson<ComposeJobStatus>(`/api/projects/compose-long-image/jobs/${jobId}`, { timeoutMs: 600000 });
}

export async function downloadComposeLongImageJob(jobId: string) {
  return requestBlob(`/api/projects/compose-long-image/jobs/${jobId}/download`, { timeoutMs: 600000 });
}

export async function downloadImage(url: string, filename: string) {
  return requestBlob("/api/projects/download-image", {
    method: "POST",
    body: JSON.stringify({ url, filename }),
    timeoutMs: 600000
  });
}
