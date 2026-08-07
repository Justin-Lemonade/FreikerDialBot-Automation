interface Props {
  onOutcome: (outcome: string) => void;
  onMoreInfo: () => void;
  disabled?: boolean;
  moreInfoDisabled?: boolean;
}

/**
 * Didn't Answer is always left, Contacted is always right -- fixed
 * ordering, matches queue_ui.py's own bot keyboard so an operator
 * switching between Telegram chat and the Mini App sees the same
 * layout either way.
 *
 * "Paid" is shown but disabled: the backend has no real "paid" write
 * path anywhere in the codebase (QueueEngine.apply_action's ActionStatus
 * only accepts warned/call_later/skip/invalid_number -- "paid" exists
 * only as a schema-level enum value, never actually written). Stays
 * disabled with an honest "not yet available" state rather than
 * inventing a write path the Telegram bot doesn't share.
 *
 * "Call Again" and the secondary "Note" button that used to live here
 * were both dead: mini_app_api._map_outcome() has no entry for either
 * "call_again" or "note", so tapping them always returned
 * `{"ok": false, "error": "Unsupported outcome: ..."}`. Replaced with
 * "More Info" (a real navigation, not a fake outcome -- see
 * onMoreInfo) per UI pass 4's explicit "replace Call Again with More
 * Info". The Note button that actually works still lives in Home.tsx's
 * bottom row; duplicating a second, broken one here only added clutter.
 */
export const OutcomeButtons = ({ onOutcome, onMoreInfo, disabled, moreInfoDisabled }: Props) => {
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

      <div className="grid grid-cols-3 gap-1.5">
        <button
          onClick={() => onOutcome('wrong_number')}
          disabled={disabled}
          className="retro-button min-h-[44px] px-1 font-display text-[9px] leading-tight disabled:cursor-not-allowed disabled:opacity-40"
          style={{ background: 'var(--bg-panel)', color: 'var(--text-muted)', border: '1px solid var(--border-frame)' }}
        >
          WRONG #
        </button>
        <button
          disabled
          title="Not yet available -- backend has no Paid action yet"
          className="retro-button min-h-[44px] px-1 font-display text-[9px] leading-tight disabled:cursor-not-allowed disabled:opacity-40"
          style={{ background: 'var(--bg-panel)', color: 'var(--text-muted)', border: '1px solid var(--border-frame)' }}
        >
          PAID
        </button>
        <button
          onClick={onMoreInfo}
          disabled={disabled || moreInfoDisabled}
          className="retro-button min-h-[44px] px-1 font-display text-[9px] leading-tight disabled:cursor-not-allowed disabled:opacity-40"
          style={{ background: 'var(--bg-panel)', color: 'var(--accent-green)', border: '1px solid var(--border-frame)' }}
        >
          MORE INFO
        </button>
      </div>
    </div>
  );
};
