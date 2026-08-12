import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { AppSettings } from '../types';

/**
 * The only Settings state that is real: backed by GET/POST /settings on
 * the Mini App API, which itself is enforced by QueueEngine
 * (maxCallAttempts), read by App.tsx to gate the post-outcome
 * transition (autoAdvance), used by MiniAppService._customer_payload to
 * pick which stored number to auto-display/dial (primaryPhonePreference),
 * used by App.tsx to decide how many upcoming customers to prefetch
 * (preReadyCount), read by CustomerCard to decide which financial
 * fields/preview note to show and how dense its layout is
 * (visibleFields/notesPreview/cardDensity), read by ProgressHeader for
 * its segment count (progressDensity), enforced by
 * MiniAppService.search_customers's search-field scoping
 * (defaultSearchFields), or read by App.tsx to set the accent-color/
 * animation-intensity data attributes on the document root
 * (accentColor/animationIntensity). Everything else on the Settings
 * screen stays a disabled placeholder -- see Settings.tsx.
 *
 * Falls back to the same defaults the backend itself falls back to
 * (unlimited attempts, auto-advance on) so the UI never flashes a
 * different value than what actually governs behavior before the first
 * fetch resolves.
 */
const DEFAULT_SETTINGS: AppSettings = {
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

export const useAppSettings = () => {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getSettings()
      .then((next) => {
        if (!cancelled) setSettings(next);
      })
      .catch(() => {
        // Keep defaults on failure -- these match backend defaults
        // exactly, so this is never a silently-wrong guess.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const updateSettings = useCallback(async (fields: Partial<AppSettings>) => {
    setIsSaving(true);
    setError(null);
    // Optimistic update -- reverted below if the request fails, so a
    // tap always feels immediate but is never left inconsistent with
    // what the backend actually persisted.
    const previous = settings;
    setSettings((current) => ({ ...current, ...fields }));
    try {
      const result = await api.updateSettings(fields);
      if (!result.ok || !result.settings) {
        setSettings(previous);
        setError(result.error || 'Could not save that setting.');
        return false;
      }
      setSettings(result.settings);
      return true;
    } catch (err) {
      setSettings(previous);
      setError(err instanceof ApiError ? err.message : 'Could not save that setting.');
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [settings]);

  return { settings, updateSettings, isSaving, error };
};
