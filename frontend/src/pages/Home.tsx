import { SessionCard } from '../components/SessionCard';
import type { Customer, SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  customer: Customer | null;
  onContinue: () => void;
  onNewSession: () => void;
  onStatistics: () => void;
  onSettings: () => void;
}

export const Home = ({ session, customer, onContinue, onNewSession, onStatistics, onSettings }: Props) => {
  return (
    <div className="space-y-4">
      <div className="rounded-[32px] border border-white/10 bg-gradient-to-b from-slate-900 to-slate-800 p-5 shadow-2xl">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">Today&apos;s session</p>
        <h1 className="mt-2 text-2xl font-semibold">Morning Calls</h1>
        <p className="mt-2 text-sm text-slate-400">{session?.currentCustomerIndex ?? 17} / {session?.customerCount ?? 48} customers</p>
        <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-800">
          <div className="h-full rounded-full bg-emerald-400" style={{ width: `${Math.min(100, (((session?.currentCustomerIndex ?? 17) / (session?.customerCount ?? 48)) * 100))}%` }} />
        </div>
        <p className="mt-3 text-sm text-slate-300">{Math.round(100 * ((session?.currentCustomerIndex ?? 17) / (session?.customerCount ?? 48)))}% complete</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <SessionCard title="Queue progress" value={`${session?.currentCustomerIndex ?? 17} / ${session?.customerCount ?? 48}`} description="Customers processed" />
        <SessionCard title="Next up" value={customer?.name ?? 'John Smith'} description={customer?.loanNumber ?? 'Loan #123456'} />
      </div>

      <div className="space-y-3">
        <button onClick={onContinue} className="w-full rounded-[28px] bg-emerald-500 px-5 py-4 text-lg font-semibold text-slate-950">▶ Continue Session</button>
        <button onClick={onNewSession} className="w-full rounded-[28px] border border-white/10 bg-slate-900 px-5 py-4 text-lg font-semibold">🆕 New Session</button>
        <div className="grid grid-cols-2 gap-3">
          <button onClick={onStatistics} className="rounded-[24px] border border-white/10 bg-slate-900 px-5 py-4 text-base font-semibold">📊 Statistics</button>
          <button onClick={onSettings} className="rounded-[24px] border border-white/10 bg-slate-900 px-5 py-4 text-base font-semibold">⚙ Settings</button>
        </div>
      </div>
    </div>
  );
};
