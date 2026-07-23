import type { ReactNode } from 'react';
import type { Customer, SessionSummary } from '../types';
import { ProgressHeader } from '../components/ProgressHeader';

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
  onOpenStats: () => void;
  onBackHome: () => void;
  onNext: () => void;
  isStale?: boolean;
  bannerError?: string | null;
  onDismissError?: () => void;
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
  onOpenStats,
  onBackHome,
  onNext,
  isStale,
  bannerError,
  onDismissError,
}: Props) => {
  const currentIndex = session?.currentCustomerIndex ?? 0;
  const totalCount = session?.customerCount ?? 0;
  const progressPercent = session?.progress?.percent ?? (totalCount ? Math.round((currentIndex / totalCount) * 100) : 0);
  const remaining = session?.progress?.remaining ?? session?.estimatedRemaining ?? 0;
  const averageTime = session?.averageCallTime ?? '0s';

  return (
    <div className="flex min-h-[100dvh] flex-col bg-slate-950 text-slate-100">
      {/* 1. PROGRESS -- sticky, always visible, the anchor of the app.
          Every number below comes straight from the backend; there is
          no client-side placeholder or fallback constant anywhere here. */}
      <ProgressHeader
        currentIndex={currentIndex}
        totalCount={totalCount}
        progressPercent={progressPercent}
        remaining={remaining}
        averageTime={averageTime}
      />

      {(isStale || bannerError) && (
        <div className="bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-300">
          {bannerError ? (
            <span>
              {bannerError}{' '}
              {onDismissError && (
                <button onClick={onDismissError} className="ml-2 underline">
                  Dismiss
                </button>
              )}
            </span>
          ) : (
            <span>Showing last known data — reconnecting…</span>
          )}
        </div>
      )}

      {/* 2-4. Current Customer / Primary Actions / Secondary Actions */}
      <main className="flex-1 overflow-y-auto px-4 pb-28 pt-4">{children}</main>

      {/* 5. NAVIGATION -- fixed bottom bar, safe-area aware */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 border-t border-white/10 bg-slate-950/95 px-4 pt-3 backdrop-blur"
        style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
      >
        <div className="flex items-center gap-2">
          <button
            onClick={onBackHome}
            className="min-h-[48px] flex-1 rounded-2xl border border-white/10 bg-slate-900 px-4 text-sm font-semibold active:scale-[0.97]"
          >
            Home
          </button>
          <button
            onClick={onToggleNotes}
            className="min-h-[48px] flex-1 rounded-2xl border border-white/10 bg-slate-900 px-4 text-sm font-semibold active:scale-[0.97]"
          >
            Notes
          </button>
          <button
            onClick={onOpenStats}
            className="min-h-[48px] flex-1 rounded-2xl border border-white/10 bg-slate-900 px-4 text-sm font-semibold active:scale-[0.97]"
          >
            Stats
          </button>
          <button
            onClick={onNext}
            className="min-h-[48px] flex-1 rounded-2xl bg-emerald-500 px-4 text-sm font-semibold text-slate-950 active:scale-[0.97]"
          >
            Next
          </button>
        </div>
      </nav>

      {showNotes && (
        <div className="fixed inset-0 z-40 flex items-end bg-slate-950/70">
          <div
            className="w-full rounded-t-[28px] border border-white/10 bg-slate-900 p-4 shadow-2xl"
            style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold">Previous Notes</p>
                <p className="text-xs text-slate-400">{customer?.name ?? 'Customer'}</p>
              </div>
              <button onClick={onCancelNotes} className="min-h-[48px] min-w-[48px] text-sm text-slate-400">
                Close
              </button>
            </div>
            <div className="mb-4 max-h-40 space-y-2 overflow-y-auto rounded-2xl bg-slate-800/70 p-3">
              {(customer?.notes ?? []).map((note, index) => (
                <div
                  key={`${index}-${note.slice(0, 20)}`}
                  className="rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2 text-sm text-slate-300"
                >
                  • {note}
                </div>
              ))}
            </div>
            <textarea
              value={noteDraft}
              onChange={(event) => onNoteDraftChange(event.target.value)}
              className="min-h-24 w-full rounded-2xl border border-white/10 bg-slate-800 px-3 py-3 text-base outline-none"
              placeholder="Add a note for this customer"
            />
            <div className="mt-3 flex gap-2">
              <button
                onClick={onSaveNote}
                className="min-h-[48px] flex-1 rounded-2xl bg-emerald-500 px-4 text-sm font-semibold text-slate-950 active:scale-[0.97]"
              >
                Save
              </button>
              <button
                onClick={onCancelNotes}
                className="min-h-[48px] flex-1 rounded-2xl border border-white/10 px-4 text-sm active:scale-[0.97]"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
