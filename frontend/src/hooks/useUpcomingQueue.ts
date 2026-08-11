import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Customer } from '../types';

/**
 * The real backend support behind Settings > Queue > Pre-ready Count:
 * whenever the active customer or the setting itself changes, fetches
 * that many upcoming customers via GET /queue/upcoming?count=N (see
 * MiniAppService.queue_upcoming) and hands them back for App.tsx to
 * show as the "Up Next" preview on the calling screen. A count of 0
 * ("None" in the UI) fetches nothing and clears the list -- matching
 * today's existing behavior of only ever preparing the current
 * customer.
 *
 * Deliberately just a preview, not a second queue: nothing here
 * mutates queue state or duplicates get_next_actionable_customer's
 * selection rule -- it only ever displays what the backend already
 * says comes next.
 */
export const useUpcomingQueue = (currentCustomerId: string | null | undefined, count: number) => {
  const [upcoming, setUpcoming] = useState<Customer[]>([]);

  useEffect(() => {
    if (!count || count < 1) {
      setUpcoming([]);
      return;
    }
    let cancelled = false;
    api
      .getUpcomingQueue(count)
      .then((result) => {
        if (!cancelled) setUpcoming(result.upcoming);
      })
      .catch(() => {
        // Best-effort preview only -- a failed prefetch shouldn't
        // surface an error banner over the live calling workflow, it
        // should just leave the strip empty until the next attempt.
        if (!cancelled) setUpcoming([]);
      });
    return () => {
      cancelled = true;
    };
    // Re-fetch whenever the active customer changes (yesterday's
    // "upcoming" preview is stale once today's current customer moves
    // on) or the operator changes the setting itself.
  }, [currentCustomerId, count]);

  return upcoming;
};
