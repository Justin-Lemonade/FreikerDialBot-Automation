import type { ReactNode } from 'react';
import type { Customer, Screen, SessionSummary } from '../types';
import { ProgressHeader } from '../components/ProgressHeader';
import { SettingsDrawer } from '../components/SettingsDrawer';
import { Settings } from '../pages/Settings';

interface Props {
  children: ReactNode;
  showNotes: boolean;
  noteDraft: string;
  onNoteDraftChange: (value: string) => void;
  onSaveNote: () => void;
  onCancelNotes: () => void;
  session: SessionSummary | null;
  customer: Customer | null;
  onNavigateHome: () => void;
  onNavigateCommands: () => void;
  onNavigateSearch: () => void;
  activeScreen: Screen;
  isSettingsOpen: boolean;
  onOpenSettings: () => void;
  onCloseSettings: () => void;
  isStale?: boolean;
  lastSyncedAt?: number | null;
  bannerError?: string | null;
  onDismissError?: () => void;
}

const NAV_ITEMS: { key: 'home' | 'commands' | 'search'; label: string; icon: string; matches: Screen[] }[] = [
  { key: 'home', label: 'HOME', icon: '⌂', matches: ['home', 'complete'] },
  { key: 'search', label: 'SEARCH', icon: '⌕', matches: ['search', 'customerDetail'] },
  { key: 'commands', label: 'CMDS', icon: '▤', matches: ['commands', 'statistics'] },
];

// Progress is the calling-workflow anchor, not a global page header --
// per the UI pass 3 brief ("show progress only on Home / Calling
// screens"), it takes up sticky vertical space that Search and Commands
// need for their own content (results, keyboard-safe layout, stats).
const SCREENS_WITH_PROGRESS: Screen[] = ['home', 'complete'];

export const MainLayout = ({
  children,
  showNotes,
  noteDraft,
  onNoteDraftChange,
  onSaveNote,
  onCancelNotes,
  session,
  customer,
  onNavigateHome,
  onNavigateCommands,
  onNavigateSearch,
  activeScreen,
  isSettingsOpen,
  onOpenSettings,
  onCloseSettings,
  isStale,
  lastSyncedAt,
  bannerError,
  onDismissError,
}: Props) => {
  const currentIndex = session?.currentCustomerIndex ?? 0;
  const totalCount = session?.customerCount ?? 0;
  const progressPercent = session?.progress?.percent ?? (totalCount ? Math.round((currentIndex / totalCount) * 100) : 0);
  const showProgress = SCREENS_WITH_PROGRESS.includes(activeScreen);

  const navHandlers: Record<'home' | 'commands' | 'search', () => void> = {
    home: onNavigateHome,
    commands: onNavigateCommands,
    search: onNavigateSearch,
  };

  return (
    <div className="flex min-h-[100dvh] flex-col font-data" style={{ background: 'var(--bg-void)', color: 'var(--text-primary)' }}>
      {/* Top app bar -- logo left, settings gear right. Present on every
          screen (brief: "logo at the top of every page", "top-right
          gear/settings icon" as a critical element to keep). */}
      <div
        className="flex items-center justify-between border-b-2 px-4 py-3"
        style={{ borderColor: 'var(--border-frame)', background: 'var(--bg-void)', paddingTop: 'max(0.75rem, env(safe-area-inset-top))' }}
      >
        <span className="font-display text-sm" style={{ color: 'var(--text-primary)' }}>
          FREIKER DIAL
        </span>
        <button
          onClick={onOpenSettings}
          aria-label="Open settings"
          className="retro-button flex h-9 w-9 items-center justify-center text-lg"
          style={{ color: 'var(--text-muted)' }}
        >
          ⚙
        </button>
      </div>

      {/* PROGRESS -- sticky, shown only on Home/calling-related screens
          (see SCREENS_WITH_PROGRESS) so Search and Commands get the
          full viewport instead. Every number below comes straight from
          the backend; there is no client-side placeholder here. */}
      {showProgress && (
        <ProgressHeader currentIndex={currentIndex} totalCount={totalCount} progressPercent={progressPercent} />
      )}

      {(isStale || bannerError) && (
        <div
          className="px-4 py-2 text-center font-data text-sm"
          style={{ background: 'rgba(224, 85, 90, 0.1)', color: 'var(--accent-red)' }}
        >
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

      <main className="flex-1 overflow-y-auto overflow-x-hidden px-4 pb-28 pt-4">{children}</main>

      {/* Bottom nav -- Home / Search / Commands. Settings lives in the
          top-right gear + slide-out drawer instead, so it isn't
          duplicated in two places (brief: "remove the duplicate bottom
          settings control if the top-right gear already handles
          settings"). */}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 border-t-2 px-2 pt-2"
        style={{ borderColor: 'var(--border-frame)', background: 'var(--bg-void)', paddingBottom: 'max(0.5rem, env(safe-area-inset-bottom))' }}
      >
        <div className="flex items-center gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive = item.matches.includes(activeScreen);
            return (
              <button
                key={item.key}
                onClick={navHandlers[item.key]}
                className={`nav-tab flex min-h-[52px] flex-1 flex-col items-center justify-center gap-0.5 ${isActive ? 'is-active' : ''}`}
                style={{ color: isActive ? 'var(--accent-green)' : 'var(--text-muted)' }}
              >
                <span className="nav-tab-icon text-lg">{item.icon}</span>
                <span className="font-display text-[8px]">{item.label}</span>
              </button>
            );
          })}
        </div>
      </nav>

      <SettingsDrawer isOpen={isSettingsOpen} onClose={onCloseSettings}>
        <Settings isStale={isStale} lastSyncedAt={lastSyncedAt} />
      </SettingsDrawer>

      {showNotes && (
        <div className="fixed inset-0 z-40 flex items-end" style={{ background: 'rgba(4, 6, 5, 0.75)' }}>
          <div
            className="w-full border-t-2 p-4"
            style={{
              background: 'var(--bg-panel-solid)',
              borderColor: 'var(--border-frame-bright)',
              paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
            }}
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="font-display text-[10px]" style={{ color: 'var(--text-primary)' }}>
                  PREVIOUS NOTES
                </p>
                <p className="font-data text-base" style={{ color: 'var(--text-muted)' }}>
                  {customer?.name ?? 'Customer'}
                </p>
              </div>
              <button onClick={onCancelNotes} className="min-h-[48px] min-w-[48px] font-display text-[10px]" style={{ color: 'var(--text-muted)' }}>
                CLOSE
              </button>
            </div>
            <div
              className="mb-4 max-h-40 space-y-2 overflow-y-auto p-3"
              style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)' }}
            >
              {(customer?.notes ?? []).map((note, index) => (
                <div
                  key={`${index}-${note.slice(0, 20)}`}
                  className="px-3 py-2 font-data text-base"
                  style={{ background: 'var(--bg-panel-raised)', border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
                >
                  • {note}
                </div>
              ))}
            </div>
            <textarea
              value={noteDraft}
              onChange={(event) => onNoteDraftChange(event.target.value)}
              className="min-h-24 w-full p-3 font-data text-lg outline-none"
              style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
              placeholder="Add a note for this customer"
            />
            <div className="mt-3 flex gap-2">
              <button
                onClick={onSaveNote}
                className="retro-button min-h-[48px] flex-1 font-display text-[10px]"
                style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
              >
                SAVE
              </button>
              <button
                onClick={onCancelNotes}
                className="retro-button min-h-[48px] flex-1 font-display text-[10px]"
                style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
              >
                CANCEL
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
