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
      className="w-full rounded-[28px] bg-emerald-500 px-5 py-4 text-lg font-semibold text-slate-950 shadow-lg shadow-emerald-500/20 transition active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
    >
      {label}
    </button>
  );
};
