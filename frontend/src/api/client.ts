/**
 * HTTP client for the Mini App API (mini_app_api.py). One fetch wrapper,
 * one auth header, one error shape -- every hook goes through this
 * instead of calling fetch() directly, so retry/error/auth behavior
 * only needs to be right in one place.
 *
 * Base URL: defaults to '' (relative/same-origin). This matches the
 * project's actual, configured deployment path: mini_app_api.py serves
 * the built frontend itself as static files (see mini_app_api.py's
 * _serve_static and config.py's MINI_APP_STATIC_DIR) when
 * start_mini_app.py builds and points at frontend/dist, so the frontend
 * and API share one origin and relative paths just work -- through the
 * ngrok tunnel, from a real phone, with no configuration needed.
 *
 * IMPORTANT: a previous version of this file defaulted to
 * 'http://localhost:8000'. That is only correct for someone running
 * `npm run dev` as a separate process from the API on their own
 * development machine. Baked into a production build and opened inside
 * Telegram on a real phone, "localhost" resolves to the phone itself,
 * not the server -- the app would never reach the backend. Confirmed
 * by tracing start_mini_app.py's actual process topology: it only
 * starts the backend + an ngrok tunnel to the backend, never a separate
 * frontend dev server.
 *
 * Override via VITE_API_BASE_URL only if you are intentionally running
 * the frontend as a separate dev-server process against a
 * different-origin backend (e.g. `npm run dev` + `python
 * mini_app_api.py` on two different ports on the same machine).
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '';

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

  pauseQueue: () =>
    post<{ ok: boolean; paused: boolean; session?: import('../types').SessionSummary }>('/queue/pause'),

  resumeQueue: () =>
    post<{ ok: boolean; paused: boolean; session?: import('../types').SessionSummary }>('/queue/resume'),

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

  getSettings: () => get<import('../types').AppSettings>('/settings'),

  updateSettings: (fields: Partial<import('../types').AppSettings>) =>
    post<{ ok: boolean; settings?: import('../types').AppSettings; error?: string }>('/settings', fields),

  /** GET /export -- admin-only (mini_app_api.py checks security.is_admin
   * before this runs; a non-admin operator gets a real 403 here, not a
   * silently-disabled button). Uses a raw fetch instead of request()
   * because the response is a file: needs the real filename from
   * Content-Disposition, not just the blob, to save it correctly. */
  exportData: async (format: 'csv' | 'json' | 'xlsx'): Promise<{ blob: Blob; filename: string }> => {
    const initData = getInitData();
    const headers: Record<string, string> = initData ? { Authorization: `tma ${initData}` } : {};
    const response = await fetch(`${API_BASE_URL}/export?format=${format}`, { headers });
    if (!response.ok) {
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        body = null;
      }
      const message = extractErrorMessage(body) || `Export failed (${response.status})`;
      throw new ApiError(response.status, message, body);
    }
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : `export.${format}`;
    const blob = await response.blob();
    return { blob, filename };
  },

  /** POST /import -- runs the same real Importer pipeline the Telegram
   * bot's /upload, JSON-file, and Excel-file handlers use. No admin
   * gate, matching the bot (only /export is admin-only). `data` is
   * either the raw JSON text ('json') or the file's base64-encoded
   * bytes ('xlsx') -- see importFile below for the FileReader glue. */
  importData: (format: 'json' | 'xlsx', data: string) =>
    post<import('../types').ImportResult>('/import', { format, data }),
};
