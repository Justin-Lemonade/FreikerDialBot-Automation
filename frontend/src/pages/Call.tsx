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
      <CustomerCard customer={customer} indexLabel={`17 / 48`} />

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400">Call status</p>
            <p className="text-lg font-semibold">{outcome ? 'Call finished' : 'Ready to dial'}</p>
          </div>
          <div className="rounded-full bg-slate-800 px-3 py-1 text-sm text-slate-300">{durationLabel}</div>
        </div>

        <CallButton label="📞 Call" onClick={onStartCall} />
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="font-semibold">Outcome</p>
          <button onClick={onOpenNotes} className="text-sm text-emerald-300">Add Note</button>
        </div>
        <OutcomeButtons onOutcome={onOutcome} disabled={isSubmitting} />
      </div>

      <button onClick={onReturn} className="w-full rounded-[28px] border border-white/10 bg-slate-900 px-5 py-4 text-lg font-semibold">
        Return from call
      </button>
    </div>
  );
};
