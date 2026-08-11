import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../client';

/**
 * Focused tests for the Mini App API client's request construction --
 * the one place every hook builds its URL, method, headers, and error
 * shape. No real network call happens: globalThis.fetch is replaced with
 * a mock that records the RequestInit each call received. window.Telegram
 * is stubbed so the Authorization header behavior is observable in both
 * states (inside vs outside a real Telegram client).
 */

type MockFetch = ReturnType<typeof vi.fn>;

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    json: async () => body,
    blob: async () => new Blob([]),
  } as unknown as Response;
}

function makeResponseOverrides(): { fetchMock: MockFetch; lastCall: () => RequestInit | undefined } {
  const fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  return {
    fetchMock,
    lastCall: () => fetchMock.mock.calls[fetchMock.mock.calls.length - 1]?.[1] as RequestInit | undefined,
  };
}

function stubTelegram(initData: string | undefined): void {
  if (initData === undefined) {
    delete (window as { Telegram?: unknown }).Telegram;
  } else {
    (window as { Telegram?: unknown }).Telegram = {
      WebApp: { initData },
    };
  }
}

describe('api client request construction', () => {
  let fetchMock: MockFetch;

  beforeEach(() => {
    const harness = makeResponseOverrides();
    fetchMock = harness.fetchMock;
    stubTelegram('query_id=real&auth_date=123&hash=abc');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    stubTelegram(undefined);
  });

  it('GET requests use the exact path and the GET method', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { customerCount: 3 }));
    await api.getCurrentSession();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/session/current');
    expect(options.method).toBe('GET');
  });

  it('GET requests send no Content-Type header', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { customerCount: 3 }));
    await api.getCurrentSession();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = options.headers as Record<string, string>;
    expect(headers).not.toHaveProperty('Content-Type');
  });

  it('sends the Authorization header with the tma prefix when Telegram initData exists', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { customerCount: 3 }));
    await api.getCurrentSession();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = options.headers as Record<string, string>;
    expect(headers.Authorization).toBe('tma query_id=real&auth_date=123&hash=abc');
  });

  it('omits the Authorization header entirely when not running inside Telegram', async () => {
    stubTelegram(undefined);
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { customerCount: 3 }));
    await api.getCurrentSession();
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.headers as Record<string, string>).not.toHaveProperty('Authorization');
  });

  it('POST requests serialize the body as JSON with a Content-Type header', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(200, { ok: true, status: 'warned', nextCustomer: null })
    );
    await api.submitCallResult('42', 'contacted', 10);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/call/result');
    expect(options.method).toBe('POST');
    expect(options.body).toBe('{"customerId":"42","outcome":"contacted","duration":10}');
    expect((options.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('URL-encodes query parameters in the search endpoint', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { results: [] }));
    await api.searchCustomers('Ana María & Sons');
    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/customer/search?q=');
    expect(url).toContain(encodeURIComponent('Ana María & Sons'));
    expect(url).not.toContain(' ');
  });

  it('getUpcomingQueue requests /queue/upcoming with the count query param', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { upcoming: [] }));
    await api.getUpcomingQueue(3);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/queue/upcoming?count=3');
    expect(options.method ?? 'GET').toBe('GET');
  });

  it('parses JSON responses into typed objects', async () => {
    const payload = { customerCount: 5, completed: false };
    fetchMock.mockResolvedValueOnce(jsonResponse(200, payload));
    const session = await api.getCurrentSession();
    expect(session).toEqual(expect.objectContaining(payload));
  });

  it('turns a backend error body into an ApiError with its message', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(400, { error: 'maxCallAttempts must be at least 1' }));
    const err = await api
      .updateSettings({ maxCallAttempts: 0 })
      .then(() => null)
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(400);
    expect((err as ApiError).message).toBe('maxCallAttempts must be at least 1');
  });

  it('falls back to a generic message when the error body has no message', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));
    const err = await api
      .getCurrentSession()
      .then(() => null)
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(500);
    expect((err as ApiError).message).toContain('Request failed (500)');
  });

  it('reports a network failure as an ApiError with status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const err = await api
      .getCurrentSession()
      .then(() => null)
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(0);
    expect(err).toBeInstanceOf(ApiError);
  });

  it('returns undefined for a 204 response', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, status: 204 } as Response);
    const result = await api
      .updateSettings({ autoAdvance: true })
      .then((r) => r)
      .catch(() => 'caught');
    expect(result).toBeUndefined();
  });
});