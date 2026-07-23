/**
 * HTTP client for the Mini App API (mini_app_api.py). One fetch wrapper,
 * one auth header, one error shape -- every hook goes through this
 * instead of calling fetch() directly, so retry/error/auth behavior
 * only needs to be right in one place.
 *
 * Base URL: the backend (mini_app_api.py) runs as its own process on a
 * different port than the Vite dev server (see start_mini_app.py), so
 * this can't assume same-origin. VITE_API_BASE_URL should be set to
 * wherever mini_app_api.py is actually listening -- during local dev
 * via start_mini_app.py that's http://localhost:8000; in production
 * behind the ngrok tunnel, the bot passes the tunneled MINI_APP_URL to
 * the frontend, and the backend needs to be reachable at a URL of its
 * own (see ARCHITECTURE.md note on this before deploying).
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** Telegram's WebApp initData, read once and reused for every request's
 * Authorization header. Empty string if not running inside Telegram
 * (e.g. local browser testing) -- the backend allows anonymous requests
 * everywhere except /export, so this degrades gracefully rather than
 * blocking non-Telegram testing entirely. */
function getInitData(): string {
  const webApp = window.Telegram?.WebApp;
  return webApp?.initData || '';
}

function extractErrorMessage(body: unknown): string | null {
  if (body && typeof body === 'object' && 'error' in body) {
    const value = (body as { error: unknown }).error;
    return value ? String(value) : null;
  }
  return null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const headers: Record<string, string> = {
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(initData ? { Authorization: `tma ${initData}` } : {}),
    ...(options.headers as Record<string, string> | undefined),
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (networkError) {
    throw new ApiError(0, 'Network request failed. Check your connection and try again.');
  }

  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    const message = extractErrorMessage(body) || `Request failed (${response.status})`;
    throw new ApiError(response.status, message, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('Content-Type') || '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }
  return (await response.blob()) as unknown as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'GET' });
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: body !== undefined ? JSON.stringify(body) : undefined });
}

// ---------------------------------------------------------------------------
// Endpoint surface -- one function per mini_app_api.py route. Field names
// here match the backend's actual JSON keys exactly (camelCase, per
// MiniAppService._customer_payload / get_current_session), so no
// translation layer sits between this file and the wire format.
// ---------------------------------------------------------------------------

export const api = {
  getCurrentSession: () => get<import('../types').SessionSummary>('/session/current'),

  getCurrentCustomer: () => get<Partial<import('../types').Customer>>('/customer/current'),

  getStatistics: () => get<import('../types').StatisticsPayload>('/statistics'),

  advanceSession: () =>
    post<{ customer: import('../types').Customer | null; session: import('../types').SessionSummary }>(
      '/session/next'
    ),

  startCall: (customerId: string) =>
    post<{ ok: boolean; customerId?: string; startedAt?: string; error?: string }>('/call/start', {
      customerId,
    }),

  submitCallResult: (customerId: string, outcome: string, durationSeconds?: number) =>
    post<import('../types').CallResultResponse>('/call/result', {
      customerId,
      outcome,
      duration: durationSeconds,
    }),

  saveNote: (customerId: string, note: string) =>
    post<{ ok: boolean; customerId?: string; note?: string; error?: string }>('/note', {
      customerId,
      note,
    }),

  pauseQueue: () => post<{ ok: boolean; paused: boolean }>('/queue/pause'),

  callBack: () =>
    post<{ ok: boolean; customer: import('../types').Customer | null; session: import('../types').SessionSummary }>(
      '/queue/call-back'
    ),

  getUpcoming: () => get<import('../types').Customer>('/queue/upcoming'),

  searchCustomers: (query: string) =>
    get<{ results: import('../types').Customer[] }>(`/customer/search?q=${encodeURIComponent(query)}`),

  getCustomerRecord: (customerId: string) =>
    get<import('../types').CustomerRecord>(`/customer/record?id=${encodeURIComponent(customerId)}`),

  editCustomer: (customerId: string, fields: Record<string, unknown>) =>
    post<{ ok: boolean; customer?: import('../types').Customer; error?: string }>('/customer/edit', {
      customerId,
      fields,
    }),

  setCustomerBlacklist: (customerId: string, blacklisted: boolean) =>
    post<{ ok: boolean; customer?: import('../types').Customer; error?: string }>('/customer/blacklist', {
      customerId,
      blacklisted,
    }),

  setPhoneBlacklist: (phone: string, blacklisted: boolean, reason?: string) =>
    post<{ ok: boolean; phone: string; blacklisted: boolean }>('/phone/blacklist', {
      phone,
      blacklisted,
      reason,
    }),
};
