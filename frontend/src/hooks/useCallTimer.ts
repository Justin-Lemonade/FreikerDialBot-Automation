import { useCallback, useRef, useState } from 'react';

const formatSeconds = (totalSeconds: number): string => {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
};

/**
 * Tracks elapsed call duration client-side for display purposes only
 * (the "0:47" ticking label on the call screen). This duration is also
 * sent to /call/result so the backend can persist it in
 * customer_events.duration_seconds -- but the backend never trusts this
 * as authoritative for anything queue-related; it's purely an operator-
 * facing stat, matching how average_seconds_per_customer already works.
 */
export const useCallTimer = () => {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startedAtRef = useRef<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTick = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    clearTick();
    startedAtRef.current = Date.now();
    setElapsedSeconds(0);
    intervalRef.current = setInterval(() => {
      if (startedAtRef.current !== null) {
        setElapsedSeconds(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }
    }, 1000);
  }, [clearTick]);

  const stop = useCallback((): string => {
    clearTick();
    const finalSeconds =
      startedAtRef.current !== null ? Math.floor((Date.now() - startedAtRef.current) / 1000) : elapsedSeconds;
    startedAtRef.current = null;
    return formatSeconds(finalSeconds);
  }, [clearTick, elapsedSeconds]);

  const getDurationSeconds = useCallback((): number => {
    if (startedAtRef.current !== null) {
      return Math.floor((Date.now() - startedAtRef.current) / 1000);
    }
    return elapsedSeconds;
  }, [elapsedSeconds]);

  const getLabel = useCallback((): string => formatSeconds(elapsedSeconds), [elapsedSeconds]);

  return { reset, stop, getLabel, getDurationSeconds };
};
