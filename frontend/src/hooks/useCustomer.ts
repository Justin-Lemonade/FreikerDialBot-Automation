import { useCallback, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Customer, CustomerRecord } from '../types';

/**
 * Deliberately thin: useSession already carries currentCustomer on every
 * poll (GET /session/current embeds it), so most screens should read
 * customer data straight off session.currentCustomer rather than using
 * this hook at all. This exists only for the two cases that genuinely
 * need an independent fetch:
 *   1. advancing the queue via /session/next, which returns a customer
 *      object directly and needs somewhere to put it before the next
 *      session poll catches up
 *   2. looking at a customer who is NOT the current one (search results,
 *      "More Info" on a past customer) via getCustomerRecord
 */
export const useCustomer = () => {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [record, setRecord] = useState<CustomerRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const setFromSession = useCallback((next: Customer | null) => {
    setCustomer(next);
  }, []);

  const advanceQueue = useCallback(async () => {
    try {
      const result = await api.advanceSession();
      setCustomer(result.customer);
      setError(null);
      return result;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not advance the queue.');
      throw err;
    }
  }, []);

  const loadRecord = useCallback(async (customerId: string) => {
    try {
      const next = await api.getCustomerRecord(customerId);
      setRecord(next);
      setError(null);
      return next;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load that customer.');
      throw err;
    }
  }, []);

  return { customer, record, error, setFromSession, advanceQueue, loadRecord, setRecord };
};
