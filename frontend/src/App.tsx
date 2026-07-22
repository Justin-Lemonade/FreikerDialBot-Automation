import { useEffect, useMemo, useState } from 'react';
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
import { api } from './api/client';
import type { Screen } from './types';

const App = () => {
  const [screen, setScreen] = useState<Screen>('home');
  const [showNotes, setShowNotes] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [outcome, setOutcome] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { session, refreshSession, nextSession } = useSession();
  const { customer, refreshCustomer, nextCustomer, prefetchCustomer } = useCustomer();
  const telegram = useTelegram();
  const timer = useCallTimer();

  useEffect(() => {
    refreshSession();
    refreshCustomer();
    prefetchCustomer();
  }, [refreshSession, refreshCustomer, prefetchCustomer]);

  useEffect(() => {
    if (telegram.isReady) {
      telegram.expand();
      telegram.setBackButton(true, () => {
        if (screen === 'call') {
          setScreen('home');
        } else if (screen !== 'home') {
          setScreen('home');
        }
      });
    }
  }, [screen, telegram]);

  const currentCustomer = useMemo(() => customer ?? session?.currentCustomer ?? null, [customer, session]);

  const onStartCall = async () => {
    if (!currentCustomer) return;
    timer.reset();
    setScreen('call');
    await api.startCall({ customerId: currentCustomer.id, startedAt: new Date().toISOString() }).catch(() => undefined);
    telegram.haptic('medium');
    window.location.href = `tel:${currentCustomer.phone}`;
  };

  const onReturnFromCall = () => {
    const duration = timer.stop();
    setOutcome(null);
    setScreen('call');
    telegram.haptic('light');
    telegram.showAlert(`Call finished • ${duration}`);
  };

  const handleOutcome = async (nextOutcome: string) => {
    if (!currentCustomer) return;
    setOutcome(nextOutcome);
    setIsSubmitting(true);
    setTimeout(async () => {
      await api.submitResult({ customerId: currentCustomer.id, outcome: nextOutcome, duration: timer.getDurationSeconds() }).catch(() => undefined);
      setIsSubmitting(false);
      await nextCustomer();
      await nextSession();
      setScreen('home');
      setShowNotes(false);
      setNoteDraft('');
      telegram.haptic('success');
    }, 450);
  };

  const handleSaveNote = async () => {
    if (!currentCustomer || !noteDraft.trim()) return;
    await api.saveNote({ customerId: currentCustomer.id, note: noteDraft.trim() }).catch(() => undefined);
    setNoteDraft('');
    setShowNotes(false);
  };

  const renderScreen = () => {
    if (screen === 'statistics') {
      return <Statistics session={session} />;
    }

    if (screen === 'settings') {
      return <Settings />;
    }

    if (screen === 'complete') {
      return <SessionComplete session={session} onRetry={() => setScreen('home')} onHome={() => setScreen('home')} />;
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
      progressLabel={`${session?.currentCustomerIndex ?? 0}/${session?.customerCount ?? 0}`}
      onOpenStats={() => setScreen('statistics')}
      onBackHome={() => setScreen('home')}
      onNext={() => setScreen('call')}
    >
      {renderScreen()}
    </MainLayout>
  );
};

export default App;
