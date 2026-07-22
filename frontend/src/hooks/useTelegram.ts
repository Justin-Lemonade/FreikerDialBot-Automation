import { useEffect, useState } from 'react';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand: () => void;
        setHeaderColor: (color: string) => void;
        setBackgroundColor: (color: string) => void;
        isExpanded: boolean;
        initDataUnsafe?: { user?: { id?: number } };
        themeParams?: Record<string, string>;
        HapticFeedback?: {
          impactOccurred: (style: string) => void;
        };
        showAlert: (message: string) => void;
        BackButton?: {
          show: () => void;
          hide: () => void;
          onClick: (callback: () => void) => void;
        };
      };
    };
  }
}

export const useTelegram = () => {
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    webApp.ready();
    webApp.expand();
    webApp.setHeaderColor?.('#0f172a');
    webApp.setBackgroundColor?.('#0f172a');
    setIsReady(true);
  }, []);

  const expand = () => window.Telegram?.WebApp?.expand();
  const haptic = (style: 'light' | 'medium' | 'success') => {
    const feedback = window.Telegram?.WebApp?.HapticFeedback;
    if (feedback) {
      feedback.impactOccurred(style === 'success' ? 'rigid' : style === 'medium' ? 'medium' : 'light');
    }
  };
  const setBackButton = (visible: boolean, callback?: () => void) => {
    const backButton = window.Telegram?.WebApp?.BackButton;
    if (!backButton) return;
    if (visible) {
      backButton.show();
      if (callback) backButton.onClick(callback);
    } else {
      backButton.hide();
    }
  };
  const showAlert = (message: string) => window.Telegram?.WebApp?.showAlert?.(message);

  return { isReady, expand, haptic, setBackButton, showAlert };
};
