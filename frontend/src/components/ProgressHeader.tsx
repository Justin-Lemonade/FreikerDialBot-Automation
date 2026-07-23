interface Props {
  currentIndex: number;
  totalCount: number;
  progressPercent: number;
  remaining: number;
  averageTime: string;
}

/** Parses "2m 18s" / "45s" / "1m" into total seconds. Falls back to 0 on
 * anything unrecognized rather than throwing -- averageCallTime is a
 * free-form label from the backend, not a strict format contract. */
const parseAverageTimeToSeconds = (averageTime: string): number => {
  const minuteMatch = averageTime.match(/(\d+)\s*m/);
  const secondMatch = averageTime.match(/(\d+)\s*s/);
  const minutes = minuteMatch ? parseInt(minuteMatch[1], 10) : 0;
  const seconds = secondMatch ? parseInt(secondMatch[1], 10) : 0;
  return minutes * 60 + seconds;
};

const formatEstimatedRemaining = (remaining: number, averageTime: string): string => {
  const perCustomerSeconds = parseAverageTimeToSeconds(averageTime);
  if (!perCustomerSeconds || !remaining) return '—';
  const totalMinutes = Math.round((remaining * perCustomerSeconds) / 60);
  if (totalMinutes < 1) return '<1 minute';
  if (totalMinutes === 1) return '1 minute';
  if (totalMinutes < 60) return `${totalMinutes} minutes`;
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  return mins ? `${hours}h ${mins}m` : `${hours}h`;
};

const FILLED_BLOCK = '█';
const EMPTY_BLOCK = '░';
const BAR_LENGTH = 18;

const renderBlockBar = (percent: number): string => {
  const clamped = Math.max(0, Math.min(100, percent));
  const filled = Math.round((clamped / 100) * BAR_LENGTH);
  return FILLED_BLOCK.repeat(filled) + EMPTY_BLOCK.repeat(BAR_LENGTH - filled);
};

export const ProgressHeader = ({ currentIndex, totalCount, progressPercent, remaining, averageTime }: Props) => {
  const estimatedLabel = formatEstimatedRemaining(remaining, averageTime);

  return (
    <div
      className="sticky top-0 z-20 rounded-b-[28px] border-b border-white/10 bg-slate-900/95 px-4 pb-4 backdrop-blur"
      style={{ paddingTop: 'max(0.75rem, env(safe-area-inset-top))' }}
      role="status"
      aria-live="polite"
      aria-label={`${currentIndex} of ${totalCount} customers, ${progressPercent}% complete`}
    >
      <div
        className="mb-2 select-none overflow-hidden whitespace-nowrap font-mono text-[13px] leading-none text-emerald-400"
        aria-hidden="true"
      >
        {renderBlockBar(progressPercent)}
      </div>

      <div className="flex items-baseline justify-between">
        <span className="text-base font-semibold text-slate-100">
          {currentIndex} of {totalCount} Customers
        </span>
        <span className="text-base font-bold text-emerald-400">{progressPercent}%</span>
      </div>

      <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
        <span>Estimated Remaining: {estimatedLabel}</span>
      </div>
    </div>
  );
};
