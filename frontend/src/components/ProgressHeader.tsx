import { useEffect, useRef, useState } from 'react';

interface Props {
  currentIndex: number;
  totalCount: number;
  progressPercent: number;
  /** Settings > Display > Progress Density -- visual UI density (how
   * many segments the bar renders), not queue semantics: this never
   * changes currentIndex/totalCount/progressPercent, which always come
   * straight from the backend regardless of this setting. */
  density?: 'low' | 'normal' | 'high';
}

// Segment count per density level. "Normal" (20) is the original,
// unchanged default -- Low/High only make the same real percentage
// coarser/finer-grained to look at, never a different percentage.
const SEGMENT_COUNTS: Record<'low' | 'normal' | 'high', number> = { low: 10, normal: 20, high: 30 };

/**
 * Segmented / battery-style progress display (image 5/6 reference),
 * built from real DOM cells rather than a single filled bar -- this is
 * what lets each cell "charge up" individually and glow when progress
 * advances. Purely presentational: percent/count come straight from
 * the backend (session.progress), nothing here computes progress
 * itself.
 *
 * Deliberately one thin row: count + segments + percent together, no
 * separate label line and no estimated-time line. The estimated-remaining
 * line was removed per the UI pass 3 brief ("remove the remaining-time
 * line") -- it was a derived guess (customers-remaining * average call
 * time), not a real backend value, and made this block taller than the
 * brief wants on a screen that must not require constant scrolling.
 */
export const ProgressHeader = ({ currentIndex, totalCount, progressPercent, density = 'normal' }: Props) => {
  const segmentCount = SEGMENT_COUNTS[density];
  const filledSegments = Math.round((Math.max(0, Math.min(100, progressPercent)) / 100) * segmentCount);

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
      className="sticky top-0 z-20 border-b-2 px-4 py-2 backdrop-blur"
      style={{
        paddingTop: 'max(0.5rem, env(safe-area-inset-top))',
        background: 'var(--bg-panel-solid)',
        borderColor: 'var(--border-frame)',
      }}
      role="status"
      aria-live="polite"
      aria-label={`${currentIndex} of ${totalCount} customers, ${progressPercent}% complete`}
    >
      <div className="flex items-center gap-2">
        <span className="font-data text-sm whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>
          {currentIndex}/{totalCount}
        </span>
        <div className="flex flex-1 gap-[3px]" aria-hidden="true">
          {Array.from({ length: segmentCount }, (_, index) => {
            const isFilled = index < filledSegments;
            const isNewest = isFilled && index === filledSegments - 1 && justCharged;
            return (
              <div
                key={index}
                className={`h-2.5 flex-1 rounded-[2px] ${isNewest ? 'progress-cell is-charging' : ''}`}
                style={{
                  background: isFilled ? 'var(--accent-green)' : 'var(--bg-panel-raised)',
                  border: `1px solid ${isFilled ? 'var(--accent-green-strong)' : 'var(--border-frame)'}`,
                }}
              />
            );
          })}
        </div>
        <span
          className={`font-display text-[10px] whitespace-nowrap ${justIncremented ? 'progress-count is-pulsing' : 'progress-count'}`}
          style={{ color: 'var(--accent-green)' }}
        >
          {progressPercent}%
        </span>
      </div>
    </div>
  );
};
