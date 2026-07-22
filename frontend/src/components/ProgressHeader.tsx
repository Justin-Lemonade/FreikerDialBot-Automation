interface Props {
  label: string;
  progressPercent: number;
  remaining: number;
  averageTime: string;
  answered: number;
}

export const ProgressHeader = ({ label, progressPercent, remaining, averageTime, answered }: Props) => {
  return (
    <div className="mb-4 rounded-[24px] border border-white/10 bg-slate-900/70 p-3">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-semibold">{label}</span>
        <span className="text-slate-400">{progressPercent}%</span>
      </div>
      <div className="mb-2 h-2 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full bg-emerald-400" style={{ width: `${progressPercent}%` }} />
      </div>
      <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-400">
        <span>Remaining {remaining}</span>
        <span>Avg {averageTime}</span>
        <span>Answered {answered}</span>
      </div>
    </div>
  );
};
