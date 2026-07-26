import type { ReactNode } from 'react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
}

/**
 * Settings opens as a slide-in panel over the current screen (brief:
 * "should be able to expand, collapse, or slide out in a way that does
 * not prevent the user from continuing the main task" -- i.e. not a
 * bottom-nav destination that replaces the whole screen). Tapping the
 * backdrop or the close button dismisses it without navigating away
 * from whatever screen was open underneath.
 */
export const SettingsDrawer = ({ isOpen, onClose, children }: Props) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        aria-label="Close settings"
        onClick={onClose}
        className="drawer-backdrop absolute inset-0"
        style={{ background: 'rgba(4, 6, 5, 0.7)' }}
      />
      <div
        className="drawer-panel relative flex h-full w-[86%] max-w-sm flex-col overflow-y-auto border-l-2 p-4"
        style={{
          background: 'var(--bg-void)',
          borderColor: 'var(--border-frame)',
          paddingTop: 'max(1rem, env(safe-area-inset-top))',
          paddingBottom: 'max(1rem, env(safe-area-inset-bottom))',
        }}
      >
        <div className="mb-4 flex items-center justify-between">
          <p className="font-display text-sm" style={{ color: 'var(--text-primary)' }}>
            SETTINGS
          </p>
          <button
            onClick={onClose}
            aria-label="Close"
            className="retro-button flex h-9 w-9 items-center justify-center font-display text-sm"
            style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
};
