import { SessionCard } from '../components/SessionCard';
import type { Customer, SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  customer: Customer | null;
  upcomingCustomer: Customer | null;
  onContinue: () => void;
  onNewSession: () => void;
}

export const Home = ({ session, customer, upcomingCustomer, onContinue, onNewSession }: Props) => {
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

      {/* Upload -- shell/placeholder only. Importing customer data is
          currently Telegram-only (screenshot/JSON/text paste directly
          in chat with the bot); there is no Mini App upload endpoint
          yet. This is an honest placeholder, not a working feature --
          see BACKLOG.md's Mini-App-side import item. */}
      <button
        disabled
        title="Not yet available -- import customer data via Telegram chat with the bot for now"
        className="min-h-[48px] w-full rounded-[24px] border border-dashed border-white/10 bg-slate-900/40 px-5 text-sm font-semibold text-slate-500"
      >
        📤 Upload Customers (coming soon — use Telegram chat for now)
      </button>
    </div>
  );
};
