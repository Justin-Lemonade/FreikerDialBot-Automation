import { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { CustomerRecord } from '../types';

interface Props {
  customerId: string;
  onBack: () => void;
}

/**
 * Reuses the existing, tested GET /customer/record endpoint -- same
 * data Telegram's /customer command and "More Info" button already
 * show, just as a Mini App page instead of a chat message.
 */
export const CustomerDetail = ({ customerId, onBack }: Props) => {
  const [record, setRecord] = useState<CustomerRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getCustomerRecord(customerId)
      .then((data) => {
        if (!cancelled) setRecord(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load this customer.');
      });
    return () => {
      cancelled = true;
    };
  }, [customerId]);

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="retro-button min-h-[44px] px-4 font-display text-[10px]"
        style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
      >
        ← BACK TO SEARCH
      </button>

      {error && (
        <div className="p-4 text-center font-data text-lg" style={{ border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      {!record && !error && (
        <div className="flex min-h-[200px] items-center justify-center font-data text-lg" style={{ color: 'var(--text-muted)' }}>
          Loading…
        </div>
      )}

      {record && (
        <>
          <div className="retro-card p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="font-data text-xl" style={{ color: 'var(--text-primary)' }}>
                {record.name || '(name missing)'}
              </p>
              {record.isBlacklisted && (
                <span
                  className="px-2 py-1 font-display text-[8px]"
                  style={{ background: 'var(--accent-red-text)', color: 'var(--accent-red)' }}
                >
                  🚫 BLACKLISTED
                </span>
              )}
            </div>
            <p className="font-data text-base" style={{ color: 'var(--text-muted)' }}>
              {record.loanNumber}
            </p>
            <div className="mt-3 space-y-1 font-data text-lg" style={{ color: 'var(--text-primary)' }}>
              <p>📞 {record.phone || '-'}</p>
              <p>💰 Balance: {record.balance || '-'}</p>
              <p style={{ color: 'var(--accent-red)' }}>📆 Days Overdue: {record.daysLate || '-'}</p>
              <p>💵 Monthly Payment: {record.monthlyPayment || '-'}</p>
            </div>
          </div>

          {record.notes.length > 0 && (
            <div className="retro-panel p-4">
              <p className="mb-2 font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
                NOTES
              </p>
              {record.notes.map((note, index) => (
                <p key={`${index}-${note.slice(0, 20)}`} className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
                  • {note}
                </p>
              ))}
            </div>
          )}

          {record.history.length > 0 && (
            <div className="retro-panel p-4">
              <p className="mb-2 font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
                HISTORY
              </p>
              {record.history.slice(0, 10).map((event, index) => (
                <p key={`${event.id ?? index}`} className="font-data text-base" style={{ color: 'var(--text-muted)' }}>
                  {event.event_timestamp} — {event.event_type}
                </p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};
