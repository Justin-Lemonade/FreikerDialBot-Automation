import { useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { CustomerRecord } from '../types';

interface Props {
  customerId: string;
  onBack: () => void;
}

interface DetailRowProps {
  icon: string;
  label: string;
  value: string;
  color?: string;
}

/** One labeled row of the detail card -- icon + label left, value
 * right, dashed divider below. Matches the "detailed" inspiration
 * image's More Info layout. Values wrap rather than truncate; this
 * screen exists specifically so nothing is ever cut off. */
const DetailRow = ({ icon, label, value, color }: DetailRowProps) => (
  <div
    className="flex items-start justify-between gap-3 border-b border-dashed py-2.5 last:border-b-0"
    style={{ borderColor: 'var(--border-frame)' }}
  >
    <span className="shrink-0 font-data text-lg" style={{ color: color ?? 'var(--text-muted)' }}>
      {icon} {label}
    </span>
    <span className="break-words text-right font-data text-lg" style={{ color: color ?? 'var(--text-primary)' }}>
      {value || '-'}
    </span>
  </div>
);

/**
 * Reuses the existing, tested GET /customer/record endpoint -- same
 * data Telegram's /customer command and "More Info" button already
 * show, just as a Mini App page instead of a chat message.
 *
 * Field list is deliberately limited to what the backend actually
 * tracks (phone, balance, days overdue, monthly payment, current
 * overdue amount, original loan amount). The "detailed" inspiration
 * image also shows interest rate, payment count, a mailing address,
 * and an email -- none of which exist in this schema, so they are not
 * invented here; only real fields are shown, per the brief's own
 * instruction not to copy unsupported fields from the reference images.
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
            <div className="mb-1 flex items-start justify-between gap-2">
              <p className="break-words font-data text-xl" style={{ color: 'var(--text-primary)' }}>
                {record.name || '(name missing)'}
              </p>
              {record.isBlacklisted && (
                <span
                  className="shrink-0 px-2 py-1 font-display text-[8px]"
                  style={{ background: 'var(--accent-red-text)', color: 'var(--accent-red)' }}
                >
                  🚫 BLACKLISTED
                </span>
              )}
            </div>
            <p className="mb-3 break-words font-data text-base" style={{ color: 'var(--text-muted)' }}>
              {record.loanNumber}
            </p>

            <div>
              <DetailRow icon="📞" label="Phone" value={record.phone} color="var(--accent-green)" />
              <DetailRow icon="🪙" label="Monthly Payment" value={record.monthlyPayment} />
              <DetailRow icon="📅" label="Days Overdue" value={record.daysLate} color="var(--accent-red)" />
              <DetailRow icon="💵" label="Current Balance" value={record.balance} />
              <DetailRow icon="🪙" label="Amount Overdue" value={record.currentOverdueAmount} />
              <DetailRow icon="🪙" label="Original Loan Amount" value={record.originalLoanAmount} />
            </div>
          </div>

          {record.notes.length > 0 && (
            <div className="retro-panel p-4">
              <p className="mb-2 font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
                NOTES
              </p>
              {record.notes.map((note, index) => (
                <p key={`${index}-${note.slice(0, 20)}`} className="break-words font-data text-lg" style={{ color: 'var(--text-primary)' }}>
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
                <p key={`${event.id ?? index}`} className="break-words font-data text-base" style={{ color: 'var(--text-muted)' }}>
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
