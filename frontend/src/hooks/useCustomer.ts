import { useCallback, useState } from 'react';
import { api } from '../api/client';
import type { Customer } from '../types';

const defaultCustomer: Customer = {
  id: '123456',
  name: 'John Smith',
  loanNumber: 'Loan #123456',
  balance: 550,
  daysLate: 18,
  phone: '+15551234567',
  notes: ['Wife answered yesterday', 'Requested callback after 4 PM'],
};

function isWrappedCustomer(data: any): data is { customer: Customer } {
  return data && typeof data === 'object' && 'customer' in data;
}

export const useCustomer = () => {
  const [customer, setCustomer] = useState<Customer | null>(defaultCustomer);

  const refreshCustomer = useCallback(async () => {
    try {
      const data = await api.getCurrentCustomer();
      const payload = isWrappedCustomer(data) ? data.customer : data;
      setCustomer(payload as Customer);
    } catch {
      setCustomer(defaultCustomer);
    }
  }, []);

  const nextCustomer = useCallback(async () => {
    try {
      const data = await api.nextCustomer();
      const payload = isWrappedCustomer(data) ? data.customer : data;
      setCustomer(payload as Customer);
    } catch {
      setCustomer(defaultCustomer);
    }
  }, []);

  const prefetchCustomer = useCallback(async () => {
    try {
      const data = await api.nextCustomer();
      const payload = isWrappedCustomer(data) ? data.customer : data;
      setCustomer((current) => current ?? (payload as Customer));
    } catch {
      // no-op
    }
  }, []);

  return { customer, refreshCustomer, nextCustomer, prefetchCustomer };
};
