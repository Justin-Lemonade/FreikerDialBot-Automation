import { useEffect, useState } from 'react';
import type { Customer, VisibleField } from '../types';

interface Props {
  customer: Customer | null;
  indexLabel?: string;
  /** Set by the parent (briefly, before swapping to the next customer)
   * to trigger the hyperspace jump-out animation. The jump-in for a new
   * customer happens automatically on mount below -- give this
   * component a `key={customer.id}` at the call site so a genuinely new
   * customer actually remounts it. */
  isLeaving?: boolean;
  /** Which phone number the CALL CUSTOMER button will dial next --
   * Settings > Phone Handling > Quick Number Switching. Highlights that
   * number in the list below so the operator can see at a glance which
   * one is active without opening More Info. */
  activePhone?: string;
  /** Tapping a number always still dials it immediately (the existing
   * href="tel:" below is unchanged) -- this additionally marks that
   * number active for next time, so the operator doesn't have to
   * re-pick it on every call to the same customer. */
  onSelectPhone?: (phone: string) => void;
  /** Settings > Display > Visible Fields -- which of the fixed known
   * fields below to render, and in what order. Defaults to the
   * pre-Display-setting behavior (days overdue + monthly payment) so
   * this component still works standalone/in tests without a settings
   * provider. */
  visibleFields?: VisibleField[];
}

interface InfoCellProps {
  icon: string;
  label: string;
  value: string;
  color: string;
}

/** One column of the info grid below the name -- matches the
 * inspiration images' compact calling-card layout. Values wrap instead
 * of truncating: loan/phone/amount digits are the one thing on this
 * screen an operator must never lose to an ellipsis. */
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

/** The fixed, known set of info-grid fields, keyed the same way
 * Settings > Display > Visible Fields refers to them (and the same way
 * the backend's _VISIBLE_FIELD_IDS does) -- adding a new field later
 * means adding one entry here, not restructuring this component's
 * render logic. `value` is a function of the customer so the whole
 * list can be built once and then filtered/ordered by whatever the
 * operator has enabled. */
const FIELD_DEFS: { id: VisibleField; icon: string; label: string; color: string; value: (c: Customer) => string }[] = [
  { id: 'daysOverdue', icon: '📅', label: 'DAYS OVERDUE', color: 'var(--accent-red)', value: (c) => c.daysLate },
  { id: 'monthlyPayment', icon: '🪙', label: 'MONTHLY', color: 'var(--text-primary)', value: (c) => c.monthlyPayment },
  { id: 'balance', icon: '💰', label: 'BALANCE', color: 'var(--text-primary)', value: (c) => c.balance },
];

// Tailwind's static analysis needs each grid-cols-N class to appear
// literally in source -- a template-string `grid-cols-${n}` would be
// purged. This map is the one place that constraint lives, so
// FIELD_DEFS above can grow independently of it (up to 4 columns
// before the cells get too cramped to read on a narrow phone).
const GRID_COLS_CLASS: Record<number, string> = { 1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3', 4: 'grid-cols-4' };

const DEFAULT_VISIBLE_FIELDS: VisibleField[] = ['daysOverdue', 'monthlyPayment'];

/**
 * The ID-card / terminal-access-card signature element -- matches the
 * calling-screen inspiration images precisely: avatar + name/loan
 * number header, then a configurable info grid (Settings > Display >
 * Visible Fields), then the phone-number list below. Anything not
 * enabled in Visible Fields lives in the More Info / CustomerDetail
 * screen instead, per the brief's "don't overload the main calling
 * interface" instruction -- this card is the quick-glance surface, not
 * the exhaustive one.
 */
export const CustomerCard = ({ customer, indexLabel, isLeaving, activePhone, onSelectPhone, visibleFields = DEFAULT_VISIBLE_FIELDS }: Props) => {
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

      {visibleFields.length > 0 && (
        <div className={`grid gap-2 ${GRID_COLS_CLASS[visibleFields.length] ?? 'grid-cols-3'}`}>
          {FIELD_DEFS.filter((field) => visibleFields.includes(field.id)).map((field) => (
            <InfoCell key={field.id} icon={field.icon} label={field.label} value={field.value(customer)} color={field.color} />
          ))}
        </div>
      )}

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
            {customer.phones.map((entry) => {
              const isActive = !entry.isBlacklisted && entry.number === activePhone;
              return (
                <a
                  key={entry.number}
                  href={`tel:${entry.number}`}
                  onClick={() => onSelectPhone?.(entry.number)}
                  className="retro-button min-h-[36px] px-3 py-1.5 font-data text-base"
                  style={{
                    border: `1px solid ${entry.isBlacklisted ? 'var(--accent-red)' : isActive ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
                    color: entry.isBlacklisted ? 'var(--accent-red)' : isActive ? 'var(--accent-green-text)' : 'var(--accent-green)',
                    background: isActive ? 'var(--accent-green)' : 'transparent',
                    textDecoration: entry.isBlacklisted ? 'line-through' : 'none',
                    opacity: entry.isBlacklisted ? 0.7 : 1,
                  }}
                >
                  {isActive ? '● ' : ''}
                  {entry.number}
                </a>
              );
            })}
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
