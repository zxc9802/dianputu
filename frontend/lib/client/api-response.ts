export class MainAppRedirectError extends Error {
  redirectUrl: string;

  constructor(redirectUrl: string) {
    super("Redirecting to main site");
    this.name = "MainAppRedirectError";
    this.redirectUrl = redirectUrl;
  }
}

type ErrorPayload = {
  error?: unknown;
  message?: unknown;
  detail?: unknown;
  redirectUrl?: unknown;
};

export async function readJsonSafely<T = unknown>(response: Response): Promise<T | null> {
  try {
    return await response.json() as T;
  } catch {
    return null;
  }
}

function readRedirectUrl(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return "";
  }

  const { redirectUrl, detail } = payload as ErrorPayload;
  if (typeof redirectUrl === "string" && redirectUrl.trim()) {
    return redirectUrl.trim();
  }
  if (detail && typeof detail === "object") {
    const nestedRedirectUrl = (detail as ErrorPayload).redirectUrl;
    if (typeof nestedRedirectUrl === "string" && nestedRedirectUrl.trim()) {
      return nestedRedirectUrl.trim();
    }
  }
  return "";
}

export function extractApiErrorMessage(payload: unknown, fallbackMessage: string) {
  if (payload && typeof payload === "object") {
    const { error, message, detail } = payload as ErrorPayload;
    if (typeof error === "string" && error.trim()) {
      return error;
    }
    if (typeof message === "string" && message.trim()) {
      return message;
    }
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }

  return fallbackMessage;
}

export function redirectToMainAppIfNeeded(response: Response, payload: unknown) {
  if (response.status !== 401 || typeof window === "undefined") {
    return false;
  }

  const redirectUrl = readRedirectUrl(payload);
  if (redirectUrl) {
    window.location.href = redirectUrl;
    throw new MainAppRedirectError(redirectUrl);
  }

  return false;
}
