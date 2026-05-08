import type { PersistedProjectState } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const LOCAL_HISTORY_STORAGE_KEY = "detail-image-agent-history";

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

type LocalHistoryRecord = HistoryDetail;

function readLocalHistory(): LocalHistoryRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(LOCAL_HISTORY_STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocalHistory(records: LocalHistoryRecord[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCAL_HISTORY_STORAGE_KEY, JSON.stringify(records.slice(0, 50)));
  } catch {
    // The main workspace still works if local persistence is unavailable.
  }
}

function createLocalHistoryId() {
  const randomPart = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`;
  return `local-${randomPart}`;
}

function historyMeta(record: HistoryDetail): HistoryMeta {
  const { state: _state, ...meta } = record;
  return meta;
}

function fetchLocalHistoryList(limit = 30, offset = 0): HistoryMeta[] {
  return readLocalHistory()
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(offset, offset + limit)
    .map(historyMeta);
}

function getLocalHistoryDetail(id: string): HistoryDetail | null {
  return readLocalHistory().find((record) => record.id === id) ?? null;
}

function saveLocalHistory(record: {
  id?: string;
  product_name: string;
  category: string;
  style_id: string;
  style_name: string;
  platform_id: string;
  thumbnail: string;
  image_count: number;
  state: PersistedProjectState;
}): HistoryMeta {
  const records = readLocalHistory();
  const existing = record.id ? records.find((item) => item.id === record.id) : null;
  const now = new Date().toISOString();
  const saved: HistoryDetail = {
    id: record.id || createLocalHistoryId(),
    product_name: record.product_name,
    category: record.category,
    style_id: record.style_id,
    style_name: record.style_name,
    platform_id: record.platform_id,
    thumbnail: record.thumbnail,
    image_count: record.image_count,
    state: record.state,
    created_at: existing?.created_at ?? now,
    updated_at: now
  };
  writeLocalHistory([saved, ...records.filter((item) => item.id !== saved.id)]);
  return historyMeta(saved);
}

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
  const localItems = fetchLocalHistoryList(limit, offset);
  try {
    const result = await requestJson<{ items: HistoryMeta[] }>(
      `/api/history?limit=${limit}&offset=${offset}`
    );
    const localIds = new Set(localItems.map((item) => item.id));
    return [...localItems, ...result.items.filter((item) => !localIds.has(item.id))].slice(0, limit);
  } catch {
    return localItems;
  }
}

export async function fetchHistoryDetail(id: string): Promise<HistoryDetail | null> {
  if (id.startsWith("local-")) {
    return getLocalHistoryDetail(id);
  }
  try {
    return await requestJson<HistoryDetail>(`/api/history/${id}`);
  } catch {
    return getLocalHistoryDetail(id);
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
    return saveLocalHistory(record);
  }
}

export async function deleteHistoryRecord(id: string): Promise<boolean> {
  if (id.startsWith("local-")) {
    writeLocalHistory(readLocalHistory().filter((record) => record.id !== id));
    return true;
  }
  try {
    await requestJson<{ deleted: boolean }>(`/api/history/${id}`, {
      method: "DELETE"
    });
    return true;
  } catch {
    const before = readLocalHistory();
    const after = before.filter((record) => record.id !== id);
    writeLocalHistory(after);
    return after.length !== before.length;
  }
}
