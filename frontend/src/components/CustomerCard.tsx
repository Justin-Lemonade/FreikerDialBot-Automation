import type { Customer } from '../types';

interface Props {
  customer: Customer | null;
  indexLabel?: string;
}

export const CustomerCard = ({ customer, indexLabel }: Props) => {
  if (!customer) {
    return (
      <div className="flex min-h-[240px] items-center justify-center rounded-[28px] border border-white/10 bg-slate-900 p-6 text-center text-slate-400">
        Loading customer…
      </div>
    );
  }

  return (
    <div className="rounded-[32px] border border-white/10 bg-gradient-to-b from-slate-900 to-slate-800 p-5 shadow-2xl">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">
          {indexLabel ? `Customer ${indexLabel}` : 'Current Customer'}
        </p>
        <div className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
          Live
        </div>
      </div>

      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-2xl">
          🙂
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-2xl font-semibold">{customer.name || '(name missing)'}</h2>
          <p className="truncate text-sm text-slate-400">{customer.loanNumber}</p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3">
          <span className="flex items-center gap-2 text-sm text-slate-400">📞 Phone</span>
          <span className="text-base font-semibold">{customer.phone || '—'}</span>
        </div>
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3">
          <span className="flex items-center gap-2 text-sm text-slate-400">💰 Monthly Payment</span>
          <span className="text-base font-semibold">{customer.monthlyPayment || '—'}</span>
        </div>
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3">
          <span className="flex items-center gap-2 text-sm text-slate-400">⏰ Days Overdue</span>
          <span className="text-base font-semibold">{customer.daysLate || '—'}</span>
        </div>
        <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3">
          <span className="flex items-center gap-2 text-sm text-slate-400">💵 Balance</span>
          <span className="text-base font-semibold">{customer.balance || '—'}</span>
        </div>
      </div>

      {customer.isBlacklisted && (
        <div className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-center text-xs font-semibold text-red-300">
          🚫 This customer is blacklisted
        </div>
      )}
    </div>
  );
};
