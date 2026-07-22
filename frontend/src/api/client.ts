const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getCurrentSession: () => request<any>('/session/current'),
  getCurrentCustomer: () => request<any>('/customer/current'),
  startCall: (payload: Record<string, unknown>) => request<any>('/call/start', { method: 'POST', body: JSON.stringify(payload) }),
  submitResult: (payload: Record<string, unknown>) => request<any>('/call/result', { method: 'POST', body: JSON.stringify(payload) }),
  saveNote: (payload: Record<string, unknown>) => request<any>('/note', { method: 'POST', body: JSON.stringify(payload) }),
  nextCustomer: () => request<any>('/session/next'),
  getStatistics: () => request<any>('/statistics'),
};
