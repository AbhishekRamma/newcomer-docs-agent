import { describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient, UnauthorizedError } from "./api";
import { answered, historyItem } from "./test/fixtures";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function setup(fetchImpl: typeof fetch, token: string | null = "test-access-token") {
  const onUnauthorized = vi.fn();
  const api = createApiClient({
    baseUrl: "http://api.test/", getToken: () => token, onUnauthorized, fetchImpl,
  });
  return { api, onUnauthorized };
}

describe("createApiClient", () => {
  it("attaches the bearer token and posts the question", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(200, answered));
    const { api } = setup(fetchImpl);
    const res = await api.ask("How do I apply for a SIN?");
    expect(res.history_id).toBe(7);
    const [url, init] = fetchImpl.mock.calls[0]!;
    expect(url).toBe("http://api.test/ask");
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-access-token");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ question: "How do I apply for a SIN?" }));
  });

  it("signs in again on a 401 and throws", async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(json(401, { detail: "expired" }));
    const { api, onUnauthorized } = setup(fetchImpl);
    await expect(api.listHistory()).rejects.toBeInstanceOf(UnauthorizedError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("signs in without calling the API when there is no token", async () => {
    const fetchImpl = vi.fn<typeof fetch>();
    const { api, onUnauthorized } = setup(fetchImpl, null);
    await expect(api.ask("hello there")).rejects.toBeInstanceOf(UnauthorizedError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("pages history with limit and offset and sends DELETE for one row", async () => {
    const page = { items: [historyItem(3, "q")], total: 1, limit: 5, offset: 10 };
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json(200, page))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const { api } = setup(fetchImpl);
    expect((await api.listHistory(5, 10)).items[0]!.id).toBe(3);
    expect(fetchImpl.mock.calls[0]![0]).toBe("http://api.test/history?limit=5&offset=10");
    await api.deleteHistory(3);
    expect(fetchImpl.mock.calls[1]![0]).toBe("http://api.test/history/3");
    expect(fetchImpl.mock.calls[1]![1]?.method).toBe("DELETE");
  });

  it("maps other errors and rejects unexpected shapes", async () => {
    const fetchImpl = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json(404, { detail: "No such history entry." }))
      .mockResolvedValueOnce(json(200, { route: 1 }));
    const { api, onUnauthorized } = setup(fetchImpl);
    const err = await api.deleteHistory(99).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(404);
    await expect(api.ask("hello there")).rejects.toThrow("Unexpected answer format.");
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
