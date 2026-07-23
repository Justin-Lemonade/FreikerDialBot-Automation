import { SessionCard } from '../components/SessionCard';
import type { Customer, SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  customer: Customer | null;
  upcomingCustomer: Customer | null;
  onContinue: () => void;
  onNewSession: () => void;
  onStatistics: () => void;
  onSettings: () => void;
}

export const Home = ({ session, customer, upcomingCustomer, onContinue, onNewSession, onStatistics, onSettings }: Props) => {
  const hasQueue = Boolean(session?.customerCount);

  return (
    <div className="space-y-4">
      {/* Current + genuinely-preloaded-next customer preview, plus the
          real answered-today count. The running progress bar already
          lives in MainLayout's sticky ProgressHeader; this screen
          doesn't duplicate it. The second card here used to be
          mislabeled "Next up" while actually re-showing the *current*
          customer -- now it shows the real preloaded upcoming customer
          from GET /queue/upcoming, and the current customer gets its
          own correctly-labeled card. */}
      <div className="grid gap-3 grid-cols-2">
        <SessionCard
          title="Answered today"
          value={`${session?.answeredToday ?? 0}`}
          description="Customers contacted"
        />
        <SessionCard
          title="Now calling"
          value={customer?.name || '—'}
          description={customer?.loanNumber || 'No customer queued'}
        />
      </div>
      <div className="grid gap-3 grid-cols-2">
        <SessionCard
          title="Next up"
          value={upcomingCustomer?.name || '—'}
          description={upcomingCustomer?.loanNumber || 'End of queue'}
        />
      </div>

      {/* Primary Actions */}
      <div className="space-y-3">
        <button
          onClick={onContinue}
          disabled={!hasQueue}
          className="min-h-[56px] w-full rounded-[28px] bg-emerald-500 px-5 text-lg font-semibold text-slate-950 active:scale-[0.98] disabled:opacity-50"
        >
          ▶ Continue Session
        </button>
        <button
          onClick={onNewSession}
          disabled={!hasQueue}
          className="min-h-[56px] w-full rounded-[28px] border border-white/10 bg-slate-900 px-5 text-lg font-semibold active:scale-[0.98] disabled:opacity-50"
        >
          🆕 New Session
        </button>
      </div>

      {/* Secondary Actions */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onStatistics}
          className="min-h-[48px] rounded-[24px] border border-white/10 bg-slate-900 px-5 text-base font-semibold active:scale-[0.98]"
        >
          📊 Statistics
        </button>
        <button
          onClick={onSettings}
          className="min-h-[48px] rounded-[24px] border border-white/10 bg-slate-900 px-5 text-base font-semibold active:scale-[0.98]"
        >
          ⚙ Settings
        </button>
      </div>
    </div>
  );
};
