import type { ReactNode } from 'react';
import { useAppSettings } from '../hooks/useAppSettings';
import type { VisibleField } from '../types';

interface Props {
  isStale?: boolean;
  lastSyncedAt?: number | null;
}

interface SettingRowProps {
  label: string;
  description: string;
  value: string;
  valueColor?: string;
  disabled?: boolean;
}

const SettingRow = ({ label, description, value, valueColor, disabled }: SettingRowProps) => (
  <div
    className="flex items-center justify-between gap-3 border-b py-3 last:border-b-0"
    style={{ borderColor: 'var(--border-frame)', opacity: disabled ? 0.45 : 1 }}
  >
    <div className="min-w-0">
      <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        {label}
      </p>
      <p className="font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        {description}
      </p>
    </div>
    <div
      className="shrink-0 font-display text-[9px]"
      style={{ color: valueColor ?? (disabled ? 'var(--text-dim)' : 'var(--accent-green)') }}
    >
      {value}
    </div>
  </div>
);

const MAX_ATTEMPTS_OPTIONS: { label: string; value: number | null }[] = [
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '3', value: 3 },
  { label: '4', value: 4 },
  { label: '∞', value: null },
];

/**
 * How many times the same customer may be attempted (call_later /
 * "Didn't Answer") before "Call Back" treats them as exhausted and
 * stops requeuing them. Real and backend-enforced -- see
 * QueueEngine.restart_call_later / get_max_call_attempts.
 */
