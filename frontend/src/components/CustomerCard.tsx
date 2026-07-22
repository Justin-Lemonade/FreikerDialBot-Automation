import type { Customer } from '../types';

interface Props {
  customer: Customer | null;
  indexLabel: string;
}

export const CustomerCard = ({ customer, indexLabel }: Props) => {
  if (!customer) {
    return <div className="rounded-[28px] border border-white/10 bg-slate-900 p-6 text-center text-slate-400">Loading customer…</div>;
  }

  return (
    <div className="rounded-[32px] border border-white/10 bg-gradient-to-b from-slate-900 to-slate-800 p-5 shadow-2xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">Customer</p>
          <p className="text-lg font-semibold">{indexLabel}</p>
        </div>
        <div className="rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3 py-1 text-sm text-emerald-300">Live</div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="mb-2 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/20 text-2xl">👤</div>
          <h2 className="text-2xl font-semibold">{customer.name}</h2>
          <p className="text-sm text-slate-400">{customer.loanNumber}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-3">
            <p className="text-slate-400">Balance</p>
            <p className="mt-1 font-semibold">{customer.balance} SM</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-3">
            <p className="text-slate-400">Days Late</p>
            <p className="mt-1 font-semibold">{customer.daysLate}</p>
          </div>
        </div>

        <div className="rounded-2xl border border-white/10 bg-slate-900/70 p-3">
          <p className="text-slate-400">Phone</p>
          <p className="mt-1 font-semibold">{customer.phone}</p>
        </div>
      </div>
    </div>
  );
};
