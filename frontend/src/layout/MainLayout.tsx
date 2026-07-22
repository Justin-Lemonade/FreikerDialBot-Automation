import type { ReactNode } from 'react';
import type { Customer, SessionSummary } from '../types';

interface Props {
  children: ReactNode;
  showNotes: boolean;
  noteDraft: string;
  onNoteDraftChange: (value: string) => void;
  onSaveNote: () => void;
  onCancelNotes: () => void;
  onToggleNotes: () => void;
  session: SessionSummary | null;
  customer: Customer | null;
  progressLabel: string;
  onOpenStats: () => void;
  onBackHome: () => void;
  onNext: () => void;
}

export const MainLayout = ({
  children,
  showNotes,
  noteDraft,
  onNoteDraftChange,
  onSaveNote,
  onCancelNotes,
  onToggleNotes,
  session,
  customer,
  progressLabel,
  onOpenStats,
  onBackHome,
  onNext,
}: Props) => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-3 pb-24 pt-3 sm:px-4">
        <header className="sticky top-0 z-20 rounded-3xl border border-white/10 bg-slate-900/80 p-3 backdrop-blur">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">Today&apos;s session</p>
              <p className="text-sm font-semibold">Customer {progressLabel}</p>
            </div>
            <button onClick={onOpenStats} className="rounded-full border border-white/10 px-3 py-2 text-sm">
              Stats
            </button>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800">
            <div className="h-full rounded-full bg-emerald-400" style={{ width: `${Math.min(100, ((session?.currentCustomerIndex ?? 0) / Math.max(1, session?.customerCount ?? 1)) * 100)}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-2 text-xs text-slate-400">
            <span>Remaining {session?.estimatedRemaining ?? 31}</span>
            <span>Avg {session?.averageCallTime ?? '2m 18s'}</span>
            <span>Answered {session?.answeredToday ?? 9}</span>
          </div>
        </header>

        <main className="mt-4 flex-1">{children}</main>

        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-slate-950/90 px-3 py-3 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-2">
            <button onClick={onBackHome} className="flex-1 rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-sm font-semibold">Home</button>
            <button onClick={onToggleNotes} className="flex-1 rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-sm font-semibold">Notes</button>
            <button onClick={onNext} className="flex-1 rounded-2xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-slate-950">Next</button>
          </div>
        </div>
      </div>

      {showNotes && (
        <div className="fixed inset-0 z-40 flex items-end bg-slate-950/70">
          <div className="w-full rounded-t-[28px] border border-white/10 bg-slate-900 p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold">Previous Notes</p>
                <p className="text-xs text-slate-400">{customer?.name ?? 'Customer'}</p>
              </div>
              <button onClick={onCancelNotes} className="text-sm text-slate-400">Close</button>
            </div>
            <div className="mb-4 space-y-2 rounded-2xl bg-slate-800/70 p-3">
              {(customer?.notes ?? []).map((note) => (
                <div key={note} className="rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm text-slate-300">
                  • {note}
                </div>
              ))}
            </div>
            <textarea
              value={noteDraft}
              onChange={(event) => onNoteDraftChange(event.target.value)}
              className="min-h-24 w-full rounded-2xl border border-white/10 bg-slate-800 px-3 py-3 text-sm outline-none"
              placeholder="Add a note for this customer"
            />
            <div className="mt-3 flex gap-2">
              <button onClick={onSaveNote} className="flex-1 rounded-2xl bg-emerald-500 px-4 py-3 text-sm font-semibold text-slate-950">Save</button>
              <button onClick={onCancelNotes} className="flex-1 rounded-2xl border border-white/10 px-4 py-3 text-sm">Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
