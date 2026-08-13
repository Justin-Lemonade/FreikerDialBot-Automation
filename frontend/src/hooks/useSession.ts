import { useCallback, useRef, useState } from 'react';
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

  // Monotonic counter guarding against out-of-order responses. App.tsx
  // polls refreshSession() every 5s AND calls applySession() directly
  // after /call/result, /queue/pause, /queue/resume, /queue/call-back --
  // any of which can resolve out of issue order under real network
  // conditions (e.g. a poll fired just before an outcome submit, slow
  // enough that it resolves just after applySession already set the
  // fresh post-outcome session). Without this guard, that stale GET
  // response would silently overwrite the newer state -- the same bug
  // class as UI Pass 8's stale-settings finding, just for session state
  // instead of settings state. Every issued request/apply bumps the
  // counter; a response is only applied if it's still the most recent
  // one issued, so an old response can never clobber a newer one.
  const requestIdRef = useRef(0);

  const refreshSession = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoadState((prev) => (prev === 'idle' ? 'loading' : prev));
    try {
      const next = await api.getCurrentSession();
      if (requestId !== requestIdRef.current) return; // superseded -- discard
      setSession(next);
      setLoadState('success');
      setIsStale(false);
      setError(null);
      setLastSyncedAt(Date.now());
    } catch (err) {
      if (requestId !== requestIdRef.current) return; // superseded -- discard
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
   * trip -- still the backend's own data, just already in hand. Bumps
   * the request counter so any older, still-in-flight refreshSession()
   * response can no longer overwrite this newer, known-fresh state. */
  const applySession = useCallback((next: SessionSummary) => {
    requestIdRef.current += 1;
    setSession(next);
    setLoadState('success');
    setIsStale(false);
    setError(null);
    setLastSyncedAt(Date.now());
  }, []);

  return { session, loadState, error, isStale, lastSyncedAt, refreshSession, applySession, setSession };
};
