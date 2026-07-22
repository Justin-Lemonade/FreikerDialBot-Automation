import { useEffect, useState } from 'react';

export const useCallTimer = () => {
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!startedAt) return;

    const tick = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => window.clearInterval(tick);
  }, [startedAt]);

  const reset = () => {
    setStartedAt(Date.now());
    setSeconds(0);
  };

  const stop = () => {
    const currentSeconds = seconds || Math.floor((Date.now() - (startedAt ?? Date.now())) / 1000);
    setStartedAt(null);
    setSeconds(currentSeconds);
    return getLabelFromSeconds(currentSeconds);
  };

  const getDurationSeconds = () => seconds;

  const getLabel = () => getLabelFromSeconds(seconds);

  return { reset, stop, getDurationSeconds, getLabel };
};

const getLabelFromSeconds = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
};
