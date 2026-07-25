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
        className="min-h-[44px] rounded-2xl border border-white/10 bg-slate-900 px-4 text-sm font-semibold active:scale-[0.98]"
      >
        ← Back to Search
      </button>

      {error && (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-4 text-center text-sm text-red-300">
          {error}
        </div>
      )}

      {!record && !error && (
        <div className="flex min-h-[200px] items-center justify-center text-slate-400">Loading…</div>
      )}

      {record && (
        <>
          <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-lg font-semibold">{record.name || '(name missing)'}</p>
              {record.isBlacklisted && (
                <span className="rounded-full bg-red-500/10 px-3 py-1 text-xs font-semibold text-red-300">
                  🚫 Blacklisted
                </span>
              )}
            </div>
            <p className="text-sm text-slate-400">{record.loanNumber}</p>
            <div className="mt-3 space-y-1 text-sm">
              <p>📞 {record.phone || '—'}</p>
              <p>💰 Balance: {record.balance || '—'}</p>
              <p>📆 Days Overdue: {record.daysLate || '—'}</p>
              <p>💵 Monthly Payment: {record.monthlyPayment || '—'}</p>
            </div>
          </div>

          {record.notes.length > 0 && (
            <div className="rounded-[24px] border border-white/10 bg-slate-900/60 p-4">
              <p className="mb-2 text-sm font-semibold text-slate-300">Notes</p>
              {record.notes.map((note, index) => (
                <p key={`${index}-${note.slice(0, 20)}`} className="text-sm text-slate-400">
                  • {note}
                </p>
              ))}
            </div>
          )}

          {record.history.length > 0 && (
            <div className="rounded-[24px] border border-white/10 bg-slate-900/60 p-4">
              <p className="mb-2 text-sm font-semibold text-slate-300">History</p>
              {record.history.slice(0, 10).map((event, index) => (
                <p key={`${event.id ?? index}`} className="text-xs text-slate-400">
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
