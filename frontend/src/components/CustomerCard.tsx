import { useEffect, useState } from 'react';
import type { Customer } from '../types';

interface Props {
  customer: Customer | null;
  indexLabel?: string;
  /** Set by the parent (briefly, before swapping to the next customer)
   * to trigger the hyperspace jump-out animation. The jump-in for a new
   * customer happens automatically on mount below -- give this
   * component a `key={customer.id}` at the call site so a genuinely new
   * customer actually remounts it. */
  isLeaving?: boolean;
}

/**
 * The ID-card / terminal-access-card signature element (images 3, 5,
 * 6). Corners are clipped via the shared .retro-card utility rather
 * than rounded, which is what gives it the sci-fi-card silhouette
 * instead of a generic rounded panel.
 */
export const CustomerCard = ({ customer, indexLabel, isLeaving }: Props) => {
  const [isEntering, setIsEntering] = useState(true);

  useEffect(() => {
    const timeout = setTimeout(() => setIsEntering(false), 400);
    return () => clearTimeout(timeout);
  }, []);

  const transitionClass = isLeaving ? 'card-jump-out' : isEntering ? 'card-jump-in' : '';

  if (!customer) {
    return (
      <div
        className="flex min-h-[240px] items-center justify-center p-6 text-center retro-card"
        style={{ color: 'var(--text-muted)' }}
      >
        Loading customer…
      </div>
    );
  }

  return (
    <div className={`retro-card p-5 ${transitionClass}`}>
      <div className="mb-3 flex items-center justify-between">
        <p className="font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          {indexLabel ? `CUSTOMER ${indexLabel}` : 'CURRENT CUSTOMER'}
        </p>
        <div
          className="rounded-sm border px-2 py-0.5 font-display text-[8px]"
          style={{ borderColor: 'var(--accent-green-strong)', color: 'var(--accent-green)' }}
        >
          LIVE
        </div>
      </div>

      <div className="mb-4 flex items-center gap-3 border-b pb-3" style={{ borderColor: 'var(--border-frame)' }}>
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center text-2xl"
          style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)' }}
        >
          🙂
        </div>
        <div className="min-w-0">
          <h2 className="truncate font-data text-2xl leading-tight" style={{ color: 'var(--text-primary)' }}>
            {customer.name || '(name missing)'}
          </h2>
          <p className="truncate font-data text-base" style={{ color: 'var(--text-muted)' }}>
            {customer.loanNumber}
          </p>
        </div>
      </div>

      <div className="space-y-1.5 font-data text-lg">
        <div className="flex items-center justify-between">
          <span style={{ color: 'var(--text-muted)' }}>📞 Phone</span>
          <span style={{ color: 'var(--text-primary)' }}>{customer.phone || '-'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ color: 'var(--text-muted)' }}>💰 Monthly</span>
          <span style={{ color: 'var(--text-primary)' }}>{customer.monthlyPayment || '-'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ color: 'var(--accent-red)' }}>⏰ Days Overdue</span>
          <span style={{ color: 'var(--accent-red)' }}>{customer.daysLate || '-'}</span>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ color: 'var(--text-muted)' }}>💵 Balance</span>
          <span style={{ color: 'var(--text-primary)' }}>{customer.balance || '-'}</span>
        </div>
      </div>

      {customer.isBlacklisted && (
        <div
          className="mt-3 border px-3 py-2 text-center font-display text-[9px]"
          style={{ borderColor: 'var(--accent-red)', color: 'var(--accent-red)', background: 'var(--accent-red-text)' }}
        >
          🚫 BLACKLISTED
        </div>
      )}
    </div>
  );
};
