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
      <div className="rounded-[24px] border border-red-500/20 bg-red-500/5 p-5 text-center text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!stats) {
    return <div className="flex min-h-[200px] items-center justify-center text-slate-400">Loading statistics…</div>;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-[32px] border border-white/10 bg-gradient-to-b from-slate-900 to-slate-800 p-5 shadow-2xl">
        <p className="text-[11px] uppercase tracking-[0.3em] text-slate-400">Today&apos;s calls</p>
        <h2 className="mt-2 text-2xl font-semibold">Performance snapshot</h2>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <StatisticsCard title="Answered" value={`${stats.answered}`} helper="Successful contacts" />
        <StatisticsCard title="Didn't Answer" value={`${stats.didntAnswer}`} helper="No answer" />
        <StatisticsCard
          title="Wrong Number"
          value={stats.wrongNumber ? `${stats.wrongNumber}` : 'N/A'}
          helper={stats.wrongNumber ? 'Bad contact' : 'Not tracked yet'}
        />
        <StatisticsCard title="Average Call Time" value={stats.averageCallTime} helper="Current average" />
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="text-sm text-slate-400">Success rate</p>
        <p className="mt-2 text-3xl font-semibold">{stats.successRate}</p>
      </div>

      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="text-sm text-slate-400">Lifetime statistics</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <StatisticsCard title="Calls" value={`${stats.lifetimeCalls}`} helper="Total handled" />
          <StatisticsCard title="Sessions" value={`${stats.sessions}`} helper="Completed" />
          <StatisticsCard title="Customers Contacted" value={`${stats.customersContacted}`} helper="Successful outcomes" />
          <StatisticsCard
            title="Best Day"
            value={stats.bestDay === 'N/A' ? '—' : stats.bestDay}
            helper={stats.bestDay === 'N/A' ? 'Not tracked yet' : 'Highest volume'}
          />
        </div>
      </div>
    </div>
  );
};
