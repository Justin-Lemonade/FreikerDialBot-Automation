import type { ReactNode } from 'react';

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
 * section separation"). Telegram Theme and Haptics are real, currently-
 * functioning settings (see useTelegram.ts). Everything else in the
 * later sections is intentionally not wired yet -- structural
 * placeholders per the brief's "design the layout so they can be added
 * later without reworking the whole screen," disabled and labeled
 * "Coming soon" rather than faked as working.
 */
export const Settings = () => {
  return (
    <div className="space-y-3">
      <Section title="APP">
        <SettingRow label="Telegram Theme" description="Uses WebApp theme colors" value="ON" />
        <SettingRow label="Haptics" description="Vibrations for key actions" value="ON" />
      </Section>

      <Section title="CALLING BEHAVIOR">
        <SettingRow label="Recall Attempts" description="Retries before skipping" value="-" disabled />
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
