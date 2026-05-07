import type { PersistedProjectState } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type HistoryMeta = {
  id: string;
  product_name: string;
  category: string;
  style_id: string;
  style_name: string;
  platform_id: string;
  thumbnail: string;
  image_count: number;
  created_at: string;
  updated_at: string;
};

export type HistoryDetail = HistoryMeta & {
  state: PersistedProjectState;
};

async function requestJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 10000);
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

export async function fetchHistoryList(limit = 30, offset = 0): Promise<HistoryMeta[]> {
  try {
    const result = await requestJson<{ items: HistoryMeta[] }>(
      `/api/history?limit=${limit}&offset=${offset}`
    );
    return result.items;
  } catch {
    return [];
  }
}

export async function fetchHistoryDetail(id: string): Promise<HistoryDetail | null> {
  try {
    return await requestJson<HistoryDetail>(`/api/history/${id}`);
  } catch {
    return null;
  }
}

export async function saveHistory(record: {
  id?: string;
  product_name: string;
  category: string;
  style_id: string;
  style_name: string;
  platform_id: string;
  thumbnail: string;
  image_count: number;
  state: PersistedProjectState;
}): Promise<HistoryMeta | null> {
  try {
    return await requestJson<HistoryMeta>("/api/history", {
      method: "POST",
      body: JSON.stringify(record),
      timeoutMs: 15000
    });
  } catch {
    return null;
  }
}

export async function deleteHistoryRecord(id: string): Promise<boolean> {
  try {
    await requestJson<{ deleted: boolean }>(`/api/history/${id}`, {
      method: "DELETE"
    });
    return true;
  } catch {
    return false;
  }
}
