import { useCallback, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { SessionSummary } from '../types';

export type LoadState = 'idle' | 'loading' | 'success' | 'error';

/**
 * The single source of truth for session/progress/current-customer state.
 * Every field here comes directly from GET /session/current -- nothing
 * is computed or incremented client-side. Completing an outcome doesn't
 * update this hook's state directly; it calls refreshSession() (or uses
 * the session object /call/result already returns) so the UI always
 * reflects what the backend actually recorded, never an optimistic
 * guess. See PRIORITY 4 in the engineering brief for why this matters:
 * currentCustomerIndex/remaining have specific backend semantics that
 * are easy to get wrong by assuming instead of asking.
 */
export const useSession = () => {
  const [session, setSession] = useState<SessionSummary | null>(null);
  const [loadState, setLoadState] = useState<LoadState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);
  // Real timestamp of the last successful GET /session/current --
  // backs Settings > Admin/Diagnostics "Sync Status", so that row
  // shows an actual last-contact time instead of a fake "connected"
  // indicator.
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);

  const refreshSession = useCallback(async () => {
    setLoadState((prev) => (prev === 'idle' ? 'loading' : prev));
    try {
      const next = await api.getCurrentSession();
      setSession(next);
      setLoadState('success');
      setIsStale(false);
      setError(null);
      setLastSyncedAt(Date.now());
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not load session.';
      setError(message);
      setLoadState((prev) => (prev === 'idle' ? 'error' : prev));
      // Keep the last-known-good session in state but flag it stale,
      // rather than blanking the screen on a transient network error --
      // see PRIORITY 10: never silently show stale data as if it's fresh.
      setSession((current) => {
        if (current) setIsStale(true);
        return current;
      });
    }
  }, []);

  /** Applies a session object the backend already returned from another
   * call (e.g. /call/result's `session` field) without an extra round
   * trip -- still the backend's own data, just already in hand. */
  const applySession = useCallback((next: SessionSummary) => {
    setSession(next);
    setLoadState('success');
    setIsStale(false);
    setError(null);
    setLastSyncedAt(Date.now());
  }, []);

  return { session, loadState, error, isStale, lastSyncedAt, refreshSession, applySession, setSession };
};
