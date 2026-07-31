import { useEffect, useRef, useState } from 'react';

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
  if (!perCustomerSeconds || !remaining) return '-';
  const totalMinutes = Math.round((remaining * perCustomerSeconds) / 60);
  if (totalMinutes < 1) return '<1 min';
  if (totalMinutes === 1) return '1 min';
  if (totalMinutes < 60) return `${totalMinutes} min`;
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  return mins ? `${hours}h ${mins}m` : `${hours}h`;
};

const SEGMENT_COUNT = 20;

/**
 * Segmented / battery-style progress display (image 5/6 reference),
 * built from real DOM cells rather than a single filled bar -- this is
 * what lets each cell "charge up" individually and glow when progress
 * advances, per the brief's recharge-animation requirement. Purely
 * presentational: percent/count come straight from the backend
 * (session.progress), nothing here computes progress itself.
 */
export const ProgressHeader = ({ currentIndex, totalCount, progressPercent, remaining, averageTime }: Props) => {
  const estimatedLabel = formatEstimatedRemaining(remaining, averageTime);
  const filledSegments = Math.round((Math.max(0, Math.min(100, progressPercent)) / 100) * SEGMENT_COUNT);

  // Track the previous filled-segment count and current-index so we can
  // briefly flag "just advanced" cells/number for the glow/pulse
  // animation, without needing any animation library.
  const previousFilledRef = useRef(filledSegments);
  const previousIndexRef = useRef(currentIndex);
  const [justCharged, setJustCharged] = useState(false);
  const [justIncremented, setJustIncremented] = useState(false);

  useEffect(() => {
    if (filledSegments > previousFilledRef.current) {
      setJustCharged(true);
      const timeout = setTimeout(() => setJustCharged(false), 650);
      previousFilledRef.current = filledSegments;
      return () => clearTimeout(timeout);
    }
    previousFilledRef.current = filledSegments;
  }, [filledSegments]);

  useEffect(() => {
    if (currentIndex > previousIndexRef.current) {
      setJustIncremented(true);
      const timeout = setTimeout(() => setJustIncremented(false), 550);
      previousIndexRef.current = currentIndex;
      return () => clearTimeout(timeout);
    }
    previousIndexRef.current = currentIndex;
  }, [currentIndex]);

  return (
    <div
      className="sticky top-0 z-20 border-b-2 px-4 pb-3 backdrop-blur"
      style={{
        paddingTop: 'max(0.75rem, env(safe-area-inset-top))',
        background: 'var(--bg-panel-solid)',
        borderColor: 'var(--border-frame)',
      }}
      role="status"
      aria-live="polite"
      aria-label={`${currentIndex} of ${totalCount} customers, ${progressPercent}% complete`}
    >
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="font-display text-[10px] whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
          CUSTOMER PROGRESS
        </span>
      </div>

      <div className="mb-2 font-data text-lg" style={{ color: 'var(--text-primary)' }}>
        {currentIndex} / {totalCount} customers
      </div>

      <div className="mb-1.5 flex items-center gap-2">
        <div className="flex flex-1 gap-[3px]" aria-hidden="true">
          {Array.from({ length: SEGMENT_COUNT }, (_, index) => {
            const isFilled = index < filledSegments;
            const isNewest = isFilled && index === filledSegments - 1 && justCharged;
            return (
              <div
                key={index}
                className={`h-3 flex-1 rounded-[2px] ${isNewest ? 'progress-cell is-charging' : ''}`}
                style={{
                  background: isFilled ? 'var(--accent-green)' : 'var(--bg-panel-raised)',
                  border: `1px solid ${isFilled ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
                }}
              />
            );
          })}
        </div>
        <span
          className={`font-display text-xs whitespace-nowrap ${justIncremented ? 'progress-count is-pulsing' : 'progress-count'}`}
          style={{ color: 'var(--accent-green)' }}
        >
          {progressPercent}%
        </span>
      </div>

      <div className="font-display text-[9px]" style={{ color: 'var(--accent-amber)' }}>
        ~{estimatedLabel} REMAINING
      </div>
    </div>
  );
};
