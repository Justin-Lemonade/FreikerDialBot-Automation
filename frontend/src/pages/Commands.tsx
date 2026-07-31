interface Props {
  onOpenStatistics: () => void;
  onOpenNotes: () => void;
}

interface CommandButtonProps {
  label: string;
  onClick?: () => void;
  color: string;
  disabled?: boolean;
}

const CommandButton = ({ label, onClick, color, disabled }: CommandButtonProps) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className="retro-button min-h-[52px] w-full font-display text-xs disabled:cursor-not-allowed disabled:opacity-40"
    style={{ background: color, color: 'var(--bg-void)', border: `2px solid ${color}` }}
  >
    [ {label} ]
  </button>
);

/**
 * Secondary-actions page (image 3 reference: bracket-style command
 * buttons + a "type command" field). Statistics and Notes previously
 * lived as bottom-nav buttons; the requested nav shell is Home/
 * Commands/Search/Settings, so they moved here rather than losing a
 * top-level slot. The free-text input below is a structural
 * placeholder -- there's no command-parsing backend yet, so it's
 * disabled and honest about that rather than faking a working REPL.
 */
export const Commands = ({ onOpenStatistics, onOpenNotes }: Props) => {
  return (
    <div className="space-y-4">
      <div className="retro-panel p-4">
        <p className="mb-3 font-display text-[10px]" style={{ color: 'var(--accent-green)' }}>
          SUGGESTED COMMANDS
        </p>
        <div className="space-y-2.5">
          <CommandButton label="VIEW STATISTICS" onClick={onOpenStatistics} color="var(--accent-indigo)" />
          <CommandButton label="SESSION NOTES" onClick={onOpenNotes} color="var(--accent-blue)" />
          <CommandButton label="PAUSE QUEUE" color="var(--accent-purple)" disabled />
          <CommandButton label="EXPORT DATA" color="var(--accent-red)" disabled />
        </div>
      </div>

      <div className="retro-panel p-4">
        <input
          disabled
          placeholder="Type command… (coming soon)"
          className="w-full px-3 py-3 font-data text-lg outline-none disabled:cursor-not-allowed"
          style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)', color: 'var(--text-dim)' }}
        />
      </div>
    </div>
  );
};
