import { useCallback, useEffect, useMemo, useState } from 'react';
import { MainLayout } from './layout/MainLayout';
import { Landing } from './pages/Landing';
import { Home } from './pages/Home';
import { Statistics } from './pages/Statistics';
import { SessionComplete } from './pages/SessionComplete';
import { Commands } from './pages/Commands';
import { Search } from './pages/Search';
import { CustomerDetail } from './pages/CustomerDetail';
import { Upload } from './pages/Upload';
import { useSession } from './hooks/useSession';
import { useCustomer } from './hooks/useCustomer';
import { useTelegram } from './hooks/useTelegram';
import { useCallTimer } from './hooks/useCallTimer';
import { useAppSettings } from './hooks/useAppSettings';
import { useUpcomingQueue } from './hooks/useUpcomingQueue';
import { api, ApiError } from './api/client';
import type { Customer, Screen } from './types';

/** Sentinel wrapper so "holding a pending customer whose value happens
 * to be null" (queue about to complete) is distinguishable from "not
 * holding anything" -- see the autoAdvance handling in handleOutcome. */
interface PendingAdvance {
  customer: Customer | null;
}

const App = () => {
  const [screen, setScreen] = useState<Screen>('home');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [outcome, setOutcome] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null);
  const [detailReturnScreen, setDetailReturnScreen] = useState<Screen>('search');
  const [pendingSearchQuery, setPendingSearchQuery] = useState<string | null>(null);
  const [pendingAdvance, setPendingAdvance] = useState<PendingAdvance | null>(null);
  // Settings > Phone Handling > Quick Number Switching: which number
  // CALL CUSTOMER dials next. Reset to the backend's own preferred
  // number (customer.phone, already Primary-Phone-Preference-ordered)
  // whenever the current customer actually changes below -- this state
  // only ever *overrides* that default for the customer it was picked
  // on, it never persists across customers.
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);

  const { session, loadState, error: sessionError, isStale, lastSyncedAt, refreshSession, applySession } = useSession();
  const { customer, setFromSession } = useCustomer();
  const telegram = useTelegram();
  const timer = useCallTimer();
  const { settings } = useAppSettings();

  // Poll every 5s so the progress bar / current customer stay live even
  // if the operator leaves the app idle on one screen -- the progress
  // display must always reflect real, current queue state, not a
  // snapshot from whenever the screen last mounted.
  useEffect(() => {
    refreshSession();
    const interval = setInterval(refreshSession, 5000);
    return () => clearInterval(interval);
  }, [refreshSession]);

  useEffect(() => {
    if (session?.currentCustomer && !pendingAdvance) {
      setFromSession(session.currentCustomer);
    }
  }, [session, setFromSession, pendingAdvance]);

  useEffect(() => {
    if (telegram.isReady) {
      telegram.expand();
      telegram.setBackButton(screen !== 'home', () => setScreen('home'));
    }
  }, [screen, telegram]);

  // Auto-navigate to the completion screen the moment the backend says
  // the queue is done -- session.completed is real backend state (see
  // MiniAppService.get_current_session's queue_complete finalization),
  // never a client-side guess. Landing ('home') is exempted: it's a
  // resting command-center screen now, not part of the active
  // workflow, so completing shouldn't yank someone away from it the
  // way it does from the live 'calling' screen.
  useEffect(() => {
    const exemptScreens: Screen[] = ['home', 'complete', 'statistics', 'commands', 'search', 'customerDetail'];
    if (session?.completed && !exemptScreens.includes(screen)) {
      setScreen('complete');
    }
  }, [session?.completed, screen]);

  const currentCustomer = useMemo(() => customer ?? session?.currentCustomer ?? null, [customer, session]);
  const upcomingPreview = useUpcomingQueue(currentCustomer?.id, settings.preReadyCount);

  // A manually-selected phone only applies to the customer it was
  // picked for -- clear it the moment the active customer actually
  // changes, so a leftover selection from the previous customer can
  // never silently carry over and dial the wrong person.
  useEffect(() => {
    setSelectedPhone(null);
  }, [currentCustomer?.id]);

  const activePhone = (currentCustomer?.phones.some((entry) => entry.number === selectedPhone)
    ? selectedPhone
    : null) ?? currentCustomer?.phone ?? undefined;

  const onStartCall = useCallback(() => {
    if (!currentCustomer || !activePhone) return;
    timer.reset();
    setActionError(null);
    telegram.haptic('medium');
    // Dial immediately and synchronously, inside this click handler's
    // own call stack -- tel: navigation only reliably works while
    // still inside the original user-gesture event; several mobile
    // browsers (including Telegram's in-app WebView) silently block
    // it once execution has crossed an await/microtask boundary. This
    // used to await api.startCall() first, which pushed the
    // navigation past that boundary and could make the button appear
    // to do nothing.
    window.location.href = `tel:${activePhone}`;
    // Bookkeeping happens after, fire-and-forget: a failure here must
    // never block or delay the actual phone call.
    api.startCall(currentCustomer.id).catch((err) => {
      setActionError(err instanceof ApiError ? err.message : 'Could not record call start.');
    });
  }, [currentCustomer, activePhone, timer, telegram]);

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
        // Auto Advance (Settings > Calling Behavior) gates whether the
        // next customer's card replaces this one immediately, or waits
        // for an explicit "Next Customer" tap -- see advanceToNextCustomer
        // below and the pendingAdvance guard on the session-poll effect
        // above. Either way this is the backend's own nextCustomer, not
        // a client-side guess.
        if (settings.autoAdvance) {
          setFromSession(result.nextCustomer ?? null);
        } else {
          setPendingAdvance({ customer: result.nextCustomer ?? null });
        }
        telegram.haptic('success');
        setIsSubmitting(false);
        setOutcome(null);
        setShowNotes(false);
        setNoteDraft('');
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Could not record that outcome. Please try again.');
        setIsSubmitting(false);
        setOutcome(null);
      }
    },
    [currentCustomer, isSubmitting, timer, applySession, setFromSession, telegram, settings.autoAdvance]
  );

  /** Applies a customer the backend already handed back in
   * /call/result's response, held until now because Auto Advance is
   * off. Nothing is re-fetched -- this is the same real nextCustomer,
   * just displayed on a tap instead of automatically. */
  const advanceToNextCustomer = useCallback(() => {
    if (!pendingAdvance) return;
    setFromSession(pendingAdvance.customer);
    setPendingAdvance(null);
  }, [pendingAdvance, setFromSession]);

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
        <div className="flex min-h-[240px] items-center justify-center font-data text-lg" style={{ color: 'var(--text-muted)' }}>
          Loading queue…
        </div>
      );
    }

    if (loadState === 'error' && !session) {
      return (
        <div className="space-y-3 p-5 text-center retro-panel">
          <p className="font-data text-lg" style={{ color: 'var(--accent-red)' }}>
            {sessionError || 'Could not reach the server.'}
          </p>
          <button
            onClick={refreshSession}
            className="retro-button min-h-[48px] font-display text-[10px]"
            style={{ border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
          >
            RETRY
          </button>
        </div>
      );
    }

    if (screen === 'statistics') {
      return <Statistics />;
    }

    if (screen === 'commands') {
      return (
        <Commands
          session={session}
          onOpenStatistics={() => setScreen('statistics')}
          onOpenNotes={() => setShowNotes(true)}
          onOpenSearch={(query) => {
            setPendingSearchQuery(query ?? null);
            setScreen('search');
          }}
          onSessionChanged={applySession}
        />
      );
    }

    if (screen === 'search') {
      return (
        <Search
          initialQuery={pendingSearchQuery ?? undefined}
          onSelectCustomer={(selected) => {
            setSelectedCustomerId(selected.id);
            setDetailReturnScreen('search');
            setScreen('customerDetail');
          }}
        />
      );
    }

    if (screen === 'customerDetail' && selectedCustomerId) {
      return (
        <CustomerDetail
          customerId={selectedCustomerId}
          onBack={() => setScreen(detailReturnScreen)}
          backLabel={detailReturnScreen === 'calling' ? '← BACK TO CALL' : '← BACK TO SEARCH'}
        />
      );
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
              setScreen('calling');
            } catch (err) {
              setActionError(err instanceof ApiError ? err.message : 'Could not requeue those customers.');
            }
          }}
          onHome={() => setScreen('home')}
        />
      );
    }

    if (screen === 'calling') {
      return (
        <Home
          session={session}
          customer={currentCustomer}
          outcome={outcome}
          isSubmitting={isSubmitting}
          durationLabel={timer.getLabel()}
          onStartCall={onStartCall}
          onOutcome={handleOutcome}
          onOpenNotes={() => setShowNotes(true)}
          hasPendingAdvance={Boolean(pendingAdvance)}
          onAdvanceNextCustomer={advanceToNextCustomer}
          activePhone={activePhone}
          onSelectPhone={setSelectedPhone}
          visibleFields={settings.visibleFields}
          upcomingPreview={upcomingPreview}
          onOpenDetail={() => {
            if (!currentCustomer) return;
            setSelectedCustomerId(currentCustomer.id);
            setDetailReturnScreen('calling');
            setScreen('customerDetail');
          }}
        />
      );
    }

    if (screen === 'upload') {
      return (
        <Upload
          onBack={() => setScreen('home')}
          onImported={() => {
            refreshSession();
          }}
        />
      );
    }

    // Landing: the real Home screen -- a command center, not the
    // calling workflow (UI pass 4). Always what 'home' means and
    // always what the bottom nav's Home button returns to.
    return (
      <Landing
        session={session}
        onContinueSession={() => setScreen('calling')}
        onOpenUpload={() => setScreen('upload')}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenSearch={() => {
          setPendingSearchQuery(null);
          setScreen('search');
        }}
        onOpenCommands={() => setScreen('commands')}
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
      session={session}
      customer={currentCustomer}
      onNavigateHome={() => setScreen('home')}
      onNavigateCommands={() => setScreen('commands')}
      onNavigateSearch={() => {
        setPendingSearchQuery(null);
        setScreen('search');
      }}
      activeScreen={screen}
      isSettingsOpen={isSettingsOpen}
      onOpenSettings={() => setIsSettingsOpen(true)}
      onCloseSettings={() => setIsSettingsOpen(false)}
      isStale={isStale}
      lastSyncedAt={lastSyncedAt}
      bannerError={actionError}
      onDismissError={() => setActionError(null)}
    >
      {renderScreen()}
    </MainLayout>
  );
};

export default App;
