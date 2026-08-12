import { createContext, useContext } from 'react';
import type { AppSettings } from '../types';

/** The fixed backend-matching defaults -- see AppSettingsProvider in
 * useAppSettings.tsx for why these must match MiniAppService.get_settings's
 * own defaults exactly. */
export const DEFAULT_SETTINGS: AppSettings = {
  maxCallAttempts: null,
  autoAdvance: true,
  primaryPhonePreference: 'first',
  preReadyCount: 0,
  visibleFields: ['daysOverdue', 'monthlyPayment'],
  cardDensity: 'expanded',
  progressDensity: 'normal',
  notesPreview: false,
  defaultSearchFields: ['name', 'loanNumber', 'phone'],
  accentColor: 'green',
  animationIntensity: 'normal',
};

export interface AppSettingsContextValue {
  settings: AppSettings;
  updateSettings: (fields: Partial<AppSettings>) => Promise<boolean>;
  isSaving: boolean;
  error: string | null;
}

// Split into its own plain (non-JSX) module, separate from
// AppSettingsProvider in useAppSettings.tsx, purely so that file can
// export only a component -- oxlint's react-refresh rule warns when a
// file mixes component and non-component exports, since Fast Refresh
// can't reliably hot-reload that combination.
export const AppSettingsContext = createContext<AppSettingsContextValue | null>(null);

export const useAppSettings = (): AppSettingsContextValue => {
  const context = useContext(AppSettingsContext);
  if (!context) {
    throw new Error('useAppSettings must be used within an AppSettingsProvider (see main.tsx)');
  }
  return context;
};
