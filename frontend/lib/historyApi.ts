import type { PersistedProjectState } from "./types";
import { MainAppRedirectError, extractApiErrorMessage, readJsonSafely, redirectToMainAppIfNeeded } from "./client/api-response";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const LOCAL_HISTORY_STORAGE_KEY = "detail-image-agent-history";
const LOCAL_DEV_HISTORY_USER_ID = "detail-image-agent-local-dev-user";

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

let currentHistoryUserIdPromise: Promise<string> | null = null;

export function getScopedLocalHistoryStorageKey(userId: string) {
  return `detail-image-agent-history:${userId || LOCAL_DEV_HISTORY_USER_ID}`;
}

async function fetchCurrentHistoryUserId(): Promise<string> {
  if (currentHistoryUserIdPromise) {
    return currentHistoryUserIdPromise;
  }

  currentHistoryUserIdPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/session`, {
        method: "GET",
        cache: "no-store",
        credentials: "include"
      });
      const payload = await readJsonSafely<{
        data?: { session?: { user?: { id?: unknown } | null } | null };
      }>(response);
      redirectToMainAppIfNeeded(response, payload);
      if (!response.ok) {
        throw new Error(extractApiErrorMessage(payload, "读取当前登录状态失败"));
      }

      const userId = payload?.data?.session?.user?.id;
      return typeof userId === "string" && userId.trim() ? userId.trim() : LOCAL_DEV_HISTORY_USER_ID;
    } catch (error) {
      if (error instanceof MainAppRedirectError) {
        throw error;
      }
      currentHistoryUserIdPromise = null;
      return LOCAL_DEV_HISTORY_USER_ID;
    }
  })();

  return currentHistoryUserIdPromise;
}

function readLocalHistory(userId: string): LocalHistoryRecord[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(getScopedLocalHistoryStorageKey(userId)) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeLocalHistory(userId: string, records: LocalHistoryRecord[]) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(getScopedLocalHistoryStorageKey(userId), JSON.stringify(records.slice(0, 50)));
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

function fetchLocalHistoryList(userId: string, limit = 30, offset = 0): HistoryMeta[] {
  return readLocalHistory(userId)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(offset, offset + limit)
    .map(historyMeta);
}

function getLocalHistoryDetail(userId: string, id: string): HistoryDetail | null {
  return readLocalHistory(userId).find((record) => record.id === id) ?? null;
}

function saveLocalHistory(userId: string, record: {
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
  const records = readLocalHistory(userId);
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
  writeLocalHistory(userId, [saved, ...records.filter((item) => item.id !== saved.id)]);
  return historyMeta(saved);
}

function removeLocalHistory(userId: string, id: string) {
  writeLocalHistory(userId, readLocalHistory(userId).filter((record) => record.id !== id));
}

async function requestJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), init?.timeoutMs ?? 10000);
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

export async function fetchHistoryList(limit = 30, offset = 0): Promise<HistoryMeta[]> {
  const userId = await fetchCurrentHistoryUserId();
  const localItems = fetchLocalHistoryList(userId, limit, offset);
  try {
    const result = await requestJson<{ items: HistoryMeta[] }>(
      `/api/history?limit=${limit}&offset=${offset}`
    );
    const localIds = new Set(localItems.map((item) => item.id));
    return [...localItems, ...result.items.filter((item) => !localIds.has(item.id))].slice(0, limit);
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    return localItems;
  }
}

export async function fetchHistoryDetail(id: string): Promise<HistoryDetail | null> {
  const userId = await fetchCurrentHistoryUserId();
  if (id.startsWith("local-")) {
    return getLocalHistoryDetail(userId, id);
  }
  try {
    return await requestJson<HistoryDetail>(`/api/history/${id}`);
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    return getLocalHistoryDetail(userId, id);
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
  const userId = await fetchCurrentHistoryUserId();
  try {
    return await requestJson<HistoryMeta>("/api/history", {
      method: "POST",
      body: JSON.stringify(record),
      timeoutMs: 15000
    });
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    return saveLocalHistory(userId, record);
  }
}

export async function deleteHistoryRecord(id: string): Promise<boolean> {
  const userId = await fetchCurrentHistoryUserId();
  if (id.startsWith("local-")) {
    removeLocalHistory(userId, id);
    return true;
  }
  try {
    await requestJson<{ deleted: boolean }>(`/api/history/${id}`, {
      method: "DELETE"
    });
    removeLocalHistory(userId, id);
    return true;
  } catch (error) {
    if (error instanceof MainAppRedirectError) {
      throw error;
    }
    const before = readLocalHistory(userId);
    const after = before.filter((record) => record.id !== id);
    writeLocalHistory(userId, after);
    return after.length !== before.length;
  }
}
