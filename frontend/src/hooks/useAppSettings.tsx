import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { api, ApiError } from '../api/client';
import type { AppSettings } from '../types';
import { AppSettingsContext, DEFAULT_SETTINGS } from './appSettingsContext';

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
 * A plain per-call-site useState (the previous implementation) meant
 * every component that called useAppSettings() -- App.tsx AND every
 * individual row in Settings.tsx -- got its OWN independent copy of
 * this state, each with its own mount-time GET /settings fetch. A row
 * saving a change updated only that row's own local state (and the
 * backend); every OTHER instance, including App.tsx's -- the one that
 * actually drives data-accent/data-motion, the props passed to
 * Home/CustomerCard/MainLayout, and onStartCall's phone logic --
 * stayed stale until a full page reload. Found during UI Pass 8's
 * audit (section 20, "Live Settings State" / section 25, "settings
 * that persist correctly but do not actually affect behavior") by
 * tracing every call site rather than trusting that a green test
 * suite meant this worked. This Provider is the fix: the one real
 * useState/useEffect/updateSettings instance (unchanged logic, just
 * relocated), shared via Context so every call site -- App.tsx and
 * every Settings.tsx row alike -- reads and writes the same value.
 */
export const AppSettingsProvider = ({ children }: { children: ReactNode }) => {
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
    // what the backend actually persisted. Because this state now
    // lives in one Provider instance, this update is immediately
    // visible to every consumer (App.tsx's data-accent/data-motion
    // effects, Home/CustomerCard's props, etc.), not just the row
    // that triggered it.
    let previous: AppSettings | undefined;
    setSettings((current) => {
      previous = current;
      return { ...current, ...fields };
    });
    try {
      const result = await api.updateSettings(fields);
      if (!result.ok || !result.settings) {
        if (previous) setSettings(previous);
        setError(result.error || 'Could not save that setting.');
        return false;
      }
      setSettings(result.settings);
      return true;
    } catch (err) {
      if (previous) setSettings(previous);
      setError(err instanceof ApiError ? err.message : 'Could not save that setting.');
      return false;
    } finally {
      setIsSaving(false);
    }
  }, []);

  return <AppSettingsContext.Provider value={{ settings, updateSettings, isSaving, error }}>{children}</AppSettingsContext.Provider>;
};
