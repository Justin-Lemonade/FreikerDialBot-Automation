interface Props {
  onOutcome: (outcome: string) => void;
  disabled?: boolean;
}

const secondaryButtons = [
  { label: 'WRONG #', value: 'wrong_number' },
  { label: 'PAID', value: 'paid', disabled: true },
  { label: 'CALL AGAIN', value: 'call_again' },
  { label: 'NOTE', value: 'note' },
];

/**
 * Didn't Answer is always left, Contacted is always right -- fixed
 * ordering, matches queue_ui.py's own bot keyboard so an operator
 * switching between Telegram chat and the Mini App sees the same
 * layout either way. (Brief: "Keep Didn't Answer on the left,
 * Contacted on the right... consistent in both Telegram and Mini App.")
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
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => onOutcome('did_not_answer')}
          disabled={disabled}
          className="retro-button min-h-[52px] px-2 font-display text-[11px] disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            background: 'var(--accent-red)',
            color: 'var(--accent-red-text)',
            border: '2px solid var(--accent-red)',
            boxShadow: disabled ? 'none' : '0 3px 0 #a83a3e',
          }}
        >
          DIDN'T ANSWER
        </button>
        <button
          onClick={() => onOutcome('contacted')}
          disabled={disabled}
          className="retro-button min-h-[52px] px-2 font-display text-[11px] disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            background: 'var(--accent-blue)',
            color: 'var(--accent-blue-text)',
            border: '2px solid var(--accent-blue)',
            boxShadow: disabled ? 'none' : '0 3px 0 #2f6ec2',
          }}
        >
          CONTACTED
        </button>
      </div>

      <div className="grid grid-cols-4 gap-1.5">
        {secondaryButtons.map((button) => (
          <button
            key={button.value}
            onClick={() => onOutcome(button.value)}
            disabled={disabled || button.disabled}
            title={button.disabled ? 'Not yet available -- backend has no Paid action yet' : undefined}
            className="retro-button min-h-[44px] px-1 font-display text-[8px] leading-tight disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: 'var(--bg-panel)',
              color: 'var(--text-muted)',
              border: '1px solid var(--border-frame)',
            }}
          >
            {button.label}
          </button>
        ))}
      </div>
    </div>
  );
};
