import type { SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  onContinueSession: () => void;
  onOpenUpload: () => void;
  onOpenSettings: () => void;
  onOpenSearch: () => void;
  onOpenCommands: () => void;
}

/**
 * The real Home screen -- a command center, not the calling workflow.
 * Always the screen the app launches to and the screen the bottom nav's
 * Home button returns to from anywhere (App.tsx keeps the 'home' screen
 * id for exactly this reason). The live call workflow moved to its own
 * 'calling' screen, entered only via "Continue Session" below.
 *
 * hasQueue mirrors the same real backend signal the old merged
 * Home/calling screen used (session.customerCount > 0) -- Welcome Back
 * with Upload Contacts when there's nothing loaded yet, Continue
 * Session plus a real queue summary once there is.
 */
export const Landing = ({ session, onContinueSession, onOpenUpload, onOpenSettings, onOpenSearch, onOpenCommands }: Props) => {
  const hasQueue = Boolean(session?.customerCount);
  const remaining = session ? Math.max(0, session.customerCount - session.currentCustomerIndex + 1) : 0;

  return (
    // Fills exactly the space MainLayout's <main> has left after its own
    // chrome (top bar, pt-4, and the pb-28 reserved for the fixed bottom
    // nav) -- flex-1 on a flex-column parent, not a guessed dvh/rem
    // constant. The previous `min-h-[calc(100dvh-8.5rem)]` assumed a
    // fixed 8.5rem of chrome, but <main>'s own pb-28 (7rem) already
    // reserves the bottom-nav space independently, so the two allowances
    // stacked and this screen overflowed (forcing a scrollbar) on any
    // viewport where the top bar wasn't exactly 1.5rem tall. Letting
    // flexbox measure the real remaining space removes the guess
    // entirely -- see AGENTS.md "prefer the smallest correct change."
    <div className="-mx-4 -mt-4 flex min-h-0 flex-1 flex-col retro-starfield">
      <div className="flex flex-1 flex-col items-center justify-center gap-6 overflow-y-auto p-6 text-center">
        {/* Logo -- also present in the persistent top bar, but repeated
            here large and centered so this screen reads as a command
            center on its own, not a stripped-down version of another
            screen. */}
        <div>
          <p
            className="font-display text-3xl leading-relaxed"
            style={{ color: 'var(--text-primary)', textShadow: '0 0 12px rgba(238, 244, 240, 0.6), 0 0 24px rgba(111, 224, 138, 0.3)' }}
          >
            FREIKER DIAL
          </p>
          <p className="mt-2 font-display text-lg tracking-wide" style={{ color: 'var(--accent-green)' }}>
            WELCOME BACK
          </p>
        </div>

        {/* Queue summary -- real backend numbers (session.customerCount /
            currentCustomerIndex), the same fields the progress header
            uses elsewhere, not a separate guess. */}
        {hasQueue && (
          <div className="retro-panel w-full max-w-xs p-4">
            <p className="font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
              QUEUE SUMMARY
            </p>
            <p className="mt-1 font-data text-2xl" style={{ color: 'var(--text-primary)' }}>
              {remaining} of {session?.customerCount} remaining
            </p>
            {typeof session?.answeredToday === 'number' && (
              <p className="mt-1 font-data text-base" style={{ color: 'var(--text-muted)' }}>
                {session.answeredToday} contacted today
              </p>
            )}
          </div>
        )}

        <div className="w-full max-w-xs space-y-3">
          {hasQueue ? (
            <button
              onClick={onContinueSession}
              className="retro-button min-h-[56px] w-full font-display text-xs"
              style={{ background: 'var(--accent-blue)', color: 'var(--accent-blue-text)', border: '2px solid var(--accent-blue)' }}
            >
              ▶ CONTINUE SESSION
            </button>
          ) : (
            <button
              onClick={onOpenUpload}
              className="retro-button min-h-[56px] w-full font-display text-xs"
              style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
            >
              UPLOAD CONTACTS
            </button>
          )}

          {/* Secondary actions -- Search / Commands / Settings all
              already exist as their own screens; these are just
              command-center shortcuts to them, not new capability. */}
          <div className="grid grid-cols-2 gap-2 pt-2">
            <button
              onClick={onOpenSearch}
              className="retro-button min-h-[44px] font-display text-[9px]"
              style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
            >
              ⌕ SEARCH
            </button>
            <button
              onClick={onOpenCommands}
              className="retro-button min-h-[44px] font-display text-[9px]"
              style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
            >
              ▤ COMMANDS
            </button>
          </div>
          <button
            onClick={onOpenSettings}
            className="retro-button min-h-[44px] w-full font-display text-[9px]"
            style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
          >
            ⚙ SETTINGS
          </button>
          {hasQueue && (
            <button
              onClick={onOpenUpload}
              className="retro-button min-h-[44px] w-full font-display text-[9px]"
              style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
            >
              UPLOAD MORE CONTACTS
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
