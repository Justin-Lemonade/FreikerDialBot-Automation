import { useState } from 'react';
import { CallButton } from '../components/CallButton';
import { CustomerCard } from '../components/CustomerCard';
import { OutcomeButtons } from '../components/OutcomeButtons';
import type { Customer, SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  customer: Customer | null;
  outcome: string | null;
  isSubmitting: boolean;
  durationLabel: string;
  onStartCall: () => void;
  onOutcome: (outcome: string) => void;
  onOpenNotes: () => void;
  onOpenUpload: () => void;
}

const CARD_EXIT_ANIMATION_MS = 380;

/**
 * Home is the calling workflow directly -- no separate "Call" screen to
 * navigate to first (per the reference images: the active customer
 * card, Call button, and outcome buttons all live on the Home tab
 * itself, and per the explicit request that Home merge calling and
 * uploading). When there's no active queue, this shows the
 * upload/welcome state instead (image 2's "Welcome Back" reference).
 */
export const Home = ({ session, customer, outcome, isSubmitting, durationLabel, onStartCall, onOutcome, onOpenNotes, onOpenUpload }: Props) => {
  const [isLeaving, setIsLeaving] = useState(false);
  const hasQueue = Boolean(session?.customerCount);

  const handleOutcomeClick = (value: string) => {
    if (isSubmitting || isLeaving) return;
    setIsLeaving(true);
    setTimeout(() => {
      onOutcome(value);
      setIsLeaving(false);
    }, CARD_EXIT_ANIMATION_MS);
  };

  if (!hasQueue) {
    return (
      <div className="-mx-4 -mt-4 flex min-h-[70vh] flex-col items-center justify-center gap-6 p-6 text-center retro-starfield">
        <h1
          className="font-display text-2xl leading-relaxed"
          style={{ color: 'var(--text-primary)', textShadow: '0 0 12px rgba(238, 244, 240, 0.6), 0 0 24px rgba(111, 224, 138, 0.3)' }}
        >
          WELCOME
          <br />
          BACK
        </h1>
        <div className="w-full max-w-xs space-y-3">
          <button
            onClick={onOpenUpload}
            disabled
            title="Not yet available -- import customer data via Telegram chat with the bot for now"
            className="retro-button min-h-[56px] w-full font-display text-xs disabled:cursor-not-allowed disabled:opacity-50"
            style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
          >
            UPLOAD CONTACTS
          </button>
          <p className="font-data text-sm" style={{ color: 'var(--text-dim)' }}>
            Coming soon — use Telegram chat with the bot for now.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <CustomerCard key={customer?.id ?? 'none'} customer={customer} isLeaving={isLeaving} />

      <CallButton label="📞 CALL CUSTOMER" onClick={onStartCall} disabled={!customer} />

      <OutcomeButtons onOutcome={handleOutcomeClick} disabled={isSubmitting || isLeaving || !customer} />

      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onOpenNotes}
          className="retro-button min-h-[48px] font-display text-[9px]"
          style={{ border: '1px solid var(--border-frame)', color: 'var(--accent-green)' }}
        >
          NOTE
        </button>
        <div
          className="flex min-h-[48px] items-center justify-center font-data text-base"
          style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
        >
          {outcome ? 'Call finished' : durationLabel}
        </div>
      </div>
    </div>
  );
};
