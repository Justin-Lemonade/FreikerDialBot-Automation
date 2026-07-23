import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Thin wrapper over window.Telegram.WebApp (injected by the
 * telegram-web-app.js script tag in index.html). Every call is guarded
 * for the "not actually running inside Telegram" case (e.g. local
 * browser testing during development) so the rest of the app never has
 * to null-check window.Telegram itself.
 */
export const useTelegram = () => {
  const [isReady, setIsReady] = useState(false);
  const backButtonCallbackRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (webApp) {
      webApp.ready();
      setIsReady(true);
    }
  }, []);

  const expand = useCallback(() => {
    window.Telegram?.WebApp?.expand();
  }, []);

  const setBackButton = useCallback((visible: boolean, onClick: () => void) => {
    const backButton = window.Telegram?.WebApp?.BackButton;
    if (!backButton) return;

    if (backButtonCallbackRef.current) {
      backButton.offClick(backButtonCallbackRef.current);
    }

    if (visible) {
      backButton.onClick(onClick);
      backButtonCallbackRef.current = onClick;
      backButton.show();
    } else {
      backButtonCallbackRef.current = null;
      backButton.hide();
    }
  }, []);

  const haptic = useCallback((style: 'light' | 'medium' | 'heavy' | 'success' | 'error' | 'warning') => {
    const feedback = window.Telegram?.WebApp?.HapticFeedback;
    if (!feedback) return;
    if (style === 'success' || style === 'error' || style === 'warning') {
      feedback.notificationOccurred(style);
    } else {
      feedback.impactOccurred(style);
    }
  }, []);

  const showAlert = useCallback((message: string) => {
    const webApp = window.Telegram?.WebApp;
    if (webApp) {
      webApp.showAlert(message);
    } else {
      // Local/browser fallback so this doesn't silently no-op during dev.
      window.alert(message);
    }
  }, []);

  const showConfirm = useCallback((message: string): Promise<boolean> => {
    return new Promise((resolve) => {
      const webApp = window.Telegram?.WebApp;
      if (webApp) {
        webApp.showConfirm(message, (confirmed) => resolve(confirmed));
      } else {
        resolve(window.confirm(message));
      }
    });
  }, []);

  const userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id ?? null;

  return { isReady, expand, setBackButton, haptic, showAlert, showConfirm, userId };
};
