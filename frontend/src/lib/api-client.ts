import { API_BASE_URL, DEFAULT_TIMEOUT_MS } from "./constants";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type ApiRequestOptions<TBody = unknown> = {
  path: string;
  method?: HttpMethod;
  body?: TBody;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  timeoutMs?: number;
};

export class ApiError extends Error {
  status: number;
  details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function withTimeout(
  promise: Promise<Response>,
  timeoutMs: number
): Promise<Response> {
  if (timeoutMs <= 0) return promise;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await promise;
  } finally {
    clearTimeout(timer);
  }
}

export async function apiRequest<TResponse, TBody = unknown>({
  path,
  method = "GET",
  body,
  headers = {},
  signal,
  timeoutMs = DEFAULT_TIMEOUT_MS,
}: ApiRequestOptions<TBody>): Promise<TResponse> {
  const url = `${API_BASE_URL}${path}`;

  const requestInit: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    signal,
  };

  if (body !== undefined) {
    requestInit.body = JSON.stringify(body);
  }

  try {
    const response = await withTimeout(fetch(url, requestInit), timeoutMs);

    if (!response.ok) {
      const errorDetails = await safeParseJson(response);
      throw new ApiError(
        `Request failed with status ${response.status}`,
        response.status,
        errorDetails
      );
    }

    return (await safeParseJson(response)) as TResponse;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if ((error as Error).name === "AbortError") {
      throw new ApiError(
        `Request aborted or timed out after ${timeoutMs}ms`,
        499
      );
    }

    throw new ApiError(
      `Network error: ${(error as Error).message}`,
      0,
      error
    );
  }
}

async function safeParseJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}


