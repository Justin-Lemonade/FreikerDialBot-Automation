import { CallButton } from '../components/CallButton';
import { CustomerCard } from '../components/CustomerCard';
import { OutcomeButtons } from '../components/OutcomeButtons';
import type { Customer } from '../types';

interface Props {
  customer: Customer | null;
  outcome: string | null;
  isSubmitting: boolean;
  durationLabel: string;
  onStartCall: () => void;
  onOutcome: (outcome: string) => void;
  onOpenNotes: () => void;
  onReturn: () => void;
}

export const Call = ({ customer, outcome, isSubmitting, durationLabel, onStartCall, onOutcome, onOpenNotes, onReturn }: Props) => {
  return (
    <div className="space-y-4">
      {/* Current Customer -- dominates the screen */}
      <CustomerCard customer={customer} />

      {/* Primary Actions */}
      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-300">{outcome ? 'Call finished' : 'Ready to dial'}</p>
          <div className="rounded-full bg-slate-800 px-3 py-1 text-sm text-slate-300">{durationLabel}</div>
        </div>
        <CallButton label="📞 Call" onClick={onStartCall} disabled={!customer} />
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="mb-3 text-sm font-semibold text-slate-300">Outcome</p>
        <OutcomeButtons onOutcome={onOutcome} disabled={isSubmitting || !customer} />
      </div>

      {/* Secondary Actions */}
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onOpenNotes}
          className="min-h-[48px] rounded-2xl border border-white/10 bg-slate-900 px-4 text-sm font-semibold text-emerald-300 active:scale-[0.98]"
        >
          📝 Add Note
        </button>
        <button
          onClick={onReturn}
          className="min-h-[48px] rounded-2xl border border-white/10 bg-slate-900 px-4 text-sm font-semibold active:scale-[0.98]"
        >
          Return from Call
        </button>
      </div>
    </div>
  );
};
