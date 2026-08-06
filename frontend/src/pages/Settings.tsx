import type { ReactNode } from 'react';
import { useAppSettings } from '../hooks/useAppSettings';

interface SettingRowProps {
  label: string;
  description: string;
  value: string;
  disabled?: boolean;
}

const SettingRow = ({ label, description, value, disabled }: SettingRowProps) => (
  <div
    className="flex items-center justify-between border-b py-3 last:border-b-0"
    style={{ borderColor: 'var(--border-frame)', opacity: disabled ? 0.45 : 1 }}
  >
    <div>
      <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        {label}
      </p>
      <p className="font-data text-sm" style={{ color: 'var(--text-muted)' }}>
        {description}
      </p>
    </div>
    <div className="font-display text-[9px]" style={{ color: disabled ? 'var(--text-dim)' : 'var(--accent-green)' }}>
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
    <div className="flex items-center justify-between border-b py-3" style={{ borderColor: 'var(--border-frame)' }}>
      <div>
        <p className="font-data text-lg" style={{ color: 'var(--text-primary)' }}>
          Max Call Attempts
        </p>
        <p className="font-data text-sm" style={{ color: 'var(--text-muted)' }}>
          Attempts before "Call Back" stops requeuing
        </p>
      </div>
      <div className="flex gap-1">
        {MAX_ATTEMPTS_OPTIONS.map((option) => {
          const isActive = settings.maxCallAttempts === option.value;
          return (
            <button
              key={option.label}
              onClick={() => updateSettings({ maxCallAttempts: option.value })}
              disabled={isSaving}
              className="retro-button flex h-8 w-8 items-center justify-center font-display text-[10px] disabled:opacity-50"
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
        className="retro-button min-h-[32px] px-3 font-display text-[9px] disabled:opacity-50"
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
 * Framed, sectioned settings (brief: "boxed settings sections, strong
 * section separation"). Telegram Theme, Haptics, Max Call Attempts, and
 * Auto Advance are real, currently-functioning settings (see
 * useTelegram.ts and useAppSettings.ts). Everything else in the later
 * sections is intentionally not wired yet -- structural placeholders
 * per the brief's "design the layout so they can be added later without
 * reworking the whole screen," disabled and labeled "Coming soon"
 * rather than faked as working.
 */
export const Settings = () => {
  return (
    <div className="space-y-3">
      <Section title="APP">
        <SettingRow label="Telegram Theme" description="Uses WebApp theme colors" value="ON" />
        <SettingRow label="Haptics" description="Vibrations for key actions" value="ON" />
      </Section>

      <Section title="CALLING BEHAVIOR">
        <MaxCallAttemptsRow />
        <AutoAdvanceRow />
        <SettingRow label="Call Delay" description="Pause between calls" value="-" disabled />
      </Section>

      <Section title="DISPLAY">
        <SettingRow label="Density" description="Compact vs. detailed cards" value="-" disabled />
        <SettingRow label="Visible Fields" description="Which data shows by default" value="-" disabled />
        <SettingRow label="Animation Intensity" description="Motion for transitions/glow" value="-" disabled />
      </Section>

      <Section title="SEARCH & QUEUE">
        <SettingRow label="Search Defaults" description="Default match fields" value="-" disabled />
        <SettingRow label="Queue Behavior" description="Ordering and skip rules" value="-" disabled />
      </Section>

      <p className="text-center font-data text-sm" style={{ color: 'var(--text-dim)' }}>
        Settings marked — are planned, not yet wired to the backend.
      </p>
    </div>
  );
};
