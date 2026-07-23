import type { SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  onRetry: () => void;
  onHome: () => void;
}

export const SessionComplete = ({ session, onRetry, onHome }: Props) => {
  const contacted = session?.progress?.contacted;
  const didNotAnswer = session?.progress?.didNotAnswer;
  const hasBreakdown = contacted !== undefined && didNotAnswer !== undefined;

  return (
    <div className="space-y-4">
      <div className="rounded-[32px] border border-emerald-400/20 bg-gradient-to-b from-emerald-500/10 to-slate-900 p-6 text-center shadow-2xl">
        <p className="text-[11px] uppercase tracking-[0.3em] text-emerald-300">Session complete</p>
        <h2 className="mt-3 text-3xl font-semibold">{session?.customerCount ?? 0} customers processed</h2>
        {hasBreakdown && (
          <p className="mt-2 text-sm text-slate-400">
            {contacted} contacted • {didNotAnswer} didn&apos;t answer
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onRetry}
          className="min-h-[56px] rounded-[28px] border border-white/10 bg-slate-900 px-5 text-base font-semibold active:scale-[0.98]"
        >
          Retry Didn&apos;t Answer
        </button>
        <button className="min-h-[56px] rounded-[28px] border border-white/10 bg-slate-900 px-5 text-base font-semibold active:scale-[0.98]">
          Export
        </button>
      </div>
      <button
        onClick={onHome}
        className="min-h-[56px] w-full rounded-[28px] bg-emerald-500 px-5 text-lg font-semibold text-slate-950 active:scale-[0.98]"
      >
        Return Home
      </button>
    </div>
  );
};
