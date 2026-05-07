import { DEFAULT_MODULES, DEMO_MODEL_CONFIG, STYLE_OPTIONS } from "./constants";
import type { MaterialPayload, ModuleConfig, ProductInfo, PublicModelConfig, StyleOption } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function requestJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 8000);
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  }).finally(() => window.clearTimeout(timeout));
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function requestBlob(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<Blob> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 180000);
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...fetchInit,
    signal: controller.signal,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  }).finally(() => window.clearTimeout(timeout));
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.blob();
}

export async function fetchModelConfig(): Promise<PublicModelConfig> {
  try {
    return await requestJson<PublicModelConfig>("/api/models/config");
  } catch {
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
  } catch {
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
  customStyle?: StyleOption
) {
  try {
    return await requestJson<{ source: string; images: Array<{ module_id: string; url: string }>; errors?: string[] }>("/api/projects/generate", {
      method: "POST",
      body: JSON.stringify({
        module_ids: moduleIds,
        style_id: styleId,
        product_info: productInfo,
        reference_images: referenceImages,
        style_reference_images: styleReferenceImages,
        custom_style: customStyle,
        promotion_info: promotionInfo,
        platform_size: platformSize
      }),
      timeoutMs: 600000
    });
  } catch {
    return {
      source: "demo",
      images: moduleIds.map((moduleId) => ({ module_id: moduleId, url: "/assets/generated-cica-asset-sheet.png" })),
      errors: ["前端请求后端生成接口失败，已使用本地演示图兜底。"]
    };
  }
}

export async function planAiCustomStyle(productInfo?: ProductInfo, category = "", brandColors: string[] = []) {
  try {
    return await requestJson<{ source: string; style?: StyleOption; error?: string }>("/api/projects/plan-style", {
      method: "POST",
      body: JSON.stringify({
        product_info: productInfo,
        category,
        brand_colors: brandColors
      }),
      timeoutMs: 180000
    });
  } catch (error) {
    return {
      source: "error",
      error: error instanceof Error ? error.message : "AI 风格规划请求失败"
    };
  }
}

export async function editGeneratedImage(imageUrl: string, instruction: string, platformSize = "") {
  try {
    return await requestJson<{ source: string; url?: string; error?: string }>("/api/projects/edit-image", {
      method: "POST",
      body: JSON.stringify({
        image_url: imageUrl,
        instruction,
        platform_size: platformSize
      }),
      timeoutMs: 600000
    });
  } catch (error) {
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

export async function fetchComposeLongImageJob(jobId: string) {
  return requestJson<ComposeJobStatus>(`/api/projects/compose-long-image/jobs/${jobId}`, { timeoutMs: 600000 });
}

export async function downloadComposeLongImageJob(jobId: string) {
  return requestBlob(`/api/projects/compose-long-image/jobs/${jobId}/download`, { timeoutMs: 600000 });
}
