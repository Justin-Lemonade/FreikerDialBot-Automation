import { useState } from 'react';
import { CallButton } from '../components/CallButton';
import { CustomerCard } from '../components/CustomerCard';
import { OutcomeButtons } from '../components/OutcomeButtons';
import type { Customer, SessionSummary, VisibleField } from '../types';

interface Props {
  session: SessionSummary | null;
  customer: Customer | null;
  outcome: string | null;
  isSubmitting: boolean;
  durationLabel: string;
  onStartCall: () => void;
  onOutcome: (outcome: string) => void;
  onOpenNotes: () => void;
  onOpenDetail: () => void;
  /** True when Auto Advance (Settings) is off and an outcome has just
   * been recorded -- the card below is frozen on the just-completed
   * customer until onAdvanceNextCustomer is tapped. */
  hasPendingAdvance?: boolean;
  onAdvanceNextCustomer?: () => void;
  /** Settings > Phone Handling > Quick Number Switching -- which number
   * CALL CUSTOMER will dial next, and the callback to change it. Lifted
   * up to App.tsx since onStartCall (also owned by App.tsx) needs to
   * read the same value. */
  activePhone?: string;
  onSelectPhone?: (phone: string) => void;
  /** Settings > Display > Visible Fields -- which financial fields
   * CustomerCard's info grid shows. */
  visibleFields?: VisibleField[];
  /** Settings > Display > Compact vs Expanded Cards. */
  cardDensity?: 'compact' | 'expanded';
  /** Settings > Display > Notes Preview -- show a truncated preview of
   * the latest note on the calling card. */
  notesPreview?: boolean;
  /** Settings > Queue > Pre-ready Count -- up to that many customers
   * after the current one, fetched via useUpcomingQueue. Empty when the
   * setting is "None" (0). Preview only: tapping nothing here changes
   * queue state, it's just "who's coming up". */
  upcomingPreview?: Customer[];
}

const CARD_EXIT_ANIMATION_MS = 380;

/**
 * The live calling workflow -- active customer card, Call button,
 * outcome buttons. Reached only via Landing's "Continue Session"
 * button (App.tsx's 'calling' screen), not the app's default/launch
 * screen anymore -- that's Landing.tsx now (UI pass 4: "Do NOT reuse
 * the queue workflow as the Home screen").
 */
export const Home = ({
  session,
  customer,
  outcome,
  isSubmitting,
  durationLabel,
  onStartCall,
  onOutcome,
  onOpenNotes,
  onOpenDetail,
  hasPendingAdvance,
  onAdvanceNextCustomer,
  activePhone,
  onSelectPhone,
  visibleFields,
  cardDensity,
  notesPreview,
  upcomingPreview,
}: Props) => {
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
    // Defensive fallback only -- App.tsx only lets the operator reach
    // this screen via Landing's "Continue Session", which itself only
    // shows once session.customerCount > 0. This covers the edge case
    // of the queue completing/emptying out from under an already-open
    // calling screen before the completed-session redirect fires.
    return (
      <div className="flex min-h-[240px] items-center justify-center p-6 text-center font-data text-lg" style={{ color: 'var(--text-muted)' }}>
        No active queue.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <CustomerCard
        key={customer?.id ?? 'none'}
        customer={customer}
        isLeaving={isLeaving}
        indexLabel={session ? `${session.currentCustomerIndex}/${session.customerCount}` : undefined}
        activePhone={activePhone}
        onSelectPhone={onSelectPhone}
        visibleFields={visibleFields}
        cardDensity={cardDensity}
        notesPreview={notesPreview}
      />

      {hasPendingAdvance ? (
        // Auto Advance is off: the outcome above was already recorded
        // and the backend already has the real next customer queued up
        // (see App.tsx's pendingAdvance) -- this button just reveals it,
        // it does not trigger any new backend write.
        <button
          onClick={onAdvanceNextCustomer}
          className="retro-button min-h-[56px] w-full font-display text-sm"
          style={{ background: 'var(--accent-blue)', color: 'var(--accent-blue-text)', border: '2px solid var(--accent-blue)' }}
        >
          NEXT CUSTOMER →
        </button>
      ) : (
        <>
          <CallButton label="📞 CALL CUSTOMER" onClick={onStartCall} disabled={!activePhone} />

          <OutcomeButtons
            onOutcome={handleOutcomeClick}
            onMoreInfo={onOpenDetail}
            disabled={isSubmitting || isLeaving || !customer}
            moreInfoDisabled={!customer}
          />

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

          {upcomingPreview && upcomingPreview.length > 0 && (
            // Settings > Queue > Pre-ready Count made real: a glance at
            // who's coming up, not another way to jump the queue --
            // there's no tap handler here on purpose.
            <div>
              <p className="mb-1.5 font-display text-[8px]" style={{ color: 'var(--text-muted)' }}>
                ⏭ UP NEXT
              </p>
              <div className="flex gap-2 overflow-x-auto pb-1">
                {upcomingPreview.map((entry) => (
                  <div
                    key={entry.id}
                    className="min-w-[120px] shrink-0 px-3 py-2 font-data text-sm"
                    style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
                  >
                    <p className="truncate" style={{ color: 'var(--text-primary)' }}>
                      {entry.name || '(name missing)'}
                    </p>
                    <p className="truncate text-xs">{entry.loanNumber}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
