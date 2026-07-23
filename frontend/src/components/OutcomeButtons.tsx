interface Props {
  onOutcome: (outcome: string) => void;
  disabled?: boolean;
}

const secondaryButtons = [
  { label: '⚠ Wrong Number', value: 'wrong_number' },
  { label: '💰 Paid', value: 'paid', disabled: true },
  { label: '📞 Call Again', value: 'call_again' },
  { label: '📝 Add Note', value: 'note' },
];

/**
 * Didn't Answer is always left, Contacted is always right -- fixed
 * ordering, matches queue_ui.py's own bot keyboard so an operator
 * switching between Telegram chat and the Mini App sees the same
 * layout either way.
 *
 * "Paid" is shown but disabled: the backend has no real "paid" write
 * path anywhere in the codebase (QueueEngine.apply_action's ActionStatus
 * only accepts warned/call_later/skip/invalid_number -- "paid" exists
 * only as a schema-level enum value, never actually written). Per
 * AGENTS.md's rule against inventing business logic to fill a doc-implied
 * gap, this button stays disabled with an honest "not yet available"
 * state rather than the frontend pretending it works or inventing its
 * own write path the Telegram bot doesn't share. Re-enable once a real
 * backend Paid action exists and both frontends can call it identically.
 */
export const OutcomeButtons = ({ onOutcome, disabled }: Props) => {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => onOutcome('did_not_answer')}
          disabled={disabled}
          className="min-h-[56px] rounded-2xl border border-white/10 bg-slate-900 px-3 text-base font-semibold text-slate-100 transition active:scale-[0.98] disabled:opacity-60"
        >
          ❌ Didn&apos;t Answer
        </button>
        <button
          onClick={() => onOutcome('contacted')}
          disabled={disabled}
          className="min-h-[56px] rounded-2xl bg-emerald-500 px-3 text-base font-semibold text-slate-950 transition active:scale-[0.98] disabled:opacity-60"
        >
          ✅ Contacted
        </button>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {secondaryButtons.map((button) => (
          <button
            key={button.value}
            onClick={() => onOutcome(button.value)}
            disabled={disabled || button.disabled}
            title={button.disabled ? 'Not yet available -- backend has no Paid action yet' : undefined}
            className="min-h-[48px] rounded-xl border border-white/10 bg-slate-900/60 px-1 text-[11px] font-medium leading-tight text-slate-300 transition active:scale-[0.98] disabled:opacity-40"
          >
            {button.label}
          </button>
        ))}
      </div>
    </div>
  );
};
