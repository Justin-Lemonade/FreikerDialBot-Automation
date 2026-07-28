import { useEffect, useState } from 'react';
import { StatisticsCard } from '../components/StatisticsCard';
import { api, ApiError } from '../api/client';
import type { StatisticsPayload } from '../types';

export const Statistics = () => {
  const [stats, setStats] = useState<StatisticsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getStatistics()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load statistics.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="p-5 text-center font-data text-lg" style={{ border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }}>
        {error}
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex min-h-[200px] items-center justify-center font-data text-lg" style={{ color: 'var(--text-muted)' }}>
        Loading statistics…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="retro-panel p-5">
        <p className="font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          TODAY'S CALLS
        </p>
        <h2 className="mt-2 font-display text-sm" style={{ color: 'var(--text-primary)' }}>
          PERFORMANCE SNAPSHOT
        </h2>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <StatisticsCard title="ANSWERED" value={`${stats.answered}`} helper="Successful contacts" />
        <StatisticsCard title="DIDN'T ANSWER" value={`${stats.didntAnswer}`} helper="No answer" />
        <StatisticsCard
          title="WRONG NUMBER"
          value={stats.wrongNumber ? `${stats.wrongNumber}` : 'N/A'}
          helper={stats.wrongNumber ? 'Bad contact' : 'Not tracked yet'}
        />
        <StatisticsCard title="AVG CALL TIME" value={stats.averageCallTime} helper="Current average" />
      </div>

      <div className="retro-panel p-4">
        <p className="font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          SUCCESS RATE
        </p>
        <p className="mt-2 font-data text-3xl" style={{ color: 'var(--accent-green)' }}>
          {stats.successRate}
        </p>
      </div>

      <div className="retro-panel p-4">
        <p className="font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          LIFETIME STATISTICS
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <StatisticsCard title="CALLS" value={`${stats.lifetimeCalls}`} helper="Total handled" />
          <StatisticsCard title="SESSIONS" value={`${stats.sessions}`} helper="Completed" />
          <StatisticsCard title="CONTACTED" value={`${stats.customersContacted}`} helper="Successful outcomes" />
          <StatisticsCard
            title="BEST DAY"
            value={stats.bestDay === 'N/A' ? '-' : stats.bestDay}
            helper={stats.bestDay === 'N/A' ? 'Not tracked yet' : 'Highest volume'}
          />
        </div>
      </div>
    </div>
  );
};
