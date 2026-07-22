import { useCallback, useState } from 'react';
import { api } from '../api/client';
import type { SessionSummary } from '../types';

export const useSession = () => {
  const [session, setSession] = useState<SessionSummary | null>(null);

  const refreshSession = useCallback(async () => {
    try {
      const data = await api.getCurrentSession();
      setSession(data as SessionSummary);
    } catch {
      setSession({
        currentCustomerIndex: 17,
        customerCount: 48,
        answeredToday: 9,
        estimatedRemaining: 31,
        averageCallTime: '2m 18s',
        completed: false,
      });
    }
  }, []);

  const nextSession = useCallback(async () => {
    try {
      const data = await api.nextCustomer();
      const sessionPayload = (data as { session?: SessionSummary } | SessionSummary)?.session ?? data;
      setSession((current) => current ? { ...current, ...sessionPayload } : sessionPayload as SessionSummary);
    } catch {
      // keep UI responsive without backend
    }
  }, []);

  return { session, refreshSession, nextSession };
};
