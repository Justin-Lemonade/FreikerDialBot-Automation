import type { SessionSummary } from '../types';

interface Props {
  session: SessionSummary | null;
  onRetry: () => void;
  onHome: () => void;
}

export const SessionComplete = ({ session, onRetry, onHome }: Props) => {
  const contacted = session?.progress?.contacted;
  const didNotAnswer = session?.progress?.didNotAnswer;
  const hasBreakdown = contacted !== undefined && didNotAnswer !== undefined;

  return (
    <div className="space-y-4">
      <div className="retro-card p-6 text-center" style={{ borderColor: 'var(--accent-green-strong)' }}>
        <p className="font-display text-[10px]" style={{ color: 'var(--accent-green)' }}>
          SESSION COMPLETE
        </p>
        <h2 className="mt-3 font-data text-3xl" style={{ color: 'var(--text-primary)' }}>
          {session?.customerCount ?? 0} customers processed
        </h2>
        {hasBreakdown && (
          <p className="mt-2 font-data text-lg" style={{ color: 'var(--text-muted)' }}>
            {contacted} contacted • {didNotAnswer} didn&apos;t answer
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onRetry}
          className="retro-button min-h-[56px] font-display text-[10px]"
          style={{ border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
        >
          RETRY NO-ANSWER
        </button>
        <button
          className="retro-button min-h-[56px] font-display text-[10px]"
          style={{ border: '1px solid var(--border-frame)', color: 'var(--text-muted)' }}
        >
          EXPORT
        </button>
      </div>
      <button
        onClick={onHome}
        className="retro-button min-h-[56px] w-full font-display text-sm"
        style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
      >
        RETURN HOME
      </button>
    </div>
  );
};
