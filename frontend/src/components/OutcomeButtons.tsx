interface Props {
  onOutcome: (outcome: string) => void;
  disabled?: boolean;
}

const buttons = [
  { label: '✅ Contacted', value: 'contacted' },
  { label: '❌ Didn\'t Answer', value: 'did_not_answer' },
  { label: '⚠ Wrong Number', value: 'wrong_number' },
  { label: '💰 Paid', value: 'paid' },
  { label: '📞 Call Again', value: 'call_again' },
  { label: '📝 Add Note', value: 'note' },
];

export const OutcomeButtons = ({ onOutcome, disabled }: Props) => {
  return (
    <div className="grid grid-cols-2 gap-3">
      {buttons.map((button) => (
        <button
          key={button.value}
          onClick={() => onOutcome(button.value)}
          disabled={disabled}
          className="rounded-2xl border border-white/10 bg-slate-900 px-3 py-3 text-sm font-semibold text-slate-100 transition active:scale-[0.98] disabled:opacity-60"
        >
          {button.label}
        </button>
      ))}
    </div>
  );
};
