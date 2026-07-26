interface Props {
  label: string;
  onClick: () => void;
  disabled?: boolean;
}

export const CallButton = ({ label, onClick, disabled }: Props) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="retro-button min-h-[56px] w-full font-display text-sm disabled:cursor-not-allowed disabled:opacity-50"
      style={{
        background: 'var(--accent-green)',
        color: 'var(--accent-green-text)',
        border: '2px solid var(--accent-green-strong)',
        boxShadow: disabled ? 'none' : '0 3px 0 var(--accent-green-strong)',
      }}
    >
      {label}
    </button>
  );
};
