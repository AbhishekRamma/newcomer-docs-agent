// Typed client for the FastAPI service. Attaches the bearer token to every protected call;
// on a 401 it asks the auth layer to sign in again and throws, so callers never retry blindly.
import {
  type AskResponse,
  type HistoryPage,
  isAskResponse,
  isHistoryPage,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor() {
    super(401, "Your session has ended. Signing you in again…");
    this.name = "UnauthorizedError";
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  getToken: () => string | null | Promise<string | null>;
  onUnauthorized: () => void | Promise<void>;
  fetchImpl?: typeof fetch;
}

export interface ApiClient {
  ask(question: string): Promise<AskResponse>;
  listHistory(limit?: number, offset?: number): Promise<HistoryPage>;
  deleteHistory(id: number): Promise<void>;
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      if (typeof body.detail === "string") return body.detail;
    }
  } catch {
    // not JSON
  }
  return "";
}

function messageFor(status: number, detail: string): string {
  if (status === 503) return detail || "The service is unavailable right now. Please try again later.";
  if (status === 422) return "Please write a question between 3 and 500 characters.";
  if (status === 404) return "That entry no longer exists.";
  return `The server answered with an error (HTTP ${status}). ${detail}`.trim();
}

export function createApiClient(opts: ApiClientOptions): ApiClient {
  const base = opts.baseUrl.replace(/\/+$/, "");
  const doFetch = opts.fetchImpl ?? ((input, init) => fetch(input, init));

  async function request(path: string, init: RequestInit = {}): Promise<Response> {
    const token = await opts.getToken();
    if (!token) {
      await opts.onUnauthorized();
      throw new UnauthorizedError();
    }
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    if (init.body !== undefined) headers.set("Content-Type", "application/json");
    const res = await doFetch(`${base}${path}`, { ...init, headers });
    if (res.status === 401) {
      await opts.onUnauthorized();
      throw new UnauthorizedError();
    }
    if (!res.ok) throw new ApiError(res.status, messageFor(res.status, await errorDetail(res)));
    return res;
  }

  return {
    async ask(question) {
      const res = await request("/ask", { method: "POST", body: JSON.stringify({ question }) });
      const body: unknown = await res.json();
      if (!isAskResponse(body)) throw new ApiError(res.status, "Unexpected answer format.");
      return body;
    },
    async listHistory(limit = 20, offset = 0) {
      const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      const res = await request(`/history?${q.toString()}`);
      const body: unknown = await res.json();
      if (!isHistoryPage(body)) throw new ApiError(res.status, "Unexpected history format.");
      return body;
    },
    async deleteHistory(id) {
      await request(`/history/${encodeURIComponent(String(id))}`, { method: "DELETE" });
    },
  };
}