const MaxCallAttemptsRow = () => {
  const { settings, updateSettings, isSaving } = useAppSettings();
  return (
    <div className="border-b py-3" style={{ borderColor: 'var(--border-frame)' }}>
      <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        Max Call Attempts
      </p>
      <p className="mb-2.5 font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        Attempts before "Call Back" stops requeuing
      </p>
      {/* Stacked below the label (not squeezed onto the same row as
          the text) so each option button can hit a real ~44px touch
          target instead of the cramped 32px row that used to sit
          beside the label. */}
      <div className="grid grid-cols-5 gap-1.5">
        {MAX_ATTEMPTS_OPTIONS.map((option) => {
          const isActive = settings.maxCallAttempts === option.value;
          return (
            <button
              key={option.label}
              onClick={() => updateSettings({ maxCallAttempts: option.value })}
              disabled={isSaving}
              className="retro-button flex min-h-[44px] items-center justify-center font-display text-xs disabled:opacity-50"
              style={{
                background: isActive ? 'var(--accent-green)' : 'var(--bg-panel)',
                color: isActive ? 'var(--accent-green-text)' : 'var(--text-muted)',
                border: `1px solid ${isActive ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

/**
 * Whether completing an outcome moves straight to the next customer
 * (current, always-on behavior) or waits for the operator to tap
 * "Next Customer" first. Real: App.tsx reads this to decide whether to
 * apply the next customer immediately or hold it.
 */
const AutoAdvanceRow = () => {
  const { settings, updateSettings, isSaving } = useAppSettings();
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-b-0" style={{ borderColor: 'var(--border-frame)' }}>
      <div>
        <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
          Auto Advance
        </p>
        <p className="font-data text-sm" style={{ color: 'var(--text-muted)' }}>
          Move to next customer automatically
        </p>
      </div>
      <button
        onClick={() => updateSettings({ autoAdvance: !settings.autoAdvance })}
        disabled={isSaving}
        className="retro-button min-h-[44px] min-w-[64px] px-3 font-display text-[10px] disabled:opacity-50"
        style={{
          background: settings.autoAdvance ? 'var(--accent-green)' : 'var(--bg-panel)',
          color: settings.autoAdvance ? 'var(--accent-green-text)' : 'var(--text-muted)',
          border: `1px solid ${settings.autoAdvance ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
        }}
      >
        {settings.autoAdvance ? 'ON' : 'OFF'}
      </button>
    </div>
  );
};

/**
 * Which stored phone number the Call button (and any other
 * auto-display of "the" phone number) tries first. Real and
 * backend-enforced -- see MiniAppService._ordered_phone_numbers.
 * "Second on File" falls back to the first number automatically if a
 * customer only has one, or if the second is blacklisted; nothing here
 * needs to special-case that on the frontend.
 */
const PrimaryPhoneRow = () => {
  const { settings, updateSettings, isSaving } = useAppSettings();
  const options: { label: string; value: 'first' | 'second' }[] = [
    { label: 'First on File', value: 'first' },
    { label: 'Second on File', value: 'second' },
  ];
  return (
    <div className="border-b py-3" style={{ borderColor: 'var(--border-frame)' }}>
      <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        Primary Phone Preference
      </p>
      <p className="mb-2.5 font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        Which number the Call button dials first
      </p>
      <div className="grid grid-cols-2 gap-1.5">
        {options.map((option) => {
          const isActive = settings.primaryPhonePreference === option.value;
          return (
            <button
              key={option.value}
              onClick={() => updateSettings({ primaryPhonePreference: option.value })}
              disabled={isSaving}
              className="retro-button flex min-h-[44px] items-center justify-center px-2 text-center font-display text-[10px] disabled:opacity-50"
              style={{
                background: isActive ? 'var(--accent-green)' : 'var(--bg-panel)',
                color: isActive ? 'var(--accent-green-text)' : 'var(--text-muted)',
                border: `1px solid ${isActive ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

const PRE_READY_OPTIONS: { label: string; value: number }[] = [
  { label: 'None', value: 0 },
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '3', value: 3 },
];

/**
 * How many upcoming customers App.tsx eagerly previews via
 * GET /queue/upcoming?count=N ahead of the active one. Real and
 * backend-enforced -- see MiniAppService.queue_upcoming's count param.
 */
const PreReadyCountRow = () => {
  const { settings, updateSettings, isSaving } = useAppSettings();
  return (
    <div className="border-b py-3" style={{ borderColor: 'var(--border-frame)' }}>
      <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        Pre-ready Count
      </p>
      <p className="mb-2.5 font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        How many customers stay pre-fetched
      </p>
      <div className="grid grid-cols-4 gap-1.5">
        {PRE_READY_OPTIONS.map((option) => {
          const isActive = settings.preReadyCount === option.value;
          return (
            <button
              key={option.value}
              onClick={() => updateSettings({ preReadyCount: option.value })}
              disabled={isSaving}
              className="retro-button flex min-h-[44px] items-center justify-center font-display text-xs disabled:opacity-50"
              style={{
                background: isActive ? 'var(--accent-green)' : 'var(--bg-panel)',
                color: isActive ? 'var(--accent-green-text)' : 'var(--text-muted)',
                border: `1px solid ${isActive ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

const VISIBLE_FIELD_OPTIONS: { label: string; value: VisibleField }[] = [
  { label: 'Days Overdue', value: 'daysOverdue' },
  { label: 'Monthly', value: 'monthlyPayment' },
  { label: 'Balance', value: 'balance' },
];

/**
 * Which financial fields CustomerCard's info grid shows. Real and
 * backend-enforced -- see MiniAppService.get_settings/update_settings's
 * visibleFields and CustomerCard's FIELD_DEFS. Multi-select: each chip
 * toggles independently, and the grid on Home actually gains/loses a
 * column as chips are toggled -- there's no separate "apply" step.
 */
const VisibleFieldsRow = () => {
  const { settings, updateSettings, isSaving } = useAppSettings();
  const toggle = (field: VisibleField) => {
    const next = settings.visibleFields.includes(field)
      ? settings.visibleFields.filter((f) => f !== field)
      : [...settings.visibleFields, field];
    updateSettings({ visibleFields: next });
  };
  return (
    <div className="border-b py-3" style={{ borderColor: 'var(--border-frame)' }}>
      <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        Visible Fields
      </p>
      <p className="mb-2.5 font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        Which fields show on the calling card
      </p>
      <div className="grid grid-cols-3 gap-1.5">
        {VISIBLE_FIELD_OPTIONS.map((option) => {
          const isActive = settings.visibleFields.includes(option.value);
          return (
            <button
              key={option.value}
              onClick={() => toggle(option.value)}
              disabled={isSaving}
              className="retro-button flex min-h-[44px] items-center justify-center px-1 text-center font-display text-[9px] disabled:opacity-50"
              style={{
                background: isActive ? 'var(--accent-green)' : 'var(--bg-panel)',
                color: isActive ? 'var(--accent-green-text)' : 'var(--text-muted)',
                border: `1px solid ${isActive ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
};

/** Real: reflects the actual last successful GET /session/current
 * (useSession's lastSyncedAt) and whether the app is currently showing
 * stale data (isStale) -- not a decorative "connected" dot. */
const DiagnosticsSection = ({ isStale, lastSyncedAt }: Props) => {
  const syncLabel = (() => {
    if (!lastSyncedAt) return 'Not yet synced';
    const seconds = Math.round((Date.now() - lastSyncedAt) / 1000);
    if (seconds < 5) return 'Just now';
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    return `${minutes}m ago`;
  })();

  return (
    <>
      <SettingRow
        label="Backend Connectivity"
        description="Last request to the Mini App API"
        value={isStale ? 'RECONNECTING' : 'CONNECTED'}
        valueColor={isStale ? 'var(--accent-red)' : 'var(--accent-green)'}
      />
      <SettingRow label="Sync Status" description="Last successful session refresh" value={syncLabel} />
    </>
  );
};

interface SectionProps {
  title: string;
  children: ReactNode;
}

const Section = ({ title, children }: SectionProps) => (
  <div className="retro-panel p-4">
    <p className="mb-2 font-display text-[10px]" style={{ color: 'var(--text-muted)' }}>
      {title}
    </p>
    {children}
  </div>
);

/**
 * Framed, sectioned settings, grouped per the UI pass 3 brief's
 * category list. Real, backend-enforced or otherwise genuinely
 * functioning settings: Telegram Theme and Haptics (useTelegram.ts --
 * always on, since there's no toggle for either yet, but the row
 * describes real current behavior, not a guess), Max Call Attempts and
 * Auto Advance (useAppSettings.ts / GET/POST /settings), and Backend
 * Connectivity / Sync Status (useSession.ts's isStale/lastSyncedAt).
 *
 * Everything else is an honest, disabled "Coming soon" placeholder --
 * grouped into the right category now so adding the real control later
 * doesn't require reworking the whole screen, per the brief's own
 * instruction not to invent backend behavior to fill these in.
 */
export const Settings = ({ isStale, lastSyncedAt }: Props) => {
  return (
    <div className="space-y-3">
      <Section title="CALLING BEHAVIOR">
        <MaxCallAttemptsRow />
        <AutoAdvanceRow />
        <SettingRow label="Call Delay" description="Pause between calls" value="-" disabled />
        <SettingRow label="Next-Customer Hold" description="How long to hold before advancing" value="-" disabled />
        <SettingRow label="Retry / Callback Behavior" description="Ordering when 'Call Back' requeues" value="-" disabled />
      </Section>

      <Section title="PHONE HANDLING">
        <SettingRow label="Show Both Numbers" description="Always on -- see the call card" value="ON" />
        <PrimaryPhoneRow />
        <SettingRow label="Quick Number Switching" description="Tap a number on the call card to make it active" value="ON" />
        <SettingRow label="Tap-to-Dial" description="Always on for every number on file" value="ON" />
      </Section>

      <Section title="DISPLAY">
        <SettingRow label="Compact vs Expanded Cards" description="Card density on Home" value="-" disabled />
        <VisibleFieldsRow />
        <SettingRow label="Progress Density" description="Progress bar detail level" value="-" disabled />
        <SettingRow label="Notes Preview" description="Show latest note on the call card" value="-" disabled />
      </Section>

      <Section title="QUEUE">
        <PreReadyCountRow />
        {/* Not a togglable choice: the customers table is the single
            source of queue truth (AGENTS.md "What to preserve" --
            deterministic queue, single source of customer state).
            New imports get a later import_timestamp and are ordered
            by get_next_actionable_customer's ORDER BY import_timestamp
            ASC, id ASC -- they join the same active queue after
            everyone already waiting. A second/separate queue isn't
            something the current architecture supports, so this row
            documents the real behavior instead of offering a fake
            choice between two options that don't both exist. */}
        <SettingRow label="Active Queue vs New Contacts" description="New imports join the same active queue" value="Merged" />
        {/* Also not a togglable choice: SessionManager.current_session
            always derives the in-progress session live from the
            database (see session_manager.py) -- there is no
            browser/local session state to lose, so reopening always
            resumes the same real session rather than offering a
            choice between "resume" and "restart" that would require
            inventing a second, fake session-state mechanism. */}
        <SettingRow label="Resume / Restart Behavior" description="Reopening always resumes the live session" value="Always Resumes" />
      </Section>

      <Section title="SEARCH">
        <SettingRow label="Highlight Matched Fields" description="Always on -- see Search results" value="ON" />
        <SettingRow label="Keyboard-Safe Layout" description="Always on -- input stays reachable" value="ON" />
        <SettingRow label="Default Search Fields" description="Which fields are searched by default" value="-" disabled />
      </Section>

      <Section title="APPEARANCE">
        {/* Was previously claimed "ON -- Uses WebApp theme colors", but
            nothing in the codebase reads window.Telegram.WebApp
            .themeParams or calls setHeaderColor/setBackgroundColor --
            grep confirms zero references. That claim was false, found
            during this pass's independent bug hunt (section 19: "fake
            settings"). The retro-spacecraft palette is a deliberate,
            fixed design (this pass's own brief: "preserve... spacecraft
            atmosphere"), not something that should flip to Telegram's
            theme -- so the fix is correcting the claim, not building
            real theme integration that would undermine the intended
            look. */}
        <SettingRow label="Telegram Theme" description="Uses the app's own fixed retro palette, not Telegram's theme" value="Custom" />
        <SettingRow label="Haptics" description="Vibrations for key actions" value="ON" />
        <SettingRow label="Accent Color" description="Override the default green accent" value="-" disabled />
        <SettingRow label="Animation Intensity" description="Motion for transitions/glow" value="-" disabled />
      </Section>

      <Section title="LANGUAGE">
        <SettingRow label="English" description="Current interface language" value="ACTIVE" />
        <SettingRow label="Russian" description="Русский" value="-" disabled />
        <SettingRow label="Tajik" description="Тоҷикӣ" value="-" disabled />
      </Section>

      <Section title="ADMIN / DIAGNOSTICS">
        <DiagnosticsSection isStale={isStale} lastSyncedAt={lastSyncedAt} />
        <SettingRow label="Version Info" description="Build/version identifier" value="-" disabled />
      </Section>

      <p className="text-center font-data text-sm" style={{ color: 'var(--text-dim)' }}>
        Settings marked — are planned, not yet wired to the backend.
      </p>
    </div>
  );
};
