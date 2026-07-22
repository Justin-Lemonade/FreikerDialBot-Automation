interface Props {
  session: {
    currentCustomerIndex?: number;
    customerCount?: number;
  } | null;
  onRetry: () => void;
  onHome: () => void;
}

export const SessionComplete = ({ session, onRetry, onHome }: Props) => {
  return (
    <div className="space-y-4">
      <div className="rounded-[32px] border border-emerald-400/20 bg-gradient-to-b from-emerald-500/10 to-slate-900 p-6 text-center shadow-2xl">
        <p className="text-[11px] uppercase tracking-[0.3em] text-emerald-300">Session complete</p>
        <h2 className="mt-3 text-3xl font-semibold">{session?.customerCount ?? 48} customers processed</h2>
        <p className="mt-2 text-sm text-slate-400">31 contacted • 12 didn&apos;t answer • 3 wrong number • 2 paid</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <button onClick={onRetry} className="rounded-[28px] border border-white/10 bg-slate-900 px-5 py-4 text-lg font-semibold">Retry didn&apos;t answer</button>
        <button className="rounded-[28px] border border-white/10 bg-slate-900 px-5 py-4 text-lg font-semibold">Export</button>
      </div>
      <button onClick={onHome} className="w-full rounded-[28px] bg-emerald-500 px-5 py-4 text-lg font-semibold text-slate-950">Return Home</button>
    </div>
  );
};
