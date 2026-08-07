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

interface InfoCellProps {
  icon: string;
  label: string;
  value: string;
  color: string;
}

/** One column of the 3-across info grid below the name (days overdue /
 * monthly payment / phone) -- matches the inspiration images' compact
 * calling-card layout exactly, rather than the previous vertical list.
 * Values wrap instead of truncating: loan/phone/amount digits are the
 * one thing on this screen an operator must never lose to an ellipsis. */
const InfoCell = ({ icon, label, value, color }: InfoCellProps) => (
  <div className="flex min-w-0 flex-col items-center gap-1 text-center">
    <span className="text-lg leading-none">{icon}</span>
    <span className="w-full break-words font-data text-base leading-tight" style={{ color }}>
      {value || '-'}
    </span>
    <span className="font-display text-[7px] leading-tight" style={{ color: 'var(--text-muted)' }}>
      {label}
    </span>
  </div>
);

/**
 * The ID-card / terminal-access-card signature element -- matches the
 * calling-screen inspiration images precisely: avatar + name/loan
 * number header, then a 3-column icon grid (days overdue / monthly
 * payment / phone), not a vertical list of every field. Balance and
 * anything beyond these three lives in the More Info / CustomerDetail
 * screen instead, per the brief's "don't overload the main calling
 * interface" instruction -- this card is the quick-glance surface, not
 * the exhaustive one.
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

      <div className="mb-4 flex items-start gap-3 border-b pb-3" style={{ borderColor: 'var(--border-frame)' }}>
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center text-2xl"
          style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)' }}
        >
          🙂
        </div>
        {/* Never truncated: long names wrap onto a second line instead
            of being cut off, per the brief's explicit requirement. */}
        <div className="min-w-0">
          <h2 className="break-words font-data text-2xl leading-tight" style={{ color: 'var(--text-primary)' }}>
            {customer.name || '(name missing)'}
          </h2>
          <p className="break-words font-data text-base" style={{ color: 'var(--text-muted)' }}>
            {customer.loanNumber}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <InfoCell icon="📅" label="DAYS OVERDUE" value={customer.daysLate} color="var(--accent-red)" />
        <InfoCell icon="🪙" label="MONTHLY" value={customer.monthlyPayment} color="var(--text-primary)" />
      </div>

      {/* Both phone numbers, each independently tap-to-dial -- More
          Info now lives in the outcome-button row below the card
          instead of here (UI pass 4: "Move More Info below the
          primary outcome buttons"), so this stays a simple, compact
          phone list. */}
      <div className="mt-3">
        <p className="mb-1.5 font-display text-[8px]" style={{ color: 'var(--text-muted)' }}>
          📞 PHONE NUMBERS
        </p>
        {customer.phones.length === 0 ? (
          <p className="font-data text-base" style={{ color: 'var(--text-dim)' }}>
            No phone on file
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {customer.phones.map((entry) => (
              <a
                key={entry.number}
                href={`tel:${entry.number}`}
                className="retro-button min-h-[36px] px-3 py-1.5 font-data text-base"
                style={{
                  border: `1px solid ${entry.isBlacklisted ? 'var(--accent-red)' : 'var(--border-frame)'}`,
                  color: entry.isBlacklisted ? 'var(--accent-red)' : 'var(--accent-green)',
                  textDecoration: entry.isBlacklisted ? 'line-through' : 'none',
                  opacity: entry.isBlacklisted ? 0.7 : 1,
                }}
              >
                {entry.number}
              </a>
            ))}
          </div>
        )}
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
