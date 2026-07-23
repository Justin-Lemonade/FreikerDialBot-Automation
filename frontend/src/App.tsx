import { useCallback, useEffect, useMemo, useState } from 'react';
import { MainLayout } from './layout/MainLayout';
import { Home } from './pages/Home';
import { Call } from './pages/Call';
import { Statistics } from './pages/Statistics';
import { Settings } from './pages/Settings';
import { SessionComplete } from './pages/SessionComplete';
import { useSession } from './hooks/useSession';
import { useCustomer } from './hooks/useCustomer';
import { useTelegram } from './hooks/useTelegram';
import { useCallTimer } from './hooks/useCallTimer';
import { api, ApiError } from './api/client';
import type { Screen } from './types';

const App = () => {
  const [screen, setScreen] = useState<Screen>('home');
  const [showNotes, setShowNotes] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [outcome, setOutcome] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { session, loadState, error: sessionError, isStale, refreshSession, applySession } = useSession();
  const { customer, setFromSession } = useCustomer();
  const telegram = useTelegram();
  const timer = useCallTimer();

  // Poll every 5s so the progress bar / next-customer stay live even if
  // the operator leaves the app idle on one screen -- matches PRIORITY 1:
  // the progress bar must always reflect real, current queue state, not
  // a snapshot from whenever the screen last mounted.
  useEffect(() => {
    refreshSession();
    const interval = setInterval(refreshSession, 5000);
    return () => clearInterval(interval);
  }, [refreshSession]);

  useEffect(() => {
    if (session?.currentCustomer) {
      setFromSession(session.currentCustomer);
    }
  }, [session, setFromSession]);

  useEffect(() => {
    if (telegram.isReady) {
      telegram.expand();
      telegram.setBackButton(screen !== 'home', () => setScreen('home'));
    }
  }, [screen, telegram]);

  // Auto-navigate to the completion screen the moment the backend says
  // the queue is done -- session.completed is real backend state (see
  // MiniAppService.get_current_session's queue_complete finalization),
  // never a client-side guess.
  useEffect(() => {
    if (session?.completed && screen !== 'complete' && screen !== 'statistics' && screen !== 'settings') {
      setScreen('complete');
    }
  }, [session?.completed, screen]);

  const currentCustomer = useMemo(() => customer ?? session?.currentCustomer ?? null, [customer, session]);

  const onStartCall = useCallback(async () => {
    if (!currentCustomer) return;
    timer.reset();
    setScreen('call');
    setActionError(null);
    try {
      await api.startCall(currentCustomer.id);
    } catch (err) {
      // Starting-call bookkeeping failing shouldn't block the operator
      // from actually dialing -- surface it, don't block the phone call.
      setActionError(err instanceof ApiError ? err.message : 'Could not record call start.');
    }
    telegram.haptic('medium');
    if (currentCustomer.phone) {
      window.location.href = `tel:${currentCustomer.phone}`;
    }
  }, [currentCustomer, timer, telegram]);

  const onReturnFromCall = useCallback(() => {
    setOutcome(null);
    telegram.haptic('light');
  }, [telegram]);

  const handleOutcome = useCallback(
    async (nextOutcome: string) => {
      if (!currentCustomer || isSubmitting) return;
      setOutcome(nextOutcome);
      setIsSubmitting(true);
      setActionError(null);
      const durationSeconds = timer.getDurationSeconds();
      try {
        const result = await api.submitCallResult(currentCustomer.id, nextOutcome, durationSeconds);
        if (!result.ok) {
          setActionError(result.error || 'That outcome could not be recorded.');
          setIsSubmitting(false);
          setOutcome(null);
          return;
        }
        timer.stop();
        if (result.session) {
          applySession(result.session);
        }
        setFromSession(result.nextCustomer ?? null);
        telegram.haptic('success');
        setIsSubmitting(false);
        setOutcome(null);
        setShowNotes(false);
        setNoteDraft('');
        if (!result.session?.completed) {
          setScreen('home');
        }
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Could not record that outcome. Please try again.');
        setIsSubmitting(false);
        setOutcome(null);
      }
    },
    [currentCustomer, isSubmitting, timer, applySession, setFromSession, telegram]
  );

  const handleSaveNote = useCallback(async () => {
    if (!currentCustomer || !noteDraft.trim()) return;
    try {
      await api.saveNote(currentCustomer.id, noteDraft.trim());
      setNoteDraft('');
      setShowNotes(false);
      setActionError(null);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Could not save that note.');
    }
  }, [currentCustomer, noteDraft]);

  const renderScreen = () => {
    if (loadState === 'loading' && !session) {
      return (
        <div className="flex min-h-[240px] items-center justify-center text-slate-400">Loading queue…</div>
      );
    }

    if (loadState === 'error' && !session) {
      return (
        <div className="space-y-3 rounded-[24px] border border-red-500/20 bg-red-500/5 p-5 text-center">
          <p className="text-sm text-red-300">{sessionError || 'Could not reach the server.'}</p>
          <button
            onClick={refreshSession}
            className="min-h-[48px] rounded-2xl border border-white/10 bg-slate-900 px-5 text-sm font-semibold active:scale-[0.98]"
          >
            Retry
          </button>
        </div>
      );
    }

    if (screen === 'statistics') {
      return <Statistics />;
    }

    if (screen === 'settings') {
      return <Settings />;
    }

    if (screen === 'complete') {
      return (
        <SessionComplete
          session={session}
          onRetry={async () => {
            try {
              const result = await api.callBack();
              if (result.session) applySession(result.session);
              setFromSession(result.customer);
              setScreen('home');
            } catch (err) {
              setActionError(err instanceof ApiError ? err.message : 'Could not requeue those customers.');
            }
          }}
          onHome={() => setScreen('home')}
        />
      );
    }

    if (screen === 'call') {
      return (
        <Call
          customer={currentCustomer}
          outcome={outcome}
          isSubmitting={isSubmitting}
          durationLabel={timer.getLabel()}
          onStartCall={onStartCall}
          onOutcome={handleOutcome}
          onOpenNotes={() => setShowNotes(true)}
          onReturn={onReturnFromCall}
        />
      );
    }

    return (
      <Home
        session={session}
        customer={currentCustomer}
        onContinue={() => setScreen('call')}
        onNewSession={() => setScreen('call')}
        onStatistics={() => setScreen('statistics')}
        onSettings={() => setScreen('settings')}
      />
    );
  };

  return (
    <MainLayout
      showNotes={showNotes}
      noteDraft={noteDraft}
      onNoteDraftChange={setNoteDraft}
      onSaveNote={handleSaveNote}
      onCancelNotes={() => setShowNotes(false)}
      onToggleNotes={() => setShowNotes((value) => !value)}
      session={session}
      customer={currentCustomer}
      onOpenStats={() => setScreen('statistics')}
      onBackHome={() => setScreen('home')}
      onNext={() => setScreen('call')}
      isStale={isStale}
      bannerError={actionError}
      onDismissError={() => setActionError(null)}
    >
      {renderScreen()}
    </MainLayout>
  );
};

export default App;
